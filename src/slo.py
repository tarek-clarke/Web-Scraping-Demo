#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Service Level Objective (SLO) Tracker
=======================================
Developed for the 2026 Cadillac F1 Initiative.

Defines, evaluates, and reports SLOs for the telemetry pipeline.
Designed to be called at the end of any stress test or health check.

SLO Definitions
---------------
- LATENCY_P95_MS   : 95th-percentile packet latency must be < 100 ms
- ACCEPTANCE_RATE  : Clean-data acceptance rate must be > 80 %
- DLQ_DEPTH        : DLQ depth must be < 5,000 packets
- AUDIT_INTEGRITY  : Audit hash chain must be intact (True)
- DETECTION_RATE   : Corruption detection rate must be ≥ 95 %

Usage
-----
    from src.slo import SLOTracker, SLOResult

    tracker = SLOTracker()
    results = tracker.evaluate(
        latency_p95_ms=62.0,
        acceptance_rate=0.84,
        dlq_depth=2421,
        audit_intact=True,
        detection_rate=1.0,
    )
    tracker.print_report(results)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class SLOBudget:
    """Definition of a single SLO."""
    name: str
    description: str
    threshold: float
    unit: str
    direction: str  # "lt" (lower is better) or "gt" (higher is better)


@dataclass
class SLOResult:
    """Evaluation result for a single SLO."""
    name: str
    description: str
    threshold: float
    unit: str
    actual: float
    passed: bool
    margin: float  # positive = headroom, negative = violation


@dataclass
class SLOReport:
    """Full SLO report for one pipeline run."""
    results: List[SLOResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    overall: str = "UNKNOWN"
    alerts: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SLO Tracker
# ---------------------------------------------------------------------------
class SLOTracker:
    """
    Evaluates pipeline metrics against defined SLO budgets.

    Produces a structured SLOReport with pass/fail per objective,
    margin, and actionable alerts for any violation.
    """

    BUDGETS: List[SLOBudget] = [
        SLOBudget(
            name="LATENCY_P95",
            description="p95 packet latency",
            threshold=100.0,
            unit="ms",
            direction="lt",
        ),
        SLOBudget(
            name="ACCEPTANCE_RATE",
            description="Acceptance rate (clean-data throughput)",
            threshold=0.80,
            unit="%",
            direction="gt",
        ),
        SLOBudget(
            name="DLQ_DEPTH",
            description="DLQ depth (unresolved quarantine)",
            threshold=5000.0,
            unit="packets",
            direction="lt",
        ),
        SLOBudget(
            name="AUDIT_INTEGRITY",
            description="Audit hash chain integrity",
            threshold=1.0,
            unit="bool",
            direction="gt",
        ),
        SLOBudget(
            name="DETECTION_RATE",
            description="Corruption detection rate",
            threshold=0.95,
            unit="%",
            direction="gt",
        ),
        SLOBudget(
            name="BREAKER_TRIPS_PER_SESSION",
            description="Circuit breaker trips per session",
            threshold=3.0,
            unit="trips",
            direction="lt",
        ),
    ]

    def evaluate(
        self,
        latency_p95_ms: float,
        acceptance_rate: float,
        dlq_depth: int,
        audit_intact: bool,
        detection_rate: float,
        breaker_trips: int = 0,
        num_sessions: int = 1,
    ) -> SLOReport:
        """
        Evaluate all SLO budgets against observed metrics.

        Parameters
        ----------
        latency_p95_ms : float
            p95 latency in milliseconds.
        acceptance_rate : float
            Clean-data packets accepted as a fraction (0–1).
        dlq_depth : int
            Current DLQ depth.
        audit_intact : bool
            Whether the audit hash chain is intact.
        detection_rate : float
            Fraction of injected chaos detected (0–1).
        breaker_trips : int
            Total circuit breaker trips across all sessions.
        num_sessions : int
            Number of sessions run (for per-session normalisation).
        """
        actuals = {
            "LATENCY_P95":               latency_p95_ms,
            "ACCEPTANCE_RATE":           acceptance_rate,
            "DLQ_DEPTH":                 float(dlq_depth),
            "AUDIT_INTEGRITY":           1.0 if audit_intact else 0.0,
            "DETECTION_RATE":            detection_rate,
            "BREAKER_TRIPS_PER_SESSION": (
                breaker_trips / max(1, num_sessions)
            ),
        }

        report = SLOReport()
        for budget in self.BUDGETS:
            actual = actuals[budget.name]
            if budget.direction == "lt":
                passed = actual < budget.threshold
                margin = budget.threshold - actual  # positive = headroom
            else:
                passed = actual >= budget.threshold
                margin = actual - budget.threshold  # positive = headroom

            result = SLOResult(
                name=budget.name,
                description=budget.description,
                threshold=budget.threshold,
                unit=budget.unit,
                actual=round(actual, 4),
                passed=passed,
                margin=round(margin, 4),
            )
            report.results.append(result)
            if passed:
                report.passed += 1
            else:
                report.failed += 1
                report.alerts.append(
                    f"[ALERT] SLO VIOLATED — {budget.name}: "
                    f"actual={actual:.4f} {budget.unit}, "
                    f"budget={budget.threshold} {budget.unit}"
                )

        if report.failed == 0:
            report.overall = "ALL SLOs MET ✅"
        elif report.failed <= 1:
            report.overall = "MINOR SLO BREACH ⚠️"
        else:
            report.overall = "MULTIPLE SLO BREACHES ❌"

        return report

    # ------------------------------------------------------------------
    def print_report(self, report: SLOReport) -> None:
        """Print a formatted SLO report to stdout."""
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich import box as rbox

            console = Console()
            table = Table(
                title="Service Level Objectives",
                box=rbox.SIMPLE_HEAD,
                show_lines=False,
            )
            table.add_column("SLO", style="bold cyan", width=28)
            table.add_column("Description", width=36)
            table.add_column("Budget", justify="right", width=12)
            table.add_column("Actual", justify="right", width=12)
            table.add_column("Margin", justify="right", width=12)
            table.add_column("Status", justify="center", width=10)

            for r in report.results:
                status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
                margin_str = (
                    f"[green]+{r.margin:.3f}[/green]"
                    if r.margin >= 0
                    else f"[red]{r.margin:.3f}[/red]"
                )
                table.add_row(
                    r.name,
                    r.description,
                    f"{r.threshold} {r.unit}",
                    f"{r.actual:.4f}",
                    margin_str,
                    status,
                )

            console.print("\n")
            console.print(table)

            overall_style = (
                "bold green" if "✅" in report.overall
                else ("bold yellow" if "⚠️" in report.overall else "bold red")
            )
            for alert in report.alerts:
                console.print(f"  [bold yellow]{alert}[/bold yellow]")

            console.print(
                Panel(
                    f"[bold]SLOs Passed:[/bold]  {report.passed}/{report.passed + report.failed}\n"
                    f"[{overall_style}]{report.overall}[/{overall_style}]",
                    title="[bold bright_white on dark_blue]  SLO SUMMARY  [/bold bright_white on dark_blue]",
                    border_style="bright_blue",
                )
            )
        except ImportError:
            # Fallback without rich
            print("\n=== SLO REPORT ===")
            for r in report.results:
                status = "PASS" if r.passed else "FAIL"
                print(f"  {r.name:<28} {status}  actual={r.actual:.4f} budget={r.threshold} {r.unit}")
            print(f"\n  {report.overall}")
            for alert in report.alerts:
                print(f"  {alert}")
