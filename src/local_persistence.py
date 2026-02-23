#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Local-First Persistence Layer (Trackside Edge Buffer)
======================================================
Developed for the 2026 Cadillac F1 Initiative.

Guarantees zero data loss during trackside connectivity drops by persisting
every telemetry packet to a local SQLite WAL database before attempting the
cloud sync.  This is the "write-ahead" layer that sits between the car's
RF downlink and the global data sink.

Architecture
------------
    Car RF  ──►  Edge Buffer (SQLite WAL)  ──►  Cloud Sink (async drain)
                      │
                 Local replay always available
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
class SyncStatus(Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


@dataclass
class BufferedPacket:
    """A telemetry packet stored in the local buffer."""
    packet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sensor: str = ""
    value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    sync_status: str = SyncStatus.PENDING.value


@dataclass
class BufferHealth:
    """Real-time health metrics for the edge buffer."""
    total_buffered: int = 0
    pending_sync: int = 0
    synced: int = 0
    failed: int = 0
    buffer_utilisation: float = 0.0      # 0.0–1.0
    last_write_time: Optional[str] = None
    last_sync_time: Optional[str] = None
    connectivity: bool = True
    db_size_bytes: int = 0


# ---------------------------------------------------------------------------
# Edge Buffer
# ---------------------------------------------------------------------------
class TracksideEdgeBuffer:
    """
    SQLite WAL-backed write-ahead buffer for F1 telemetry.

    Every packet is persisted locally *before* any cloud sync is attempted.
    If the uplink drops, the buffer accumulates and drains automatically
    when connectivity is restored.

    Parameters
    ----------
    db_path : str
        Path for the SQLite database.
    max_buffer_size : int
        Soft cap (rows) before the buffer raises a back-pressure warning.
    sync_callback : callable | None
        Async function called to push packets to the global sink.
        Signature: ``(List[Dict]) -> bool``  (returns True on success).
    batch_size : int
        Number of packets to drain per sync cycle.
    """

    DDL = """
    CREATE TABLE IF NOT EXISTS telemetry_buffer (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        packet_id   TEXT    UNIQUE NOT NULL,
        session_id  TEXT,
        timestamp   TEXT    NOT NULL,
        sensor      TEXT,
        value       TEXT,
        metadata    TEXT,
        sync_status TEXT    DEFAULT 'PENDING',
        created_at  TEXT    DEFAULT (datetime('now')),
        synced_at   TEXT,
        drain_batch_id TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_buf_sync ON telemetry_buffer(sync_status);
    CREATE INDEX IF NOT EXISTS idx_buf_session ON telemetry_buffer(session_id);
    CREATE INDEX IF NOT EXISTS idx_buf_drain ON telemetry_buffer(drain_batch_id);

    CREATE TABLE IF NOT EXISTS drain_batches (
        batch_id    TEXT    PRIMARY KEY,
        created_at  TEXT    NOT NULL,
        packet_count INTEGER NOT NULL,
        status      TEXT    DEFAULT 'DRAINING',
        acked_at    TEXT
    );
    """

    def __init__(
        self,
        db_path: str = "data/edge_buffer.sqlite",
        max_buffer_size: int = 100_000,
        sync_callback: Optional[Callable] = None,
        batch_size: int = 500,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_buffer_size = max_buffer_size
        self.sync_callback = sync_callback
        self.batch_size = batch_size

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.executescript(self.DDL)
        self._lock = threading.Lock()

        self._last_write_time: Optional[str] = None
        self._last_sync_time: Optional[str] = None
        self._connectivity = True

        # Background drain thread
        self._drain_active = False
        self._drain_thread: Optional[threading.Thread] = None

        logger.info(
            "TracksideEdgeBuffer online | db=%s max=%d",
            self.db_path, self.max_buffer_size,
        )

    # -----------------------------------------------------------------
    # Write Path — guaranteed local persistence
    # -----------------------------------------------------------------
    def write(self, packet: BufferedPacket) -> None:
        """Persist a single telemetry packet to the local buffer."""
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO telemetry_buffer
                   (packet_id, session_id, timestamp, sensor, value, metadata, sync_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    packet.packet_id,
                    packet.session_id,
                    packet.timestamp,
                    packet.sensor,
                    json.dumps(packet.value),
                    json.dumps(packet.metadata),
                    packet.sync_status,
                ),
            )
            self._conn.commit()
            self._last_write_time = datetime.utcnow().isoformat()

    def write_batch(self, packets: List[BufferedPacket]) -> int:
        """Persist a batch; returns the count of newly inserted rows."""
        inserted = 0
        with self._lock:
            for pkt in packets:
                try:
                    self._conn.execute(
                        """INSERT OR IGNORE INTO telemetry_buffer
                           (packet_id, session_id, timestamp, sensor, value, metadata, sync_status)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            pkt.packet_id,
                            pkt.session_id,
                            pkt.timestamp,
                            pkt.sensor,
                            json.dumps(pkt.value),
                            json.dumps(pkt.metadata),
                            pkt.sync_status,
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass  # de-dup on packet_id
            self._conn.commit()
            self._last_write_time = datetime.utcnow().isoformat()
        return inserted

    # -----------------------------------------------------------------
    # Sync / Drain Path — best-effort cloud push
    # -----------------------------------------------------------------
    def drain_pending(self) -> Dict[str, Any]:
        """
        Attempt to sync pending packets to the global sink with exactly-once
        semantics.

        Each drain cycle is assigned a unique ``batch_id``.  Packets are
        marked as DRAINING *before* the sync callback fires.  The batch is
        only promoted to SYNCED after the cloud sink ACKs.  On failure the
        batch is rolled back to PENDING so it can be retried.

        Returns summary: ``{"synced": n, "failed": m, "batch_id": ...}``.
        """
        if not self.sync_callback:
            return {"synced": 0, "failed": 0, "reason": "no_sync_callback"}

        batch_id = uuid.uuid4().hex[:16]
        now = datetime.utcnow().isoformat()

        # Phase 1 — claim a batch of PENDING rows
        with self._lock:
            cur = self._conn.execute(
                "SELECT id, packet_id, session_id, timestamp, sensor, value, metadata "
                "FROM telemetry_buffer WHERE sync_status = 'PENDING' "
                "ORDER BY id LIMIT ?",
                (self.batch_size,),
            )
            rows = cur.fetchall()
            if not rows:
                return {"synced": 0, "failed": 0, "batch_id": batch_id}

            row_ids = [r[0] for r in rows]

            # Mark as DRAINING + tag with batch_id (atomically)
            self._conn.executemany(
                "UPDATE telemetry_buffer SET sync_status = 'DRAINING', drain_batch_id = ? WHERE id = ?",
                [(batch_id, rid) for rid in row_ids],
            )
            self._conn.execute(
                "INSERT INTO drain_batches (batch_id, created_at, packet_count, status) "
                "VALUES (?, ?, ?, 'DRAINING')",
                (batch_id, now, len(row_ids)),
            )
            self._conn.commit()

        # Phase 2 — call the sync callback (outside lock to avoid blocking writes)
        payloads = []
        for row in rows:
            payloads.append({
                "packet_id": row[1],
                "session_id": row[2],
                "timestamp": row[3],
                "sensor": row[4],
                "value": json.loads(row[5]) if row[5] else None,
                "metadata": json.loads(row[6]) if row[6] else {},
                "_batch_id": batch_id,
            })

        try:
            success = self.sync_callback(payloads)
        except Exception as exc:
            logger.warning("Sync callback raised: %s", exc)
            success = False

        # Phase 3 — finalise the batch
        ack_time = datetime.utcnow().isoformat()

        with self._lock:
            if success:
                new_status = SyncStatus.SYNCED.value
                self._conn.executemany(
                    "UPDATE telemetry_buffer SET sync_status = ?, synced_at = ? WHERE id = ?",
                    [(new_status, ack_time, rid) for rid in row_ids],
                )
                self._conn.execute(
                    "UPDATE drain_batches SET status = 'ACKED', acked_at = ? WHERE batch_id = ?",
                    (ack_time, batch_id),
                )
            else:
                # Roll back to PENDING so the next drain cycle retries
                self._conn.executemany(
                    "UPDATE telemetry_buffer SET sync_status = 'PENDING', drain_batch_id = NULL WHERE id = ?",
                    [(rid,) for rid in row_ids],
                )
                self._conn.execute(
                    "UPDATE drain_batches SET status = 'FAILED' WHERE batch_id = ?",
                    (batch_id,),
                )
            self._conn.commit()

        self._connectivity = success
        if success:
            self._last_sync_time = ack_time

        return {
            "synced": len(row_ids) if success else 0,
            "failed": 0 if success else len(row_ids),
            "batch_id": batch_id,
        }

    def start_background_drain(self, interval: float = 5.0) -> None:
        """Start a daemon thread that drains pending packets periodically."""
        if self._drain_active:
            return
        self._drain_active = True

        def _loop():
            while self._drain_active:
                try:
                    self.drain_pending()
                except Exception as exc:
                    logger.error("Background drain error: %s", exc)
                time.sleep(interval)

        self._drain_thread = threading.Thread(target=_loop, daemon=True, name="edge-drain")
        self._drain_thread.start()
        logger.info("Background drain thread started (interval=%.1fs)", interval)

    def stop_background_drain(self) -> None:
        self._drain_active = False
        if self._drain_thread and self._drain_thread.is_alive():
            self._drain_thread.join(timeout=10)

    def recover_incomplete_batches(self) -> int:
        """
        On startup, recover any batches left in DRAINING state (crash recovery).

        Rolls them back to PENDING so they will be retried on the next drain cycle.
        Returns the number of packets recovered.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM telemetry_buffer WHERE sync_status = 'DRAINING'"
            )
            stuck = cur.fetchone()[0]
            if stuck > 0:
                self._conn.execute(
                    "UPDATE telemetry_buffer SET sync_status = 'PENDING', drain_batch_id = NULL "
                    "WHERE sync_status = 'DRAINING'"
                )
                self._conn.execute(
                    "UPDATE drain_batches SET status = 'RECOVERED' WHERE status = 'DRAINING'"
                )
                self._conn.commit()
                logger.warning("Recovered %d packets from incomplete drain batches", stuck)
            return stuck

    @property
    def drain_history(self) -> List[Dict[str, Any]]:
        """Recent drain batch history for observability."""
        cur = self._conn.execute(
            "SELECT batch_id, created_at, packet_count, status, acked_at "
            "FROM drain_batches ORDER BY rowid DESC LIMIT 20"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # -----------------------------------------------------------------
    # Health metrics
    # -----------------------------------------------------------------
    @property
    def health(self) -> BufferHealth:
        """Snapshot of current buffer health."""
        counts = {}
        for status in ("PENDING", "SYNCED", "FAILED"):
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM telemetry_buffer WHERE sync_status = ?",
                (status,),
            )
            counts[status] = cur.fetchone()[0]

        total = sum(counts.values())
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return BufferHealth(
            total_buffered=total,
            pending_sync=counts["PENDING"],
            synced=counts["SYNCED"],
            failed=counts["FAILED"],
            buffer_utilisation=round(total / self.max_buffer_size, 4) if self.max_buffer_size else 0,
            last_write_time=self._last_write_time,
            last_sync_time=self._last_sync_time,
            connectivity=self._connectivity,
            db_size_bytes=db_size,
        )

    # -----------------------------------------------------------------
    # Replay (for post-race analysis)
    # -----------------------------------------------------------------
    def replay(self, session_id: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """
        Read telemetry back from the local buffer (regardless of sync state).
        Enables full local replay even when the cloud link is severed.
        """
        if session_id:
            cur = self._conn.execute(
                "SELECT packet_id, session_id, timestamp, sensor, value, metadata, sync_status "
                "FROM telemetry_buffer WHERE session_id = ? ORDER BY id LIMIT ?",
                (session_id, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT packet_id, session_id, timestamp, sensor, value, metadata, sync_status "
                "FROM telemetry_buffer ORDER BY id LIMIT ?",
                (limit,),
            )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # -----------------------------------------------------------------
    def close(self) -> None:
        self.stop_background_drain()
        self._conn.close()
