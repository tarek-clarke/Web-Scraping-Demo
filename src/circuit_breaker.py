#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Circuit-Breaker Pattern for F1 Telemetry Streams
==================================================
Developed for the 2026 Cadillac F1 Initiative.

Implements a three-state circuit breaker (CLOSED → OPEN → HALF_OPEN) that
protects the simulation-ready data pipeline from corrupted or drifted
telemetry packets.  Bad data is isolated to a Dead Letter Queue (DLQ)
while the primary pit-wall feed remains clean.

Architecture
------------
              ┌─────────┐   failures >= threshold   ┌────────┐
              │ CLOSED  │ ────────────────────────►  │  OPEN  │
              │ (relay) │                            │ (block)│
              └────┬────┘  ◄──────────────────────── └───┬────┘
                   │          probe succeeds              │
                   │       ┌───────────┐                  │
                   └──────►│ HALF_OPEN │◄─────────────────┘
                           │  (probe)  │  after cooldown
                           └───────────┘

Stakeholder: Mandar Hazare — Data Fidelity for Simulation.
"""

from __future__ import annotations

import enum
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit-Breaker States
# ---------------------------------------------------------------------------
class CircuitState(enum.Enum):
    """Three canonical states of the circuit breaker."""
    CLOSED = "CLOSED"         # Normal operation — packets flow through
    OPEN = "OPEN"             # Tripped — all packets routed to DLQ
    HALF_OPEN = "HALF_OPEN"   # Recovery probe — testing a limited batch


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class TelemetryPacket:
    """Single telemetry observation from the car."""
    packet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sensor: str = ""
    value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DLQRecord:
    """A packet quarantined in the Dead Letter Queue."""
    packet: TelemetryPacket
    reason: str
    circuit_state: str
    quarantined_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    retry_count: int = 0


@dataclass
class CircuitBreakerMetrics:
    """Live metrics exposed to the Health Monitor."""
    state: str = CircuitState.CLOSED.value
    consecutive_failures: int = 0
    total_passed: int = 0
    total_rejected: int = 0
    total_dlq: int = 0
    last_failure_time: Optional[str] = None
    last_state_change: Optional[str] = None
    uptime_ratio: float = 1.0


# ---------------------------------------------------------------------------
# Validators — pluggable checks for Schema Drift & Bit-Flip Detection
# ---------------------------------------------------------------------------
class SchemaValidator:
    """
    Schema-on-Read guard.

    Validates that incoming telemetry conforms to the expected field types
    and value ranges.  Catches the two primary corruption modes:

    1. **Schema Drift** — field names or types change between firmware versions.
    2. **Bit-Flip / Sensor Fault** — values exceed physically plausible bounds.
    """

    # Physically plausible ranges for F1 telemetry sensors (SI units)
    DEFAULT_RANGES: Dict[str, Tuple[float, float]] = {
        "speed":               (0.0, 380.0),       # km/h
        "rpm":                 (0.0, 16_000.0),
        "throttle":            (0.0, 100.0),        # %
        "brake":               (0.0, 100.0),        # %
        "gear":                (0.0, 9.0),
        "drs":                 (0.0, 14.0),
        "engine_temp":         (-40.0, 1000.0),     # °C
        "engine_temperature":  (-40.0, 1000.0),
        "tyre_pressure":       (15.0, 35.0),        # psi
        "brake_temp":          (50.0, 1200.0),      # °C
        "ecu_canbus":          (-1e6, 1e6),
        "aero_load":           (-500.0, 3000.0),    # N
        "heart_rate":          (30.0, 250.0),       # bpm (driver biometrics)
        "g_force_lateral":     (-8.0, 8.0),         # G
        "g_force_longitudinal":(-8.0, 8.0),
        "g_force_vertical":    (-5.0, 5.0),
    }

    def __init__(
        self,
        expected_fields: Optional[List[str]] = None,
        value_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
    ):
        self.expected_fields = expected_fields or []
        self.value_ranges = {**self.DEFAULT_RANGES, **(value_ranges or {})}

    # ------------------------------------------------------------------
    def validate_packet(self, packet: TelemetryPacket) -> Tuple[bool, str]:
        """
        Returns (is_valid, reason).
        """
        sensor = packet.sensor.lower().replace(" ", "_").replace("(", "").replace(")", "")

        # --- Null / missing value ----------------------------------
        if packet.value is None:
            return False, f"null_value|sensor={packet.sensor}"

        # --- Type guard: sensor values must be numeric -------------
        if isinstance(packet.value, str):
            return False, f"string_in_numeric_field|sensor={packet.sensor}|value={packet.value}"

        # --- Range check (bit-flip / impossible reading) -----------
        for key, (lo, hi) in self.value_ranges.items():
            if key in sensor:
                try:
                    v = float(packet.value)
                    if v < lo or v > hi:
                        return False, (
                            f"out_of_range|sensor={packet.sensor}"
                            f"|value={v}|expected=[{lo},{hi}]"
                        )
                except (ValueError, TypeError):
                    return False, f"non_numeric|sensor={packet.sensor}|value={packet.value}"
                break

        return True, "OK"


# ---------------------------------------------------------------------------
# Dead Letter Queue — SQLite-backed for crash resilience
# ---------------------------------------------------------------------------
class DeadLetterQueue:
    """
    Persistent quarantine for rejected telemetry packets.

    Uses SQLite WAL mode for concurrent read access from the Health Monitor
    while the pipeline writes.
    """

    DDL = """
    CREATE TABLE IF NOT EXISTS dead_letters (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        packet_id   TEXT    NOT NULL,
        timestamp   TEXT    NOT NULL,
        sensor      TEXT,
        value       TEXT,
        metadata    TEXT,
        reason      TEXT    NOT NULL,
        circuit_state TEXT  NOT NULL,
        quarantined_at TEXT NOT NULL,
        retry_count INTEGER DEFAULT 0,
        reprocessed INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_dl_sensor ON dead_letters(sensor);
    CREATE INDEX IF NOT EXISTS idx_dl_quarantined ON dead_letters(quarantined_at);
    """

    def __init__(self, db_path: str = "data/dlq.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(self.DDL)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def enqueue(self, record: DLQRecord) -> None:
        """Persist a rejected packet."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO dead_letters
                   (packet_id, timestamp, sensor, value, metadata,
                    reason, circuit_state, quarantined_at, retry_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.packet.packet_id,
                    record.packet.timestamp,
                    record.packet.sensor,
                    json.dumps(record.packet.value),
                    json.dumps(record.packet.metadata),
                    record.reason,
                    record.circuit_state,
                    record.quarantined_at,
                    record.retry_count,
                ),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    def depth(self) -> int:
        """Number of un-reprocessed records in the queue."""
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM dead_letters WHERE reprocessed = 0"
        )
        return cur.fetchone()[0]

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch the most recent DLQ entries."""
        cur = self._conn.execute(
            "SELECT packet_id, sensor, value, reason, quarantined_at "
            "FROM dead_letters WHERE reprocessed = 0 "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def mark_reprocessed(self, packet_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE dead_letters SET reprocessed = 1 WHERE packet_id = ?",
                (packet_id,),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
class TelemetryCircuitBreaker:
    """
    Production circuit breaker for the Cadillac F1 telemetry spine.

    Parameters
    ----------
    failure_threshold : int
        Consecutive bad packets before the breaker trips to OPEN.
    recovery_timeout : float
        Seconds to wait in OPEN before transitioning to HALF_OPEN.
    half_open_max_calls : int
        Number of probe packets allowed in HALF_OPEN before deciding.
    dlq_path : str
        File-system path for the SQLite Dead Letter Queue.
    validator : SchemaValidator | None
        Pluggable validation strategy.  Defaults to F1 telemetry ranges.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        dlq_path: str = "data/dlq.sqlite",
        validator: Optional[SchemaValidator] = None,
    ):
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()

        # Thresholds
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        # Counters
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._half_open_calls = 0
        self._total_passed = 0
        self._total_rejected = 0

        # Timestamps
        self._last_failure_time: Optional[float] = None
        self._last_state_change: Optional[str] = None
        self._opened_at: Optional[float] = None
        self._start_time = time.time()

        # Dependencies
        self.validator = validator or SchemaValidator()
        self.dlq = DeadLetterQueue(db_path=dlq_path)

        # Event hooks (for Health Monitor)
        self._on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None
        self._on_reject: Optional[Callable[[DLQRecord], None]] = None

        logger.info(
            "CircuitBreaker initialised | threshold=%d recovery=%.1fs",
            failure_threshold, recovery_timeout,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        elapsed = max(time.time() - self._start_time, 1)
        total = self._total_passed + self._total_rejected
        uptime = self._total_passed / total if total > 0 else 1.0
        return CircuitBreakerMetrics(
            state=self.state.value,
            consecutive_failures=self._consecutive_failures,
            total_passed=self._total_passed,
            total_rejected=self._total_rejected,
            total_dlq=self.dlq.depth(),
            last_failure_time=(
                datetime.fromtimestamp(self._last_failure_time).isoformat()
                if self._last_failure_time else None
            ),
            last_state_change=self._last_state_change,
            uptime_ratio=round(uptime, 4),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process(self, packet: TelemetryPacket) -> Tuple[bool, str]:
        """
        Submit a telemetry packet to the circuit breaker.

        Returns
        -------
        (accepted, reason) — True if the packet was forwarded to the
        primary pipeline; False if it was routed to the DLQ.
        """
        with self._lock:
            self._maybe_transition_to_half_open()

            # ---- OPEN: reject everything until cooldown expires ----
            if self._state == CircuitState.OPEN:
                return self._reject(packet, "circuit_open")

            # ---- Validate the packet --------------------------------
            is_valid, reason = self.validator.validate_packet(packet)

            if is_valid:
                return self._on_success(packet)
            else:
                return self._on_failure(packet, reason)

    def process_batch(self, packets: List[TelemetryPacket]) -> Dict[str, int]:
        """
        Process a list of packets.  Returns summary counts.
        """
        accepted = 0
        rejected = 0
        for pkt in packets:
            ok, _ = self.process(pkt)
            if ok:
                accepted += 1
            else:
                rejected += 1
        return {"accepted": accepted, "rejected": rejected}

    def reset(self) -> None:
        """Force-close the breaker (manual override from pit wall)."""
        with self._lock:
            old = self._state
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._half_open_calls = 0
            self._half_open_successes = 0
            self._record_state_change(old, CircuitState.CLOSED)
        logger.info("CircuitBreaker manually RESET → CLOSED")

    # ------------------------------------------------------------------
    # Internal state machine
    # ------------------------------------------------------------------
    def _on_success(self, packet: TelemetryPacket) -> Tuple[bool, str]:
        self._total_passed += 1

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            self._half_open_calls += 1
            if self._half_open_successes >= self.half_open_max_calls:
                self._transition(CircuitState.CLOSED)
                self._consecutive_failures = 0
        else:
            # CLOSED — reset failure counter on each success
            self._consecutive_failures = 0

        return True, "OK"

    def _on_failure(self, packet: TelemetryPacket, reason: str) -> Tuple[bool, str]:
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed — reopen immediately
            self._transition(CircuitState.OPEN)
            return self._reject(packet, reason)

        if self._consecutive_failures >= self.failure_threshold:
            self._transition(CircuitState.OPEN)

        return self._reject(packet, reason)

    def _reject(self, packet: TelemetryPacket, reason: str) -> Tuple[bool, str]:
        self._total_rejected += 1
        record = DLQRecord(
            packet=packet,
            reason=reason,
            circuit_state=self._state.value,
        )
        self.dlq.enqueue(record)

        if self._on_reject:
            self._on_reject(record)

        return False, reason

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0
        self._record_state_change(old, new_state)
        logger.info("CircuitBreaker %s → %s", old.value, new_state.value)

        if self._on_state_change:
            self._on_state_change(old, new_state)

    def _maybe_transition_to_half_open(self) -> None:
        """Auto-promote from OPEN → HALF_OPEN after the recovery timeout."""
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and (time.time() - self._opened_at) >= self.recovery_timeout
        ):
            self._transition(CircuitState.HALF_OPEN)

    def _record_state_change(self, old: CircuitState, new: CircuitState) -> None:
        self._last_state_change = (
            f"{old.value}→{new.value} @ {datetime.utcnow().isoformat()}"
        )
