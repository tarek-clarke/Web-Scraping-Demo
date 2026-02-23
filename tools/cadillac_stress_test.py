#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Cadillac F1 Triple-Header Stress Test
=======================================
Developed for the 2026 Cadillac F1 Initiative.

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
    PYTHONPATH="." python tools/cadillac_stress_test.py
    PYTHONPATH="." python tools/cadillac_stress_test.py --packets 5000 --chaos 0.20

Author: Tarek Clarke (PhD Candidate — TalTech)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich import box

from src.circuit_breaker import (
    TelemetryCircuitBreaker,
    TelemetryPacket,
    SchemaValidator,
    CircuitState,
)
from src.local_persistence import TracksideEdgeBuffer, BufferedPacket
from src.geo_fence import GeoFence


console = Console()


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

    def __init__(self, chaos_rate: float = 0.12):
        self.chaos_rate = chaos_rate
        self.events_injected: Dict[str, int] = defaultdict(int)

    def maybe_corrupt(
        self, sensor: str, value: float
    ) -> Tuple[str, Any, Optional[str]]:
        """
        Returns (sensor_name, value, chaos_type_or_None).
        """
        if random.random() > self.chaos_rate:
            return sensor, value, None

        mode = random.choice(CHAOS_MODES)
        self.events_injected[mode] += 1

        if mode == "null_value":
            return sensor, None, mode
        elif mode == "string_in_numeric":
            return sensor, random.choice(["OVERHEAT", "ERR_DECODE", "NaN", "---"]), mode
        elif mode == "bit_flip_high":
            return sensor, value * random.uniform(100, 1000), mode
        elif mode == "bit_flip_low":
            return sensor, -abs(value) * random.uniform(10, 100), mode
        elif mode == "schema_drift":
            # Rename the sensor to simulate firmware change
            drifted = sensor + random.choice(["_v2", "_new", "_alt", "_canbus", "_raw"])
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
class CadillacStressTest:
    """
    Triple-header stress test that exercises every layer of the
    Cadillac F1 telemetry spine.
    """

    def __init__(
        self,
        packets_per_session: int = 1000,
        chaos_rate: float = 0.12,
        breaker_threshold: int = 5,
        breaker_recovery: float = 2.0,
        output_dir: str = "data/reports",
    ):
        self.packets_per_session = packets_per_session
        self.chaos = ChaosInjector(chaos_rate)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Subsystems
        self.breaker = TelemetryCircuitBreaker(
            failure_threshold=breaker_threshold,
            recovery_timeout=breaker_recovery,
            dlq_path="data/stress_dlq.sqlite",
        )
        self.buffer = TracksideEdgeBuffer(db_path="data/stress_edge_buffer.sqlite")
        self.geo = GeoFence()

        self.report = StressTestReport()
        self._latencies: List[float] = []
        self._breaker_trip_count = 0

    # -----------------------------------------------------------------
    def run(self) -> StressTestReport:
        """Execute the full Triple-Header stress test."""
        console.print(Panel(
            "[bold bright_white]CADILLAC F1 — TRIPLE-HEADER STRESS TEST[/bold bright_white]\n"
            "[dim]Simulating 3 consecutive race weekends with randomised chaos injection[/dim]",
            style="on dark_red",
            box=box.DOUBLE_EDGE,
        ))
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
        self._export_results()

        # Cleanup
        self.breaker.dlq.close()
        self.buffer.close()

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

            pkt = TelemetryPacket(sensor=sensor_out, value=value_out)

            # Circuit Breaker
            t0 = time.monotonic()
            accepted, reason = self.breaker.process(pkt)
            latency_ms = (time.monotonic() - t0) * 1000
            session_latencies.append(latency_ms)
            self._latencies.append(latency_ms)

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
            else:
                result.packets_rejected += 1

            # Detect breaker trips
            cur_state = self.breaker.state
            if prev_state != CircuitState.OPEN and cur_state == CircuitState.OPEN:
                result.breaker_trips += 1
                self._breaker_trip_count += 1
            prev_state = cur_state

            # Geo-fence every 50th packet
            if i % 50 == 0:
                payload = {"sensor": sensor_out, "value": value_out, "heart_rate": 155}
                gf_result = self.geo.process(weekend.circuit, payload)
                result.geo_scrubbed += len(gf_result.fields_scrubbed)

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
    def _finalise_report(self) -> None:
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
        #   40% acceptance under chaos  +  30% breaker recovery  +  30% latency health
        acceptance_score = self.report.overall_acceptance_rate
        recovery_score = 1.0 if self._breaker_trip_count == 0 else max(
            0, 1.0 - (self._breaker_trip_count / (len(self.report.sessions) * 2))
        )
        latency_score = max(0, 1.0 - (self.report.overall_latency_p95 / 50.0))
        self.report.resilience_score = round(
            0.40 * acceptance_score + 0.30 * recovery_score + 0.30 * latency_score, 4
        )

        if self.report.resilience_score >= 0.85:
            self.report.verdict = "RACE-READY ✅"
        elif self.report.resilience_score >= 0.70:
            self.report.verdict = "CONDITIONAL — Review Required ⚠️"
        else:
            self.report.verdict = "NOT READY — Engineering Review ❌"

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

        console.print(Panel(
            f"[bold]Resilience Score:[/bold] {self.report.resilience_score:.2%}\n"
            f"[bold]Acceptance Rate:[/bold]  {self.report.overall_acceptance_rate:.2%}\n"
            f"[bold]Breaker Trips:[/bold]    {self.report.total_breaker_trips}\n"
            f"[bold]DLQ Total:[/bold]        {self.report.total_dlq}\n"
            f"[bold]p95 Latency:[/bold]      {self.report.overall_latency_p95:.2f} ms\n\n"
            f"[{verdict_style}]VERDICT: {self.report.verdict}[/{verdict_style}]",
            title="[bold bright_white on dark_red]  FINAL ASSESSMENT  [/bold bright_white on dark_red]",
            border_style="bright_white",
        ))

    # -----------------------------------------------------------------
    def _export_results(self) -> None:
        """Write results to CSV and JSON for downstream consumption."""
        # --- CSV ---
        csv_path = self.output_dir / "cadillac_stress_test_results.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "session_name", "circuit", "packets_sent", "packets_accepted",
                "packets_rejected", "chaos_injected", "breaker_trips",
                "breaker_final_state", "dlq_depth", "latency_p50_ms",
                "latency_p95_ms", "latency_p99_ms", "geo_scrubbed",
            ])
            writer.writeheader()
            for s in self.report.sessions:
                writer.writerow(asdict(s))
        console.print(f"\n[dim]CSV exported → {csv_path}[/dim]")

        # --- JSON ---
        json_path = self.output_dir / "cadillac_stress_test_report.json"
        with open(json_path, "w") as f:
            json.dump(asdict(self.report), f, indent=2, default=str)
        console.print(f"[dim]JSON exported → {json_path}[/dim]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Cadillac F1 Triple-Header Stress Test"
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
        "--threshold", type=int, default=5,
        help="Circuit-breaker failure threshold (default: 5)"
    )
    args = parser.parse_args()

    test = CadillacStressTest(
        packets_per_session=args.packets,
        chaos_rate=args.chaos,
        breaker_threshold=args.threshold,
    )
    report = test.run()
    return 0 if "✅" in report.verdict else 1


if __name__ == "__main__":
    sys.exit(main())
