import json
import csv
import os
from typing import Dict
from datetime import datetime

class TelemetryLogger:
    def __init__(self, hardware_profile: str):
        self.hardware_profile = hardware_profile
        self.output_dir = f"../../data/reports/{hardware_profile}"
        os.makedirs(self.output_dir, exist_ok=True)

    def log_results(self, results: Dict):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        self._write_manifest(results, timestamp)
        self._write_csv(results, timestamp)
        self._write_latex(results, timestamp)
        self._write_json(results, timestamp)

    def _write_manifest(self, results: Dict, timestamp: str):
        meta = results.get("run_metadata", {})
        hw = meta.get("hardware", {})
        filepath = f"{self.output_dir}/manifest_{timestamp}.json"

        manifest = {
            "run_id": timestamp,
            "hardware_model": hw.get("model", "unknown"),
            "hardware_type": hw.get("type", "unknown"),
            "cpu": hw.get("cpu", "unknown"),
            "motherboard": hw.get("motherboard", "unknown"),
            "vram_total_gb": hw.get("vram_gb", 0),
            "vram_free_gb": hw.get("free_vram_gb", 0),
            "driver": hw.get("driver", "unknown"),
            "os": hw.get("os", "unknown"),
            "python_version": hw.get("python_version", "unknown"),
            "concurrent_runs": hw.get("concurrent_runs", 1),
            "batch_size": hw.get("batch_size", 1),
            "total_duration_s": round(meta.get("total_duration_s", 0), 2),
            "total_packets": meta.get("total_packets", 0),
            "cite_method": meta.get("cite_method", ""),
            "method_reference": meta.get("method_reference", ""),
            "phases": results.get("phases", []),
            "matrix_count": len(results.get("matrix", []))
        }

        with open(filepath, 'w') as f:
            json.dump(manifest, f, indent=2)

    def _write_csv(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/matrix_results_{timestamp}.csv"

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "phase", "api", "chaos_method", "reconciler",
                "accuracy", "avg_latency_ms", "min_latency_ms", "max_latency_ms",
                "total_time_ms", "throughput_pps", "packets_processed",
                "batch_size", "hosseini_resilience"
            ])
            writer.writeheader()

            for row in results["matrix"]:
                writer.writerow(row)

    def _write_latex(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/ieee_table_{timestamp}.tex"

        with open(filepath, 'w') as f:
            f.write("% Hosseini et al. (2016) Resilience Index\n")
            f.write("% Reference: Hosseini, S., Barker, K., & Ramirez-Marquez, J.E. (2016)\n")
            f.write("% Reliability Engineering & System Safety, 145, 47-61.\n\n")

            meta = results.get("run_metadata", {})
            hw = meta.get("hardware", {})
            f.write(f"% Hardware: {hw.get('model', 'unknown')} | VRAM: {hw.get('vram_gb', 0)} GB | Driver: {hw.get('driver', 'unknown')}\n")
            f.write(f"% Batch Size: {hw.get('batch_size', 1)} | Concurrent Runs: {hw.get('concurrent_runs', 1)}\n\n")

            f.write("\\begin{table}[htbp]\n")
            f.write("\\caption{Resilience Matrix Results --- " + hw.get("model", self.hardware_profile) + "}\n")
            f.write("\\begin{tabular}{l l l r r r r r r}\n")
            f.write("\\hline\n")
            f.write("Phase & API & Reconciler & Accuracy & Hosseini Index & Latency (ms) & Throughput (pps) & Batch Size \\\\\n")
            f.write("\\hline\n")

            for row in results["matrix"]:
                phase = row.get("phase", "??").replace("_", "\\_")
                api = row["api"].replace("_", "\\_")
                rec = row["reconciler"].replace("_", "\\_")
                hoss = row.get("hosseini_resilience", 0.0)
                f.write(f"{phase} & {api} & {rec} & {row['accuracy']:.3f} & {hoss:.3f} & {row['avg_latency_ms']:.2f} & {row['throughput_pps']:.0f} & {row['batch_size']} \\\\\n")

            f.write("\\hline\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")

    def _write_json(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/full_results_{timestamp}.json"
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
