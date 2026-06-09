#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Telemetry Platform Triple-Header Stress Test
=======================================
Developed for the 2026 Telemetry Platform Initiative.

Simulates the most punishing load profile in the F1 calendar: three
consecutive race weekends (e.g. Spielberg → Silverstone → Budapest)
with randomised sensor failures, schema drift events, connectivity
drops, and bit-flip corruption.

Each race weekend includes:
  FP1 → FP2 → FP3 → Qualifying → Race

The test validates:
  1. Circuit-Breaker trips and recovers correctly.
  2. Edge Buffer sustains zero data loss during connectivity blackouts.
  3. Geo-Fence processes telemetry under the correct jurisdiction.
  4. Latency stays within acceptable percentiles under sustained load.

Usage
-----
    PYTHONPATH="." python tools/telemetry_stress_test.py
    PYTHONPATH="." python tools/telemetry_stress_test.py --packets 5000 --chaos 0.20

Author: Tarek Clarke (PhD Candidate — TalTech)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import random
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn  # noqa: E402
from rich import box  # noqa: E402

from src.circuit_breaker import (  # noqa: E402
    TelemetryCircuitBreaker,
    TelemetryPacket,
    CircuitState,
)
from src.local_persistence import TracksideEdgeBuffer, BufferedPacket  # noqa: E402
from src.geo_fence import GeoFence  # noqa: E402
from src.audit_log import ComplianceAuditLog  # noqa: E402
from src.llm_chaos import LLMChaosPlan, LLMChaosPlanner  # noqa: E402
from src.middleware.tracing import RequestContext  # noqa: E402
from src.slo import SLOTracker  # noqa: E402


console = Console()


def _sanitize_suffix_token(raw: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "", raw or "")
    return token[:40]


def _detect_cpu_suffix() -> str:
    env_override = os.environ.get("RAP_OUTPUT_SUFFIX", "").strip()
    if env_override:
        return _sanitize_suffix_token(env_override)

    brand = ""

    if platform.system() == "Darwin":
        try:
            brand = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            m = re.search(r"Apple\s+(M\d+)", brand, flags=re.IGNORECASE)
            if m:
                return m.group(1).upper()
        except Exception:
            pass
    elif platform.system() == "Windows":
        try:
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "name"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            lines = [l.strip() for l in out.splitlines()
                     if l.strip() and l.strip().lower() != "name"]
            brand = lines[0] if lines else ""
        except Exception:
            pass
    else:  # Linux / other
        try:
            with open("/proc/cpuinfo") as _f:
                for _line in _f:
                    if "model name" in _line.lower():
                        brand = _line.split(":", 1)[1].strip()
                        break
        except Exception:
            brand = platform.processor()

    if brand:
        # Intel Core: i3/i5/i7/i9-XXXXX[suffix]  e.g. i5-12600K → i512600K
        m = re.search(r"(i[3579]-\d{4,5}[A-Z]*)", brand, re.IGNORECASE)
        if m:
            return _sanitize_suffix_token(m.group(1))
        # AMD Ryzen: e.g. Ryzen 9 5900X → 5900X
        m = re.search(r"Ryzen\s+\d+\s+(\d{4,5}[A-Z0-9]*)", brand, re.IGNORECASE)
        if m:
            return _sanitize_suffix_token(m.group(1))
        # Generic: first 4-5 digit model number with optional letter suffix e.g. 12600K
        m = re.search(r"\b(\d{4,5}[A-Z]+)\b", brand)
        if m:
            return m.group(1)
        return _sanitize_suffix_token(brand)

    cpu = platform.processor() or platform.machine() or "CPU"
    return _sanitize_suffix_token(cpu.upper()) or "CPU"


def _resolve_hardware_output_dir(base_dir: str | Path, hardware_suffix: str) -> Path:
    hardware_dir = _sanitize_suffix_token(hardware_suffix) or "CPU"
    return Path(base_dir) / hardware_dir


def _increment_output_path_if_needed(output_path: Path) -> Path:
    """Append _Run2, _Run3, etc. if a report already exists."""
    if not output_path.exists():
        return output_path

    stem = output_path.stem
    suffix = output_path.suffix
    run_idx = 2
    while True:
        candidate = output_path.with_name(f"{stem}_Run{run_idx}{suffix}")
        if not candidate.exists():
            return candidate
        run_idx += 1


# ---------------------------------------------------------------------------
# Triple-Header Configuration
# ---------------------------------------------------------------------------
@dataclass
class RaceWeekend:
    """Configuration for a single race weekend."""
    round_number: int
    circuit: str
    country: str
    sessions: List[str] = field(default_factory=lambda: ["FP1", "FP2", "FP3", "QUALI", "RACE"])


TRIPLE_HEADER: List[RaceWeekend] = [
    RaceWeekend(round_number=10, circuit="spielberg", country="Austria"),
    RaceWeekend(round_number=11, circuit="silverstone", country="United Kingdom"),
    RaceWeekend(round_number=12, circuit="budapest", country="Hungary"),
]

# Sensor channels simulated
SENSORS = [
    ("speed", 80.0, 360.0),
    ("rpm", 4000.0, 15500.0),
    ("throttle", 0.0, 100.0),
    ("brake_temp", 100.0, 1100.0),
    ("engine_temp", 70.0, 130.0),
    ("aero_load", 150.0, 2800.0),
    ("tyre_pressure", 19.0, 28.0),
    ("ecu_canbus", 0.0, 65535.0),
    ("heart_rate", 55.0, 200.0),
    ("g_force_lateral", -6.0, 6.0),
]

# Chaos injection catalogue
CHAOS_MODES = [
    "null_value",
    "string_in_numeric",
    "bit_flip_high",
    "bit_flip_low",
    "schema_drift",
    "duplicate_timestamp",
    "sensor_dropout",
]


# ---------------------------------------------------------------------------
# Chaos Injector
# ---------------------------------------------------------------------------
class ChaosInjector:
    """Generates realistic sensor corruption events."""

    def __init__(
        self,
        chaos_rate: float = 0.12,
        strategy: str = "random",
        llm_model: str = "gemma-4-e4b-it",
        llm_endpoint: str = "http://localhost:11434/api/generate",
        llm_timeout_ms: int = 8000,
        llm_temperature: float = 0.7,
    ):
        self.chaos_rate = chaos_rate
        self.strategy = strategy if strategy in {"random", "llm"} else "random"
        self.events_injected: Dict[str, int] = defaultdict(int)
        self.plan = LLMChaosPlan(mode_weights={m: 1.0 / len(CHAOS_MODES) for m in CHAOS_MODES})

        if self.strategy == "llm":
            planner = LLMChaosPlanner(
                model=llm_model,
                endpoint=llm_endpoint,
                timeout_ms=llm_timeout_ms,
                temperature=llm_temperature,
            )
            self.plan = planner.build_plan(
                profile="balanced",
                modes=CHAOS_MODES,
                sensors=[s[0] for s in SENSORS],
            )

    def maybe_corrupt(
        self, sensor: str, value: float
    ) -> Tuple[str, Any, Optional[str]]:
        """
        Returns (sensor_name, value, chaos_type_or_None).
        """
        if random.random() > self.chaos_rate:
            return sensor, value, None

        mode = random.choices(
            CHAOS_MODES,
            weights=[self.plan.mode_weights.get(m, 0.0) for m in CHAOS_MODES],
            k=1,
        )[0]
        self.events_injected[mode] += 1

        if mode == "null_value":
            return sensor, None, mode
        elif mode == "string_in_numeric":
            tokens = self.plan.string_tokens or ["OVERHEAT", "ERR_DECODE", "NaN", "---"]
            return sensor, random.choice(tokens), mode
        elif mode == "bit_flip_high":
            lo, hi = self.plan.high_flip_range
            return sensor, value * random.uniform(lo, hi), mode
        elif mode == "bit_flip_low":
            lo, hi = self.plan.low_flip_range
            return sensor, -abs(value) * random.uniform(lo, hi), mode
        elif mode == "schema_drift":
            # Rename the sensor to simulate firmware change
            suffixes = self.plan.schema_suffixes or ["_v2", "_new", "_alt", "_canbus", "_raw"]
            drifted = sensor + random.choice(suffixes)
            return drifted, value, mode
        elif mode == "duplicate_timestamp":
            return sensor, value, mode  # handled at packet level
        elif mode == "sensor_dropout":
            return sensor, None, mode
        else:
            return sensor, value, None


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass
class SessionResult:
    session_name: str
    circuit: str
    packets_sent: int = 0
    packets_accepted: int = 0
    packets_rejected: int = 0
    chaos_injected: int = 0
    breaker_trips: int = 0
    breaker_final_state: str = "CLOSED"
    dlq_depth: int = 0
    buffer_pending: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    geo_scrubbed: int = 0
    duration_s: float = 0.0


@dataclass
class DetectionEvent:
    """Timing record for a single anomaly detection."""
    packet_id: str = ""
    session: str = ""
    sensor: str = ""
    chaos_type: str = ""
    detection_latency_ms: float = 0.0  # Time to detect (reject) the packet
    detected: bool = True


@dataclass
class RepairEvent:
    """Timing record for a single DLQ repair attempt."""
    packet_id: str = ""
    repair_latency_ms: float = 0.0
    recovered: bool = False


@dataclass
class ResilienceTimingSummary:
    """Aggregate timing metrics with confidence intervals."""
    # Detection
    detection_count: int = 0
    detection_mean_ms: float = 0.0
    detection_std_ms: float = 0.0
    detection_p50_ms: float = 0.0
    detection_p95_ms: float = 0.0
    detection_p99_ms: float = 0.0
    detection_min_ms: float = 0.0
    detection_max_ms: float = 0.0
    detection_ci95_lower_ms: float = 0.0
    detection_ci95_upper_ms: float = 0.0
    detection_rate: float = 0.0
    # Repair
    repair_count: int = 0
    repair_recovered: int = 0
    repair_mean_ms: float = 0.0
    repair_std_ms: float = 0.0
    repair_p50_ms: float = 0.0
    repair_p95_ms: float = 0.0
    repair_min_ms: float = 0.0
    repair_max_ms: float = 0.0
    repair_ci95_lower_ms: float = 0.0
    repair_ci95_upper_ms: float = 0.0
    repair_rate: float = 0.0
    # Confidence
    confidence_level: float = 0.95
    sample_size: int = 0
    verdict: str = ""


@dataclass
class StressTestReport:
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: str = ""
    total_packets: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    total_chaos: int = 0
    total_breaker_trips: int = 0
    total_dlq: int = 0
    overall_acceptance_rate: float = 0.0
    overall_latency_p95: float = 0.0
    resilience_score: float = 0.0
    sessions: List[SessionResult] = field(default_factory=list)
    chaos_breakdown: Dict[str, int] = field(default_factory=dict)
    verdict: str = "PENDING"


# ---------------------------------------------------------------------------
# Stress Test Runner
# ---------------------------------------------------------------------------
class TelemetryStressTest:
    """
    Triple-header stress test that exercises every layer of the
    Telemetry Platform telemetry spine.
    """

    def __init__(
        self,
        packets_per_session: int = 1000,
        chaos_rate: float = 0.12,
        chaos_strategy: str = "random",
        llm_model: str = "gemma-4-e4b-it",
        llm_endpoint: str = "http://localhost:11434/api/generate",
        llm_timeout_ms: int = 1200,
        llm_temperature: float = 0.7,
        breaker_threshold: int = 5,
        breaker_recovery: float = 2.0,
        output_dir: str = "data/reports",
        output_suffix: str = "",
    ):
        self.packets_per_session = packets_per_session
        self.chaos = ChaosInjector(
            chaos_rate,
            strategy=chaos_strategy,
            llm_model=llm_model,
            llm_endpoint=llm_endpoint,
            llm_timeout_ms=llm_timeout_ms,
            llm_temperature=llm_temperature,
        )
        auto_suffix = _detect_cpu_suffix()
        self.hardware_suffix = auto_suffix
        chosen = (output_suffix.strip() or auto_suffix).lstrip("_")
        self.output_suffix = f"_{chosen}" if chosen else ""
        self.output_dir = _resolve_hardware_output_dir(output_dir, self.hardware_suffix)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Subsystems
        self.breaker = TelemetryCircuitBreaker(
            failure_threshold=breaker_threshold,
            recovery_timeout=breaker_recovery,
            dlq_path="data/stress_dlq.sqlite",
        )
        self.buffer = TracksideEdgeBuffer(
            db_path="data/stress_edge_buffer.sqlite",
            sync_callback=self._mock_cloud_sync,
        )
        self.audit = ComplianceAuditLog(db_path="data/stress_audit.sqlite")
        self.geo = GeoFence(audit_log=self.audit)

        self.report = StressTestReport()
        self._latencies: List[float] = []
        self._breaker_trip_count = 0
        self._drain_results: List[Dict[str, Any]] = []

        # Resilience timing instrumentation
        self._detection_events: List[DetectionEvent] = []
        self._repair_events: List[RepairEvent] = []
        self.timing_summary: Optional[ResilienceTimingSummary] = None

    @staticmethod
    def _mock_cloud_sync(payloads: list) -> bool:
        """Simulated cloud sink. Succeeds 95% of the time for realism."""
        return random.random() < 0.95

    # -----------------------------------------------------------------
    def run(self) -> StressTestReport:
        """Execute the full Triple-Header stress test."""
        console.print(Panel(
            "[bold bright_white]TELEMETRY PLATFORM — TRIPLE-HEADER STRESS TEST[/bold bright_white]\n"
            "[dim]Simulating 3 consecutive race weekends with randomised chaos injection[/dim]",
            style="on dark_red",
            box=box.DOUBLE_EDGE,
        ))
        console.print(
            f"[dim]Chaos strategy: {self.chaos.strategy} | plan={self.chaos.plan.source}[/dim]"
        )
        console.print()

        total_sessions = sum(len(rw.sessions) for rw in TRIPLE_HEADER)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            overall_task = progress.add_task("Overall", total=total_sessions)

            for weekend in TRIPLE_HEADER:
                console.print(f"\n[bold cyan]🏁 Round {weekend.round_number} — "
                              f"{weekend.circuit.title()} ({weekend.country})[/bold cyan]")

                for session_name in weekend.sessions:
                    result = self._run_session(weekend, session_name, progress)
                    self.report.sessions.append(result)
                    progress.advance(overall_task)

                # Reset breaker between weekends (simulates pit-wall restart)
                self.breaker.reset()

        self._finalise_report()
        self._print_report()
        self._evaluate_slos()
        self._export_results()

        # Cleanup (audit closed last to allow post-run queries)
        self.breaker.dlq.close()
        self.buffer.close()
        # Note: self.audit is NOT closed here to allow post-run queries.
        # The caller is responsible for calling self.audit.close().

        return self.report

    # -----------------------------------------------------------------
    def _run_session(
        self, weekend: RaceWeekend, session_name: str, progress
    ) -> SessionResult:
        """Simulate a single session (e.g. FP1 at Silverstone)."""
        label = f"  {weekend.circuit.title()} {session_name}"
        task = progress.add_task(label, total=self.packets_per_session)

        result = SessionResult(
            session_name=f"{weekend.circuit}_{session_name}",
            circuit=weekend.circuit,
        )

        session_latencies: List[float] = []
        prev_state = self.breaker.state

        for i in range(self.packets_per_session):
            sensor_name, lo, hi = random.choice(SENSORS)
            base_value = round(random.uniform(lo, hi), 2)

            # Apply chaos
            sensor_out, value_out, chaos_type = self.chaos.maybe_corrupt(sensor_name, base_value)
            if chaos_type:
                result.chaos_injected += 1

            # Create packet with request-ID for end-to-end tracing
            ctx = RequestContext.new(
                session_id=result.session_name,
                source="stress_test",
            )
            pkt = TelemetryPacket(
                sensor=sensor_out,
                value=value_out,
                request_id=ctx.request_id,
            )

            # Circuit Breaker — measure validation separately from DLQ I/O
            t_val = time.monotonic()
            _is_valid, _val_reason = self.breaker.validator.validate_packet(pkt)
            detection_latency_ms = (time.monotonic() - t_val) * 1000

            t0 = time.monotonic()
            accepted, reason = self.breaker.process(pkt)
            latency_ms = (time.monotonic() - t0) * 1000
            session_latencies.append(latency_ms)
            self._latencies.append(latency_ms)

            ctx.add_stage("circuit_breaker", status="PASSED" if accepted else "REJECTED")

            # Track detection timing for chaos-injected packets
            if chaos_type:
                self._detection_events.append(DetectionEvent(
                    packet_id=pkt.packet_id,
                    session=result.session_name,
                    sensor=sensor_out,
                    chaos_type=chaos_type,
                    detection_latency_ms=detection_latency_ms,
                    detected=not accepted,
                ))

            result.packets_sent += 1
            if accepted:
                result.packets_accepted += 1
                # Write to edge buffer
                bp = BufferedPacket(
                    packet_id=pkt.packet_id,
                    session_id=result.session_name,
                    sensor=sensor_out,
                    value=value_out,
                )
                self.buffer.write(bp)
                ctx.add_stage("edge_buffer", status="BUFFERED")
            else:
                result.packets_rejected += 1

            # Detect breaker trips
            cur_state = self.breaker.state
            if prev_state != CircuitState.OPEN and cur_state == CircuitState.OPEN:
                result.breaker_trips += 1
                self._breaker_trip_count += 1
            prev_state = cur_state

            # Geo-fence every 50th packet (with request-ID propagation)
            if i % 50 == 0:
                payload = {"sensor": sensor_out, "value": value_out, "heart_rate": 155}
                gf_result = self.geo.process(
                    weekend.circuit, payload,
                    session_id=result.session_name,
                    request_id=ctx.request_id,
                )
                result.geo_scrubbed += len(gf_result.fields_scrubbed)
                ctx.add_stage("geo_fence", status="PROCESSED")

            # Drain buffer every 200 packets to exercise exactly-once semantics
            if i > 0 and i % 200 == 0:
                drain = self.buffer.drain_pending()
                self._drain_results.append(drain)

            progress.advance(task)

        # Session summary
        result.breaker_final_state = self.breaker.state.value
        result.dlq_depth = self.breaker.dlq.depth()
        result.buffer_pending = self.buffer.health.pending_sync

        if session_latencies:
            sl = sorted(session_latencies)
            result.latency_p50_ms = round(sl[len(sl) // 2], 3)
            result.latency_p95_ms = round(sl[int(len(sl) * 0.95)], 3)
            result.latency_p99_ms = round(sl[int(len(sl) * 0.99)], 3)

        return result

    # -----------------------------------------------------------------
    # Schema-drift recovery: strip known firmware-version suffixes
    # so packets with a drifted sensor name can be re-validated against
    # the canonical sensor definition.
    _SCHEMA_DRIFT_SUFFIXES = (
        "_v2", "_v3", "_new", "_alt", "_canbus", "_raw", "_temp",
    )

    def _normalize_sensor(self, sensor: str) -> str:
        """Strip known schema-drift suffixes to recover the canonical name."""
        for suffix in self._SCHEMA_DRIFT_SUFFIXES:
            if sensor.endswith(suffix):
                return sensor[: -len(suffix)]
        return sensor

    # -----------------------------------------------------------------
    def _finalise_report(self) -> None:
        # Run DLQ reprocessing pass with per-packet repair timing.
        # Strategy:
        #   1. Try direct re-validation (unchanged data may now be valid
        #      if validator ranges were updated).
        #   2. For schema_drift failures, normalize the sensor name and retry.
        candidates = self.breaker.dlq.fetch_reprocessable(limit=200)
        repaired = 0
        still_bad = 0
        max_retries = 0

        for rec in candidates:
            raw_sensor = rec["sensor"] or ""
            raw_value = (
                json.loads(rec["value"])
                if isinstance(rec["value"], str)
                else rec["value"]
            )
            raw_meta = (
                json.loads(rec["metadata"])
                if isinstance(rec["metadata"], str)
                else (rec["metadata"] or {})
            )

            # --- Pass 1: direct re-validation ---
            pkt = TelemetryPacket(
                packet_id=rec["packet_id"],
                timestamp=rec["timestamp"],
                sensor=raw_sensor,
                value=raw_value,
                metadata=raw_meta,
            )
            t0 = time.monotonic()
            is_valid, reason = self.breaker.validator.validate_packet(pkt)

            # --- Pass 2: schema-drift normalization ---
            if not is_valid and "schema_drift" in rec.get("reason", ""):
                normalized = self._normalize_sensor(raw_sensor)
                if normalized != raw_sensor:
                    pkt_norm = TelemetryPacket(
                        packet_id=rec["packet_id"],
                        timestamp=rec["timestamp"],
                        sensor=normalized,
                        value=raw_value,
                        metadata=raw_meta,
                    )
                    is_valid, reason = self.breaker.validator.validate_packet(pkt_norm)

            repair_ms = (time.monotonic() - t0) * 1000

            if is_valid:
                self.breaker.dlq.mark_reprocessed(rec["packet_id"])
                repaired += 1
                self._repair_events.append(RepairEvent(
                    packet_id=rec["packet_id"],
                    repair_latency_ms=repair_ms,
                    recovered=True,
                ))
            else:
                self.breaker.dlq.increment_retry(rec["packet_id"])
                retry_count = rec.get("retry_count", 0) + 1
                if retry_count >= 3:
                    max_retries += 1
                else:
                    still_bad += 1
                self._repair_events.append(RepairEvent(
                    packet_id=rec["packet_id"],
                    repair_latency_ms=repair_ms,
                    recovered=False,
                ))

        self._dlq_reprocess_result = {
            "recovered": repaired,
            "still_invalid": still_bad,
            "max_retries": max_retries,
        }

        # Final drain pass
        final_drain = self.buffer.drain_pending()
        self._drain_results.append(final_drain)

        self.report.ended_at = datetime.utcnow().isoformat()
        self.report.total_packets = sum(s.packets_sent for s in self.report.sessions)
        self.report.total_accepted = sum(s.packets_accepted for s in self.report.sessions)
        self.report.total_rejected = sum(s.packets_rejected for s in self.report.sessions)
        self.report.total_chaos = sum(s.chaos_injected for s in self.report.sessions)
        self.report.total_breaker_trips = self._breaker_trip_count
        self.report.total_dlq = self.breaker.dlq.depth()
        self.report.chaos_breakdown = dict(self.chaos.events_injected)

        total = self.report.total_packets
        if total > 0:
            self.report.overall_acceptance_rate = round(
                self.report.total_accepted / total, 4
            )

        if self._latencies:
            sl = sorted(self._latencies)
            self.report.overall_latency_p95 = round(sl[int(len(sl) * 0.95)], 3)

        # Resilience Score: weighted composite
        #   35% clean-data throughput  +  25% corruption detection
        #   20% breaker recovery        +  20% latency health
        #
        # The key insight: rejecting corrupted packets IS correct behaviour.
        # We measure (a) how many clean packets got through, and (b) how
        # effectively the system caught the injected chaos.

        clean_packets = max(1, total - self.report.total_chaos)
        clean_throughput = min(1.0, self.report.total_accepted / clean_packets)

        # Corruption detection: what fraction of chaos was correctly rejected?
        if self.report.total_chaos > 0:
            detection_rate = min(1.0, self.report.total_rejected / self.report.total_chaos)
        else:
            detection_rate = 1.0

        recovery_score = 1.0 if self._breaker_trip_count == 0 else max(
            0, 1.0 - (self._breaker_trip_count / (len(self.report.sessions) * 2))
        )

        # 100ms p95 is the real-world target for trackside telemetry
        latency_score = max(0, 1.0 - (self.report.overall_latency_p95 / 100.0))

        self.report.resilience_score = round(
            0.35 * clean_throughput
            + 0.25 * detection_rate
            + 0.20 * recovery_score
            + 0.20 * latency_score, 4
        )

        if self.report.resilience_score >= 0.85:
            self.report.verdict = "RACE-READY ✅"
        elif self.report.resilience_score >= 0.70:
            self.report.verdict = "CONDITIONAL — Review Required ⚠️"
        else:
            self.report.verdict = "NOT READY — Engineering Review ❌"

        # Build resilience timing summary
        self.timing_summary = self._build_timing_summary()

    # -----------------------------------------------------------------
    def _build_timing_summary(self) -> ResilienceTimingSummary:
        """Compute detection/repair timing statistics with 95% confidence intervals."""
        summary = ResilienceTimingSummary()

        # --- Detection stats ---
        det = self._detection_events
        summary.detection_count = len(det)
        detected = [e for e in det if e.detected]
        summary.detection_rate = len(detected) / max(1, len(det))

        if detected:
            lats = [e.detection_latency_ms for e in detected]
            sl = sorted(lats)
            n = len(sl)
            summary.detection_mean_ms = round(statistics.mean(sl), 4)
            summary.detection_std_ms = round(statistics.stdev(sl), 4) if n > 1 else 0.0
            summary.detection_p50_ms = round(sl[n // 2], 4)
            summary.detection_p95_ms = round(sl[int(n * 0.95)], 4)
            summary.detection_p99_ms = round(sl[int(n * 0.99)], 4)
            summary.detection_min_ms = round(sl[0], 4)
            summary.detection_max_ms = round(sl[-1], 4)
            # 95% CI for the mean: mean ± 1.96 * (std / sqrt(n))
            if n > 1:
                margin = 1.96 * (summary.detection_std_ms / math.sqrt(n))
                summary.detection_ci95_lower_ms = round(summary.detection_mean_ms - margin, 4)
                summary.detection_ci95_upper_ms = round(summary.detection_mean_ms + margin, 4)

        # --- Repair stats ---
        rep = self._repair_events
        summary.repair_count = len(rep)
        summary.repair_recovered = sum(1 for e in rep if e.recovered)
        summary.repair_rate = summary.repair_recovered / max(1, len(rep))

        if rep:
            rlats = [e.repair_latency_ms for e in rep]
            sr = sorted(rlats)
            m = len(sr)
            summary.repair_mean_ms = round(statistics.mean(sr), 4)
            summary.repair_std_ms = round(statistics.stdev(sr), 4) if m > 1 else 0.0
            summary.repair_p50_ms = round(sr[m // 2], 4)
            summary.repair_p95_ms = round(sr[int(m * 0.95)], 4)
            summary.repair_min_ms = round(sr[0], 4)
            summary.repair_max_ms = round(sr[-1], 4)
            if m > 1:
                margin = 1.96 * (summary.repair_std_ms / math.sqrt(m))
                summary.repair_ci95_lower_ms = round(summary.repair_mean_ms - margin, 4)
                summary.repair_ci95_upper_ms = round(summary.repair_mean_ms + margin, 4)

        summary.confidence_level = 0.95
        summary.sample_size = summary.detection_count + summary.repair_count

        # Timing verdict
        if summary.detection_count > 0 and summary.detection_p95_ms < 1.0:
            summary.verdict = "SUB-MILLISECOND DETECTION ✅"
        elif summary.detection_count > 0 and summary.detection_p95_ms < 5.0:
            summary.verdict = "FAST DETECTION (<5ms) ✅"
        elif summary.detection_count > 0 and summary.detection_p95_ms < 50.0:
            summary.verdict = "ACCEPTABLE DETECTION (<50ms) ⚠️"
        else:
            summary.verdict = "SLOW DETECTION — REVIEW REQUIRED ❌"

        return summary

    # -----------------------------------------------------------------
    def _print_report(self) -> None:
        console.print("\n")

        # --- Session Detail Table ---
        table = Table(
            title="Triple-Header Session Results",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("Session", style="bold cyan")
        table.add_column("Sent", justify="right")
        table.add_column("Accepted", justify="right", style="green")
        table.add_column("Rejected", justify="right", style="red")
        table.add_column("Chaos", justify="right", style="yellow")
        table.add_column("CB Trips", justify="right")
        table.add_column("CB State")
        table.add_column("DLQ", justify="right")
        table.add_column("p95 (ms)", justify="right")

        for s in self.report.sessions:
            state_style = {
                "CLOSED": "[green]CLOSED[/green]",
                "OPEN": "[red]OPEN[/red]",
                "HALF_OPEN": "[yellow]HALF_OPEN[/yellow]",
            }.get(s.breaker_final_state, s.breaker_final_state)

            table.add_row(
                s.session_name,
                str(s.packets_sent),
                str(s.packets_accepted),
                str(s.packets_rejected),
                str(s.chaos_injected),
                str(s.breaker_trips),
                state_style,
                str(s.dlq_depth),
                f"{s.latency_p95_ms:.2f}",
            )

        console.print(table)

        # --- Chaos Breakdown ---
        chaos_table = Table(title="Chaos Injection Breakdown", box=box.SIMPLE)
        chaos_table.add_column("Chaos Mode", style="bold")
        chaos_table.add_column("Count", justify="right")
        for mode, count in sorted(self.report.chaos_breakdown.items(), key=lambda x: -x[1]):
            chaos_table.add_row(mode, str(count))
        console.print(chaos_table)

        # --- Verdict ---
        verdict_style = (
            "bold green" if "✅" in self.report.verdict
            else ("bold yellow" if "⚠️" in self.report.verdict else "bold red")
        )

        clean_pkt = max(1, self.report.total_packets - self.report.total_chaos)
        clean_thru = min(1.0, self.report.total_accepted / clean_pkt)
        det_rate = (
            min(1.0, self.report.total_rejected / self.report.total_chaos)
            if self.report.total_chaos > 0 else 1.0
        )

        console.print(Panel(
            f"[bold]Resilience Score:[/bold]         {self.report.resilience_score:.2%}\n"
            f"[bold]Clean-Data Throughput:[/bold]    {clean_thru:.2%}\n"
            f"[bold]Corruption Detection:[/bold]     {det_rate:.2%}\n"
            f"[bold]Breaker Trips:[/bold]            {self.report.total_breaker_trips}\n"
            f"[bold]DLQ Quarantined:[/bold]          {self.report.total_dlq}\n"
            f"[bold]DLQ Reprocessed:[/bold]          {self._dlq_reprocess_result.get('recovered', 0)} recovered\n"
            f"[bold]Drain Batches:[/bold]            {len(self._drain_results)} cycles\n"
            f"[bold]Audit Log Entries:[/bold]        {self.audit.count()}\n"
            f"[bold]Audit Chain Intact:[/bold]       {self.audit.verify_chain()}\n"
            f"[bold]p95 Latency:[/bold]              {self.report.overall_latency_p95:.2f} ms\n\n"
            f"[{verdict_style}]VERDICT: {self.report.verdict}[/{verdict_style}]",
            title="[bold bright_white on dark_red]  FINAL ASSESSMENT  [/bold bright_white on dark_red]",
            border_style="bright_white",
        ))

        # --- Resilience Timing Report ---
        if self.timing_summary:
            ts = self.timing_summary
            timing_verdict_style = (
                "bold green" if "✅" in ts.verdict
                else ("bold yellow" if "⚠️" in ts.verdict else "bold red")
            )

            timing_table = Table(
                title="Resilience Timing Report",
                box=box.DOUBLE_EDGE,
                show_lines=True,
            )
            timing_table.add_column("Metric", style="bold cyan", width=30)
            timing_table.add_column("Detection", justify="right", style="green", width=20)
            timing_table.add_column("Repair", justify="right", style="yellow", width=20)

            timing_table.add_row("Events", str(ts.detection_count), str(ts.repair_count))
            timing_table.add_row("Success Rate", f"{ts.detection_rate:.2%}", f"{ts.repair_rate:.2%}")
            timing_table.add_row("Mean Latency", f"{ts.detection_mean_ms:.4f} ms", f"{ts.repair_mean_ms:.4f} ms")
            timing_table.add_row("Std Deviation", f"{ts.detection_std_ms:.4f} ms", f"{ts.repair_std_ms:.4f} ms")
            timing_table.add_row("Min", f"{ts.detection_min_ms:.4f} ms", f"{ts.repair_min_ms:.4f} ms")
            timing_table.add_row("p50 (Median)", f"{ts.detection_p50_ms:.4f} ms", f"{ts.repair_p50_ms:.4f} ms")
            timing_table.add_row("p95", f"{ts.detection_p95_ms:.4f} ms", f"{ts.repair_p95_ms:.4f} ms")
            timing_table.add_row("p99", f"{ts.detection_p99_ms:.4f} ms", "—")
            timing_table.add_row("Max", f"{ts.detection_max_ms:.4f} ms", f"{ts.repair_max_ms:.4f} ms")
            timing_table.add_row(
                "95% CI (Mean)",
                f"[{ts.detection_ci95_lower_ms:.4f}, {ts.detection_ci95_upper_ms:.4f}] ms",
                f"[{ts.repair_ci95_lower_ms:.4f}, {ts.repair_ci95_upper_ms:.4f}] ms",
            )

            console.print(timing_table)

            console.print(Panel(
                f"[bold]Anomalies Injected:[/bold]      {ts.detection_count}\n"
                f"[bold]Anomalies Caught:[/bold]        {sum(1 for e in self._detection_events if e.detected)}\n"
                f"[bold]Detection Rate:[/bold]          {ts.detection_rate:.2%}\n"
                f"[bold]Mean Detection Speed:[/bold]    {ts.detection_mean_ms:.4f} ms\n"
                f"[bold]p95 Detection Speed:[/bold]     {ts.detection_p95_ms:.4f} ms\n"
                f"[bold]95% CI (Detection):[/bold]      "
                f"[{ts.detection_ci95_lower_ms:.4f}, {ts.detection_ci95_upper_ms:.4f}] ms\n"
                f"[bold]DLQ Repairs Attempted:[/bold]   {ts.repair_count}\n"
                f"[bold]DLQ Repairs Recovered:[/bold]   {ts.repair_recovered}\n"
                f"[bold]Repair Rate:[/bold]             {ts.repair_rate:.2%}\n"
                f"[bold]Mean Repair Speed:[/bold]       {ts.repair_mean_ms:.4f} ms\n"
                f"[bold]Confidence Level:[/bold]        {ts.confidence_level:.0%}\n"
                f"[bold]Sample Size:[/bold]             {ts.sample_size}\n\n"
                f"[{timing_verdict_style}]TIMING VERDICT: {ts.verdict}[/{timing_verdict_style}]",
                title="[bold bright_white on blue]  RESILIENCE TIMING ASSESSMENT  [/bold bright_white on blue]",
                border_style="bright_cyan",
            ))

    # -----------------------------------------------------------------
    def _evaluate_slos(self) -> None:
        """Evaluate all SLO budgets and print a compliance report."""
        report = self.report

        # Detection rate: fraction of injected chaos packets that were rejected
        if report.total_chaos > 0:
            detection_rate = min(1.0, report.total_rejected / report.total_chaos)
        else:
            detection_rate = 1.0

        # Audit chain integrity
        try:
            audit_intact = self.audit.verify_chain()
        except Exception:
            audit_intact = False

        total_sessions = len(report.sessions)

        tracker = SLOTracker()
        slo_report = tracker.evaluate(
            latency_p95_ms=report.overall_latency_p95,
            acceptance_rate=report.overall_acceptance_rate,
            dlq_depth=report.total_dlq,
            audit_intact=audit_intact,
            detection_rate=detection_rate,
            breaker_trips=report.total_breaker_trips,
            num_sessions=total_sessions,
            packets_per_session=self.packets_per_session,
        )
        tracker.print_report(slo_report)

    # -----------------------------------------------------------------
    def _export_results(self) -> None:
        """Write results to CSV and JSON for downstream consumption."""
        # --- CSV ---
        csv_path = _increment_output_path_if_needed(
            self.output_dir / f"telemetry_stress_test_results{self.output_suffix}.csv"
        )
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "session_name", "circuit", "packets_sent", "packets_accepted",
                "packets_rejected", "chaos_injected", "breaker_trips",
                "breaker_final_state", "dlq_depth", "buffer_pending",
                "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
                "geo_scrubbed", "duration_s",
            ])
            writer.writeheader()
            for s in self.report.sessions:
                writer.writerow(asdict(s))
        console.print(f"\n[dim]CSV exported → {csv_path}[/dim]")

        # --- JSON ---
        json_path = _increment_output_path_if_needed(
            self.output_dir / f"telemetry_stress_test_report{self.output_suffix}.json"
        )
        with open(json_path, "w") as f:
            json.dump(asdict(self.report), f, indent=2, default=str)
        console.print(f"[dim]JSON exported → {json_path}[/dim]")

        # --- Resilience Timing CSV ---
        timing_csv_path = _increment_output_path_if_needed(
            self.output_dir / f"resilience_timing_report{self.output_suffix}.csv"
        )
        with open(timing_csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "packet_id", "session", "sensor", "chaos_type",
                "event_type", "latency_ms", "detected_or_recovered",
            ])
            writer.writeheader()
            for ev in self._detection_events:
                writer.writerow({
                    "packet_id": ev.packet_id,
                    "session": ev.session,
                    "sensor": ev.sensor,
                    "chaos_type": ev.chaos_type,
                    "event_type": "detection",
                    "latency_ms": round(ev.detection_latency_ms, 4),
                    "detected_or_recovered": ev.detected,
                })
            for ev in self._repair_events:
                writer.writerow({
                    "packet_id": ev.packet_id,
                    "session": "",
                    "sensor": "",
                    "chaos_type": "dlq_repair",
                    "event_type": "repair",
                    "latency_ms": round(ev.repair_latency_ms, 4),
                    "detected_or_recovered": ev.recovered,
                })
        console.print(f"[dim]Timing CSV exported → {timing_csv_path}[/dim]")

        # --- Resilience Timing JSON ---
        if self.timing_summary:
            timing_json_path = _increment_output_path_if_needed(
                self.output_dir / f"resilience_timing_report{self.output_suffix}.json"
            )
            with open(timing_json_path, "w") as f:
                json.dump(asdict(self.timing_summary), f, indent=2, default=str)
            console.print(f"[dim]Timing JSON exported → {timing_json_path}[/dim]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Telemetry Platform Triple-Header Stress Test"
    )
    parser.add_argument(
        "--packets", type=int, default=1000,
        help="Packets per session (default: 1000)"
    )
    parser.add_argument(
        "--chaos", type=float, default=0.12,
        help="Chaos injection rate 0.0–1.0 (default: 0.12)"
    )
    parser.add_argument(
        "--chaos-strategy", type=str, choices=["random", "llm"], default="random",
        help="Chaos mode selection strategy (default: random)",
    )
    parser.add_argument(
        "--llm-model", type=str, default="gemma-4-e4b-it",
        help="Local lightweight model for --chaos-strategy llm (default: gemma-4-e4b-it)",
    )
    parser.add_argument(
        "--llm-endpoint", type=str, default="http://localhost:11434/api/generate",
        help="LLM HTTP endpoint (default: Ollama generate endpoint)",
    )
    parser.add_argument(
        "--llm-timeout-ms", type=int, default=8000,
        help="LLM request timeout in milliseconds (default: 8000)",
    )
    parser.add_argument(
        "--llm-temperature", type=float, default=0.7,
        help="LLM sampling temperature (default: 0.7)",
    )
    parser.add_argument(
        "--threshold", type=int, default=5,
        help="Circuit-breaker failure threshold (default: 5)"
    )
    parser.add_argument(
        "--showcase", action="store_true",
        help="Showcase mode: tuned for live demo (1000 pkt, 10%% chaos, fast)"
    )
    parser.add_argument(
        "--output-suffix", type=str, default="",
        help="Optional output suffix token (e.g. M4, 7900XT); auto-detected if omitted",
    )
    args = parser.parse_args()

    if args.showcase:
        packets = 1000
        chaos = 0.10
        threshold = 5
        console.print("[bold bright_white on dark_red]  SHOWCASE MODE  [/bold bright_white on dark_red]\n")
    else:
        packets = args.packets
        chaos = args.chaos
        threshold = args.threshold

    test = TelemetryStressTest(
        packets_per_session=packets,
        chaos_rate=chaos,
        chaos_strategy=args.chaos_strategy,
        llm_model=args.llm_model,
        llm_endpoint=args.llm_endpoint,
        llm_timeout_ms=args.llm_timeout_ms,
        llm_temperature=args.llm_temperature,
        breaker_threshold=threshold,
        output_suffix=args.output_suffix,
    )
    report = test.run()
    # Allow CI to pass on minor SLO breach
    return 0 if ("✅" in report.verdict or "⚠️" in report.verdict) else 1


if __name__ == "__main__":
    sys.exit(main())
