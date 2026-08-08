#!/usr/bin/env python3
"""Aggregate workload energy summaries and emit JSON, CSV, and LaTeX."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


PHASE_ORDER = ("Oracle construction", "VQC optimization", "Model selection")


def phase_for(label: str) -> str:
    if "oracle" in label:
        return "Oracle construction"
    if "vqc-train" in label:
        return "VQC optimization"
    if "vqc-select" in label:
        return "Model selection"
    return "Other"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--inputs", nargs="+", required=True)
    args = parser.parse_args()

    paths = list(dict.fromkeys(Path(item).resolve() for item in args.inputs))
    rows = []
    excluded_replicas = []
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("status") != "complete":
            raise RuntimeError(f"Incomplete energy summary: {path}")
        telemetry = report.get("telemetry", {})
        if not telemetry.get("energy_sensor_owner", True):
            excluded_replicas.append(str(path))
            continue
        if telemetry.get("gpu_power_source") not in {"nvml", "amd_sysfs"}:
            raise RuntimeError(f"Unmeasured GPU energy summary: {path}")
        rows.append(
            {
                "phase": phase_for(str(report.get("label", ""))),
                "label": report.get("label"),
                "path": str(path),
                "samples": int(telemetry.get("samples_count", 0)),
                "elapsed_seconds": float(telemetry.get("elapsed_seconds", 0.0)),
                "gpu_joules": float(telemetry.get("gpu_energy_draw_joules", 0.0)),
                "cpu_joules": float(telemetry.get("cpu_energy_draw_joules", 0.0)),
                "estimated_gCO2e": float(telemetry.get("estimated_gCO2e", 0.0)),
                "gpu_power_source": telemetry.get("gpu_power_source"),
                "cpu_power_source": telemetry.get("cpu_power_source"),
                "measurement_quality": telemetry.get("measurement_quality"),
                "gpu_measurement_scope": telemetry.get("gpu_measurement_scope"),
            }
        )
    if not rows:
        raise RuntimeError("No owner energy summaries were available to aggregate")

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["phase"]].append(row)
    phase_rows = []
    for phase in (*PHASE_ORDER, "Other"):
        items = grouped.get(phase, [])
        if not items:
            continue
        cpu_observed = any(item["cpu_power_source"] != "unavailable" for item in items)
        phase_rows.append(
            {
                "phase": phase,
                "summaries": len(items),
                "samples": sum(item["samples"] for item in items),
                "elapsed_seconds_max": max(item["elapsed_seconds"] for item in items),
                "gpu_energy_joules": sum(item["gpu_joules"] for item in items),
                "cpu_energy_joules": (
                    sum(item["cpu_joules"] for item in items) if cpu_observed else None
                ),
                "estimated_gCO2e": sum(item["estimated_gCO2e"] for item in items),
                "gpu_power_sources": sorted({item["gpu_power_source"] for item in items}),
                "cpu_power_sources": sorted({item["cpu_power_source"] for item in items}),
                "measurement_scopes": sorted(
                    {str(item["gpu_measurement_scope"]) for item in items}
                ),
            }
        )

    output = Path(args.output_prefix)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "complete",
        "aggregation": "sum distinct sensor-owner workloads; replica MI250X GCD summaries excluded",
        "input_count": len(paths),
        "included_count": len(rows),
        "excluded_replica_summaries": excluded_replicas,
        "phases": phase_rows,
        "inputs": rows,
    }
    output.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        fieldnames = [
            "phase", "summaries", "samples", "elapsed_seconds_max",
            "gpu_energy_joules", "cpu_energy_joules", "estimated_gCO2e",
            "gpu_power_sources", "cpu_power_sources", "measurement_scopes",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in phase_rows:
            writer.writerow(
                {
                    **row,
                    "gpu_power_sources": ";".join(row["gpu_power_sources"]),
                    "cpu_power_sources": ";".join(row["cpu_power_sources"]),
                    "measurement_scopes": ";".join(row["measurement_scopes"]),
                }
            )

    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\caption{Host-observed energy for router-oracle construction and VQC training.}",
        "\\label{tab:router-host-energy}",
        "\\begin{tabular}{lrrr}",
        "\\toprule",
        "Phase & Samples & GPU energy (kJ) & CPU energy (kJ) \\\\",
        "\\midrule",
    ]
    for row in phase_rows:
        cpu_text = (
            f"{row['cpu_energy_joules'] / 1000.0:.3f}"
            if row["cpu_energy_joules"] is not None
            else "--"
        )
        lines.append(
            f"{row['phase']} & {row['samples']} & "
            f"{row['gpu_energy_joules'] / 1000.0:.3f} & {cpu_text} \\\\"
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\begin{flushleft}\\footnotesize CPU energy is shown as -- when no RAPL counter was observable. "
            "MI250X package sensors are counted once per physical card; carbon values remain estimates.\\end{flushleft}",
            "\\end{table}",
        ]
    )
    output.with_suffix(".tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Energy summaries written to {output.with_suffix('.*')}")


if __name__ == "__main__":
    main()
