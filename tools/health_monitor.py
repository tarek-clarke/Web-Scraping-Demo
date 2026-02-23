#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Pit Wall Health Monitor — CLI Dashboard
=========================================
Developed for the 2026 Cadillac F1 Initiative.

Real-time visibility into:
  • Circuit-Breaker state & DLQ depth
  • Edge Buffer health & sync backlog
  • Latency percentiles (p50 / p95 / p99)
  • Schema Drift alerts
  • Geo-Fence compliance status

Uses Rich Live for a continuously updating terminal UI.

Usage
-----
    # Standalone demo (generates synthetic load)
    python tools/health_monitor.py

    # Attach to a running pipeline (import and feed metrics)
    from tools.health_monitor import PitWallMonitor
    monitor = PitWallMonitor(breaker=my_breaker, buffer=my_buffer)
    monitor.start()
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Deque

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


# ---------------------------------------------------------------------------
# Latency Tracker
# ---------------------------------------------------------------------------
class LatencyTracker:
    """Rolling-window latency percentile tracker."""

    def __init__(self, window_size: int = 500):
        self._window: Deque[float] = deque(maxlen=window_size)

    def record(self, latency_ms: float) -> None:
        self._window.append(latency_ms)

    def percentile(self, p: float) -> float:
        if not self._window:
            return 0.0
        data = sorted(self._window)
        k = (len(data) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(data):
            return data[-1]
        return data[f] + (k - f) * (data[c] - data[f])

    @property
    def p50(self) -> float:
        return round(self.percentile(50), 2)

    @property
    def p95(self) -> float:
        return round(self.percentile(95), 2)

    @property
    def p99(self) -> float:
        return round(self.percentile(99), 2)

    @property
    def sample_count(self) -> int:
        return len(self._window)


# ---------------------------------------------------------------------------
# Drift Alert Log
# ---------------------------------------------------------------------------
@dataclass
class DriftAlert:
    timestamp: str
    sensor: str
    reason: str
    severity: str = "WARNING"   # WARNING | CRITICAL


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------
class PitWallMonitor:
    """
    Aggregates metrics from the circuit breaker, edge buffer, and latency
    tracker into a single Rich Live dashboard.
    """

    def __init__(
        self,
        breaker=None,
        buffer=None,
        geo_fence=None,
        refresh_rate: float = 1.0,
    ):
        self.breaker = breaker
        self.buffer = buffer
        self.geo_fence = geo_fence
        self.latency = LatencyTracker()
        self.drift_alerts: Deque[DriftAlert] = deque(maxlen=50)
        self.refresh_rate = refresh_rate
        self._running = False
        self.console = Console()

        # Summary counters
        self.packets_total = 0
        self.packets_accepted = 0
        self.packets_rejected = 0
        self.start_time = time.time()

    # -----------------------------------------------------------------
    # Alert API
    # -----------------------------------------------------------------
    def record_drift(self, sensor: str, reason: str, severity: str = "WARNING") -> None:
        self.drift_alerts.appendleft(DriftAlert(
            timestamp=datetime.utcnow().strftime("%H:%M:%S"),
            sensor=sensor,
            reason=reason,
            severity=severity,
        ))

    def record_packet(self, accepted: bool, latency_ms: float = 0) -> None:
        self.packets_total += 1
        if accepted:
            self.packets_accepted += 1
        else:
            self.packets_rejected += 1
        if latency_ms > 0:
            self.latency.record(latency_ms)

    # -----------------------------------------------------------------
    # Layout Builders
    # -----------------------------------------------------------------
    def _build_header(self) -> Panel:
        elapsed = time.time() - self.start_time
        mins, secs = divmod(int(elapsed), 60)
        hrs, mins = divmod(mins, 60)
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        header = Text()
        header.append("  CADILLAC F1  ", style="bold white on dark_red")
        header.append("  PIT WALL HEALTH MONITOR  ", style="bold white on grey27")
        header.append(f"  {ts}  ", style="dim")
        header.append(f"  Uptime: {hrs:02d}:{mins:02d}:{secs:02d}", style="dim cyan")
        return Panel(header, box=box.DOUBLE_EDGE, style="bright_white")

    def _build_circuit_breaker_panel(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=True)
        table.add_column("Metric", style="bold", width=22)
        table.add_column("Value", justify="right")

        if self.breaker:
            m = self.breaker.metrics
            state_style = {
                "CLOSED": "bold green",
                "OPEN": "bold red",
                "HALF_OPEN": "bold yellow",
            }.get(m.state, "bold white")

            table.add_row("State", Text(m.state, style=state_style))
            table.add_row("Consecutive Failures", str(m.consecutive_failures))
            table.add_row("Passed", f"[green]{m.total_passed}[/green]")
            table.add_row("Rejected", f"[red]{m.total_rejected}[/red]")
            table.add_row("DLQ Depth", f"[yellow]{m.total_dlq}[/yellow]")
            table.add_row("Uptime Ratio", f"{m.uptime_ratio:.2%}")
        else:
            table.add_row("State", Text("N/A", style="dim"))

        return Panel(table, title="[bold]⚡ Circuit Breaker[/bold]", border_style="cyan")

    def _build_buffer_panel(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=True)
        table.add_column("Metric", style="bold", width=22)
        table.add_column("Value", justify="right")

        if self.buffer:
            h = self.buffer.health
            conn_style = "bold green" if h.connectivity else "bold red blink"
            conn_text = "ONLINE" if h.connectivity else "OFFLINE"
            bar_pct = min(h.buffer_utilisation, 1.0)
            bar_filled = int(bar_pct * 20)
            bar_str = "█" * bar_filled + "░" * (20 - bar_filled)
            bar_color = "green" if bar_pct < 0.7 else ("yellow" if bar_pct < 0.9 else "red")

            table.add_row("Connectivity", Text(conn_text, style=conn_style))
            table.add_row("Buffered", str(h.total_buffered))
            table.add_row("Pending Sync", f"[yellow]{h.pending_sync}[/yellow]")
            table.add_row("Synced", f"[green]{h.synced}[/green]")
            table.add_row("Failed", f"[red]{h.failed}[/red]")
            table.add_row("Utilisation", f"[{bar_color}]{bar_str}[/{bar_color}] {bar_pct:.1%}")
            table.add_row("DB Size", f"{h.db_size_bytes / 1024:.1f} KB")
        else:
            table.add_row("Status", Text("N/A", style="dim"))

        return Panel(table, title="[bold]💾 Edge Buffer[/bold]", border_style="green")

    def _build_latency_panel(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=True)
        table.add_column("Metric", style="bold", width=22)
        table.add_column("Value", justify="right")

        p50 = self.latency.p50
        p95 = self.latency.p95
        p99 = self.latency.p99

        p50_style = "green" if p50 < 10 else ("yellow" if p50 < 50 else "red")
        p95_style = "green" if p95 < 50 else ("yellow" if p95 < 100 else "red")
        p99_style = "green" if p99 < 100 else ("yellow" if p99 < 200 else "red")

        table.add_row("Samples", str(self.latency.sample_count))
        table.add_row("p50 Latency", f"[{p50_style}]{p50:.1f} ms[/{p50_style}]")
        table.add_row("p95 Latency", f"[{p95_style}]{p95:.1f} ms[/{p95_style}]")
        table.add_row("p99 Latency", f"[{p99_style}]{p99:.1f} ms[/{p99_style}]")
        table.add_row("Packets Total", str(self.packets_total))
        rate = self.packets_total / max(time.time() - self.start_time, 1)
        table.add_row("Throughput", f"{rate:.0f} pkt/s")

        return Panel(table, title="[bold]📊 Latency[/bold]", border_style="magenta")

    def _build_drift_panel(self) -> Panel:
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Time", style="dim", width=10)
        table.add_column("Severity", width=10)
        table.add_column("Sensor", width=18)
        table.add_column("Reason")

        for alert in list(self.drift_alerts)[:10]:
            sev_style = "red bold" if alert.severity == "CRITICAL" else "yellow"
            table.add_row(
                alert.timestamp,
                Text(alert.severity, style=sev_style),
                alert.sensor,
                alert.reason[:50],
            )
        if not self.drift_alerts:
            table.add_row("--", "--", "--", "No drift events detected")

        return Panel(table, title="[bold]🚨 Drift Alerts[/bold]", border_style="red")

    def _build_geo_panel(self) -> Panel:
        table = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=True)
        table.add_column("Metric", style="bold", width=22)
        table.add_column("Value", justify="right")

        if self.geo_fence:
            s = self.geo_fence.processing_summary
            table.add_row("Processed", str(s["total_processed"]))
            for jur, cnt in s.get("by_jurisdiction", {}).items():
                table.add_row(f"  {jur}", str(cnt))
            table.add_row("Fields Scrubbed", f"[yellow]{s['total_fields_scrubbed']}[/yellow]")
            table.add_row("Fields Anonymised", f"[cyan]{s['total_fields_anonymised']}[/cyan]")
        else:
            table.add_row("Status", Text("N/A", style="dim"))

        return Panel(table, title="[bold]🌍 Geo-Fence[/bold]", border_style="blue")

    # -----------------------------------------------------------------
    # Dashboard Assembly
    # -----------------------------------------------------------------
    def build_dashboard(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="upper", size=14),
            Layout(name="lower"),
        )
        layout["upper"].split_row(
            Layout(name="breaker"),
            Layout(name="buffer"),
            Layout(name="latency"),
        )
        layout["lower"].split_row(
            Layout(name="drift", ratio=3),
            Layout(name="geo", ratio=2),
        )

        layout["header"].update(self._build_header())
        layout["breaker"].update(self._build_circuit_breaker_panel())
        layout["buffer"].update(self._build_buffer_panel())
        layout["latency"].update(self._build_latency_panel())
        layout["drift"].update(self._build_drift_panel())
        layout["geo"].update(self._build_geo_panel())

        return layout

    # -----------------------------------------------------------------
    # Live Loop
    # -----------------------------------------------------------------
    def start(self, duration: Optional[float] = None) -> None:
        """
        Start the live dashboard.

        Parameters
        ----------
        duration : float | None
            If set, auto-stop after this many seconds (useful for demos/tests).
        """
        self._running = True
        deadline = time.time() + duration if duration else None

        with Live(self.build_dashboard(), console=self.console, refresh_per_second=2) as live:
            while self._running:
                live.update(self.build_dashboard())
                time.sleep(self.refresh_rate)
                if deadline and time.time() >= deadline:
                    break

    def stop(self) -> None:
        self._running = False

    # -----------------------------------------------------------------
    # One-shot snapshot (non-live, for scripting)
    # -----------------------------------------------------------------
    def snapshot(self) -> None:
        """Print a single frame of the dashboard and exit."""
        self.console.print(self.build_dashboard())


# ---------------------------------------------------------------------------
# Standalone Demo — Generates synthetic load to exercise the dashboard
# ---------------------------------------------------------------------------
def _run_demo(duration: int = 30) -> None:
    """
    Self-contained demo that spins up a circuit breaker, edge buffer,
    and geo-fence, then feeds them synthetic telemetry while the
    dashboard renders live.
    """
    from src.circuit_breaker import TelemetryCircuitBreaker, TelemetryPacket, SchemaValidator
    from src.local_persistence import TracksideEdgeBuffer, BufferedPacket
    from src.geo_fence import GeoFence

    console = Console()
    console.print("\n[bold bright_white on dark_red]  CADILLAC F1 — PIT WALL MONITOR DEMO  [/bold bright_white on dark_red]\n")

    # --- Initialise subsystems ---
    breaker = TelemetryCircuitBreaker(
        failure_threshold=5,
        recovery_timeout=8.0,
        dlq_path="data/demo_dlq.sqlite",
    )
    buffer = TracksideEdgeBuffer(db_path="data/demo_edge_buffer.sqlite")
    geo = GeoFence()

    monitor = PitWallMonitor(breaker=breaker, buffer=buffer, geo_fence=geo)

    circuits = ["barcelona", "silverstone", "austin", "monza", "suzuka"]
    sensors = ["speed", "rpm", "throttle", "brake_temp", "engine_temp", "aero_load", "heart_rate"]

    # --- Background telemetry generator ---
    def _generate():
        pkt_count = 0
        while monitor._running:
            circuit = random.choice(circuits)
            sensor = random.choice(sensors)

            # Dynamic chaos: ramp up mid-demo to trigger breaker trip,
            # then settle back so the audience sees recovery in real-time.
            elapsed = time.time() - monitor.start_time
            demo_frac = elapsed / max(duration, 1)
            if 0.30 < demo_frac < 0.50:
                # Burst phase — high corruption to trip the breaker
                chaos_chance = 0.45
            elif 0.50 <= demo_frac < 0.65:
                # Recovery phase — moderate
                chaos_chance = 0.08
            else:
                # Normal operations
                chaos_chance = 0.12

            if random.random() < chaos_chance:
                value: Any = random.choice([None, "CORRUPT", -9999, 99999])
                severity = "CRITICAL" if value is None else "WARNING"
            else:
                ranges = {
                    "speed": (80, 350), "rpm": (5000, 15000), "throttle": (0, 100),
                    "brake_temp": (200, 900), "engine_temp": (80, 120),
                    "aero_load": (200, 2500), "heart_rate": (60, 190),
                }
                lo, hi = ranges.get(sensor, (0, 100))
                value = round(random.uniform(lo, hi), 1)
                severity = None

            pkt = TelemetryPacket(sensor=sensor, value=value)

            t0 = time.time()
            accepted, reason = breaker.process(pkt)
            latency_ms = (time.time() - t0) * 1000

            monitor.record_packet(accepted, latency_ms)
            if not accepted and severity:
                monitor.record_drift(sensor, reason, severity)

            # Buffer the good packets
            if accepted:
                bp = BufferedPacket(
                    packet_id=pkt.packet_id,
                    session_id="demo_session",
                    sensor=sensor,
                    value=value,
                )
                buffer.write(bp)

            # Geo-fence a sample
            if pkt_count % 10 == 0:
                geo.process(circuit, {"sensor": sensor, "value": value, "heart_rate": 145})

            pkt_count += 1
            time.sleep(random.uniform(0.01, 0.05))

    gen_thread = threading.Thread(target=_generate, daemon=True)
    gen_thread.start()

    # Give the generator a moment to warm up before rendering
    time.sleep(0.3)

    # --- Launch dashboard ---
    try:
        monitor.start(duration=duration)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()

    # Print final summary (before closing DB handles)
    dlq_depth = breaker.dlq.depth()
    console.print("\n[bold green]✓ Demo complete[/bold green]")
    console.print(f"  Packets processed: {monitor.packets_total}")
    console.print(f"  Accepted: {monitor.packets_accepted}  Rejected: {monitor.packets_rejected}")
    console.print(f"  DLQ Depth: {dlq_depth}")
    console.print(f"  Latency p50={monitor.latency.p50}ms  p95={monitor.latency.p95}ms  p99={monitor.latency.p99}ms\n")

    breaker.dlq.close()
    buffer.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cadillac F1 Pit Wall Health Monitor")
    parser.add_argument("--duration", type=int, default=30, help="Demo duration in seconds")
    parser.add_argument("--snapshot", action="store_true", help="Print a single frame and exit")
    args = parser.parse_args()

    if args.snapshot:
        m = PitWallMonitor()
        m.snapshot()
    else:
        _run_demo(duration=args.duration)
