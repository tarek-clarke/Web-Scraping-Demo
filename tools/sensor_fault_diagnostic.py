#!/usr/bin/env python3
"""
Sensor Fault Diagnostic Tool
Standalone analysis of missed fault detections from GPU stress test diagnostic output.

Usage:
    python tools/sensor_fault_diagnostic.py --input data/reports/missed_detection_analysis.json
    python tools/sensor_fault_diagnostic.py --input missed_analysis.json --output-text report.txt --output-csv breakdown.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class SensorFaultDiagnostic:
    """Analyzes missed detection breakdown from GPU stress test diagnostic output."""

    # Thresholds for flagging high-miss scenarios
    HIGH_MISS_RATE_THRESHOLD = 0.01  # >1%
    CRITICAL_MISS_RATE_THRESHOLD = 0.05  # >5%

    def __init__(self, analysis: Dict[str, Any]):
        """Initialize diagnostic with analysis data from stress test."""
        self.analysis = analysis
        self.missed_fault_count = analysis.get("missed_fault_count", 0)
        self.detection_rate = analysis.get("detection_rate", 1.0)
        self.miss_rate = analysis.get("miss_rate", 0.0)
        self.missed_by_sensor = analysis.get("missed_by_sensor", [])
        self.missed_by_chaos_mode = analysis.get("missed_by_chaos_mode", [])
        self.missed_by_session = analysis.get("missed_by_session", [])
        self.missed_by_sensor_and_chaos = analysis.get("missed_by_sensor_and_chaos", [])

    def format_miss_rate(self, miss_rate: float) -> str:
        """Format miss rate as percentage with visual indicator."""
        pct = miss_rate * 100
        if miss_rate >= self.CRITICAL_MISS_RATE_THRESHOLD:
            flag = "🔴 CRITICAL"
        elif miss_rate >= self.HIGH_MISS_RATE_THRESHOLD:
            flag = "🟡 HIGH"
        else:
            flag = "✅ OK"
        return f"{pct:.2f}% ({flag})"

    def print_summary(self) -> None:
        """Print overall summary statistics."""
        print("\n" + "=" * 80)
        print("SENSOR FAULT DIAGNOSTIC - SUMMARY")
        print("=" * 80)
        print(f"Total Missed Faults:         {self.missed_fault_count:,}")
        print(f"Overall Detection Rate:      {self.detection_rate:.4f} ({(self.detection_rate)*100:.2f}%)")
        print(f"Overall Miss Rate:           {self.format_miss_rate(self.miss_rate)}")
        print("=" * 80)

    def print_by_sensor(self) -> None:
        """Print miss breakdown by sensor."""
        print("\n" + "-" * 80)
        print("MISSED DETECTIONS BY SENSOR (ranked by miss count)")
        print("-" * 80)

        # Sort by miss_count descending
        sorted_sensors = sorted(
            self.missed_by_sensor,
            key=lambda x: x.get("miss_count", 0),
            reverse=True,
        )

        if not sorted_sensors:
            print("  No missed detections recorded by sensor.")
            return

        print(f"{'Sensor':<30} {'Misses':<12} {'Injected':<12} {'Miss Rate':<20}")
        print("-" * 80)

        for row in sorted_sensors:
            sensor_id = row.get("sensor_id", "unknown")
            miss_count = row.get("miss_count", 0)
            total_injected = row.get("total_injected", 0)
            miss_rate = row.get("miss_rate", 0.0)

            sensor_display = sensor_id[:29]
            miss_display = f"{miss_count:,}"
            injected_display = f"{total_injected:,}"
            rate_display = self.format_miss_rate(miss_rate)

            print(f"{sensor_display:<30} {miss_display:<12} {injected_display:<12} {rate_display:<20}")

    def print_by_chaos_mode(self) -> None:
        """Print miss breakdown by chaos mode."""
        print("\n" + "-" * 80)
        print("MISSED DETECTIONS BY CHAOS MODE (ranked by miss count)")
        print("-" * 80)

        # Sort by miss_count descending
        sorted_modes = sorted(
            self.missed_by_chaos_mode,
            key=lambda x: x.get("miss_count", 0),
            reverse=True,
        )

        if not sorted_modes:
            print("  No missed detections recorded by chaos mode.")
            return

        print(f"{'Chaos Mode':<30} {'Misses':<12} {'Injected':<12} {'Miss Rate':<20}")
        print("-" * 80)

        for row in sorted_modes:
            chaos_mode = row.get("chaos_mode", "unknown")
            miss_count = row.get("miss_count", 0)
            total_injected = row.get("total_injected", 0)
            miss_rate = row.get("miss_rate", 0.0)

            mode_display = chaos_mode[:29]
            miss_display = f"{miss_count:,}"
            injected_display = f"{total_injected:,}"
            rate_display = self.format_miss_rate(miss_rate)

            print(f"{mode_display:<30} {miss_display:<12} {injected_display:<12} {rate_display:<20}")

    def print_by_session(self) -> None:
        """Print miss breakdown by session."""
        print("\n" + "-" * 80)
        print("MISSED DETECTIONS BY SESSION (ranked by miss count)")
        print("-" * 80)

        # Sort by miss_count descending
        sorted_sessions = sorted(
            self.missed_by_session,
            key=lambda x: x.get("miss_count", 0),
            reverse=True,
        )

        if not sorted_sessions:
            print("  No missed detections recorded by session.")
            return

        print(f"{'Session':<30} {'Misses':<12} {'Injected':<12} {'Miss Rate':<20}")
        print("-" * 80)

        for row in sorted_sessions:
            session = row.get("session", "unknown")
            miss_count = row.get("miss_count", 0)
            total_injected = row.get("total_injected", 0)
            miss_rate = row.get("miss_rate", 0.0)

            session_display = session[:29]
            miss_display = f"{miss_count:,}"
            injected_display = f"{total_injected:,}"
            rate_display = self.format_miss_rate(miss_rate)

            print(f"{session_display:<30} {miss_display:<12} {injected_display:<12} {rate_display:<20}")

    def print_by_sensor_and_chaos(self) -> None:
        """Print miss breakdown by sensor + chaos mode combination."""
        print("\n" + "-" * 80)
        print("MISSED DETECTIONS BY SENSOR + CHAOS MODE (ranked by miss count)")
        print("-" * 80)

        # Sort by miss_count descending
        sorted_combos = sorted(
            self.missed_by_sensor_and_chaos,
            key=lambda x: x.get("miss_count", 0),
            reverse=True,
        )

        if not sorted_combos:
            print("  No missed detections recorded by sensor+chaos combination.")
            return

        print(f"{'Sensor':<25} {'Chaos Mode':<20} {'Misses':<10} {'Miss Rate':<20}")
        print("-" * 80)

        for row in sorted_combos:
            sensor_id = row.get("sensor_id", "unknown")
            chaos_mode = row.get("chaos_mode", "unknown")
            miss_count = row.get("miss_count", 0)
            miss_rate = row.get("miss_rate", 0.0)

            sensor_display = sensor_id[:24]
            chaos_display = chaos_mode[:19]
            miss_display = f"{miss_count:,}"
            rate_display = self.format_miss_rate(miss_rate)

            print(f"{sensor_display:<25} {chaos_display:<20} {miss_display:<10} {rate_display:<20}")

    def print_report(self) -> None:
        """Print full diagnostic report to stdout."""
        self.print_summary()
        self.print_by_sensor()
        self.print_by_chaos_mode()
        self.print_by_session()
        self.print_by_sensor_and_chaos()
        print("\n" + "=" * 80)

    def export_csv(self, output_path: Path) -> None:
        """Export breakdown tables as CSV file."""
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Section 1: By Sensor
            writer.writerow(["=== MISSED DETECTIONS BY SENSOR ==="])
            writer.writerow(["sensor_id", "miss_count", "total_injected", "miss_rate", "miss_rate_pct"])
            for row in sorted(
                self.missed_by_sensor,
                key=lambda x: x.get("miss_count", 0),
                reverse=True,
            ):
                writer.writerow([
                    row.get("sensor_id", ""),
                    row.get("miss_count", 0),
                    row.get("total_injected", 0),
                    f"{row.get('miss_rate', 0):.6f}",
                    f"{row.get('miss_rate', 0)*100:.2f}%",
                ])
            writer.writerow([])

            # Section 2: By Chaos Mode
            writer.writerow(["=== MISSED DETECTIONS BY CHAOS MODE ==="])
            writer.writerow(["chaos_mode", "miss_count", "total_injected", "miss_rate", "miss_rate_pct"])
            for row in sorted(
                self.missed_by_chaos_mode,
                key=lambda x: x.get("miss_count", 0),
                reverse=True,
            ):
                writer.writerow([
                    row.get("chaos_mode", ""),
                    row.get("miss_count", 0),
                    row.get("total_injected", 0),
                    f"{row.get('miss_rate', 0):.6f}",
                    f"{row.get('miss_rate', 0)*100:.2f}%",
                ])
            writer.writerow([])

            # Section 3: By Session
            writer.writerow(["=== MISSED DETECTIONS BY SESSION ==="])
            writer.writerow(["session", "miss_count", "total_injected", "miss_rate", "miss_rate_pct"])
            for row in sorted(
                self.missed_by_session,
                key=lambda x: x.get("miss_count", 0),
                reverse=True,
            ):
                writer.writerow([
                    row.get("session", ""),
                    row.get("miss_count", 0),
                    row.get("total_injected", 0),
                    f"{row.get('miss_rate', 0):.6f}",
                    f"{row.get('miss_rate', 0)*100:.2f}%",
                ])
            writer.writerow([])

            # Section 4: By Sensor + Chaos Mode
            writer.writerow(["=== MISSED DETECTIONS BY SENSOR + CHAOS MODE ==="])
            writer.writerow(["sensor_id", "chaos_mode", "miss_count", "total_injected", "miss_rate", "miss_rate_pct", "severity"])
            for row in sorted(
                self.missed_by_sensor_and_chaos,
                key=lambda x: x.get("miss_count", 0),
                reverse=True,
            ):
                miss_rate = row.get("miss_rate", 0.0)
                if miss_rate >= self.CRITICAL_MISS_RATE_THRESHOLD:
                    severity = "CRITICAL"
                elif miss_rate >= self.HIGH_MISS_RATE_THRESHOLD:
                    severity = "HIGH"
                else:
                    severity = "LOW"

                writer.writerow([
                    row.get("sensor_id", ""),
                    row.get("chaos_mode", ""),
                    row.get("miss_count", 0),
                    row.get("total_injected", 0),
                    f"{miss_rate:.6f}",
                    f"{miss_rate*100:.2f}%",
                    severity,
                ])


def main():
    parser = argparse.ArgumentParser(
        description="Sensor Fault Diagnostic: Analyze missed detection breakdowns",
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="Path to missed_detection_analysis JSON file from GPU stress test",
    )
    parser.add_argument(
        "--output-text", type=str, default=None,
        help="Optional output file for text report (default: print to stdout)",
    )
    parser.add_argument(
        "--output-csv", type=str, default=None,
        help="Optional output file for CSV breakdown (if not provided, no CSV export)",
    )
    args = parser.parse_args()

    # Load analysis JSON
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        with open(input_path, "r") as f:
            analysis = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON file: {e}", file=sys.stderr)
        return 1

    # Create diagnostic instance
    diagnostic = SensorFaultDiagnostic(analysis)

    # Print report (to stdout or file)
    if args.output_text:
        with open(args.output_text, "w") as f:
            # Redirect print output
            import io
            import contextlib

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                diagnostic.print_report()
            f.write(buffer.getvalue())
        print(f"✅ Text report exported to {args.output_text}")
    else:
        diagnostic.print_report()

    # Export CSV if requested
    if args.output_csv:
        csv_path = Path(args.output_csv)
        diagnostic.export_csv(csv_path)
        print(f"✅ CSV export written to {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
