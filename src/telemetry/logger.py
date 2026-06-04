import json
import csv
import os
import re
from typing import Dict, Optional
from datetime import datetime

class TelemetryLogger:
    def __init__(self, hw_type: str, model_name: Optional[str] = None):
        self.hardware_profile = hw_type
        folder = model_name if model_name else hw_type
        folder = re.sub(r'[^a-zA-Z0-9_-]', '', folder.replace(' ', '_'))
        if not folder:
            folder = hw_type
        self.output_dir = f"data/reports/{folder}"
        os.makedirs(self.output_dir, exist_ok=True)

    def log_results(self, results: Dict):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._write_manifest(results, timestamp)
        self._write_csv(results, timestamp)
        self._write_iterations_csv(results, timestamp)
        self._write_drift_events_csv(results, timestamp)
        self._write_latex(results, timestamp)
        self._write_json(results, timestamp)

    def _write_drift_events_csv(self, results: Dict, timestamp: str):
        events = results.get("drift_events", [])
        if not events:
            return
        filepath = f"{self.output_dir}/drift_events_{timestamp}.csv"
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "phase", "api", "chaos_method", "reconciler", "iteration",
                "packet_idx", "source_field", "drifted_field",
                "chaos_sub_type", "reconciliation_status"
            ])
            writer.writeheader()
            for e in events:
                writer.writerow({
                    "phase": e["phase"],
                    "api": e["api"],
                    "chaos_method": e["chaos_method"],
                    "reconciler": e["reconciler"],
                    "iteration": e["iteration"],
                    "packet_idx": e["packet_idx"],
                    "source_field": e["source_field"],
                    "drifted_field": e.get("drifted_field", "") if e.get("drifted_field") else "",
                    "chaos_sub_type": e.get("chaos_sub_type", ""),
                    "reconciliation_status": e.get("reconciliation_status", "")
                })

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
            "repetitions": results.get("repetitions", 1),
            "total_duration_s": round(meta.get("total_duration_s", 0), 2),
            "total_packets": meta.get("total_packets", 0),
            "total_iterations": len(results.get("iterations", [])),
            "total_aggregates": len(results.get("matrix", [])),
            "total_drift_events": len(results.get("drift_events", [])),
            "cite_method": meta.get("cite_method", ""),
            "method_reference": meta.get("method_reference", ""),
            "phases": results.get("phases", [])
        }
        with open(filepath, 'w') as f:
            json.dump(manifest, f, indent=2)

    def _write_csv(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/matrix_results_{timestamp}.csv"
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "phase", "api", "chaos_method", "reconciler", "n_iterations",
                "accuracy_mean", "accuracy_std", "accuracy_min", "accuracy_max",
                "hosseini_mean", "hosseini_std", "hosseini_min", "hosseini_max",
                "latency_mean_ms", "latency_std_ms",
                "throughput_mean_pps", "throughput_std_pps",
                "throughput_min_pps", "throughput_max_pps",
                "total_time_mean_ms", "total_time_std_ms",
                "fast_path_latency_mean_ms", "fast_path_latency_std_ms",
                "gpu_latency_mean_ms", "gpu_latency_std_ms",
                "packets_clean_mean", "packets_drifted_mean",
                "batch_size"
            ])
            writer.writeheader()
            for row in results["matrix"]:
                writer.writerow({
                    "phase": row["phase"],
                    "api": row["api"],
                    "chaos_method": row["chaos_method"],
                    "reconciler": row["reconciler"],
                    "n_iterations": row["n_iterations"],
                    "accuracy_mean": row["accuracy"]["mean"],
                    "accuracy_std": row["accuracy"]["std"],
                    "accuracy_min": row["accuracy"]["min"],
                    "accuracy_max": row["accuracy"]["max"],
                    "hosseini_mean": row["hosseini_resilience"]["mean"],
                    "hosseini_std": row["hosseini_resilience"]["std"],
                    "hosseini_min": row["hosseini_resilience"]["min"],
                    "hosseini_max": row["hosseini_resilience"]["max"],
                    "latency_mean_ms": row["avg_latency_ms"]["mean"],
                    "latency_std_ms": row["avg_latency_ms"]["std"],
                    "throughput_mean_pps": row["throughput_pps"]["mean"],
                    "throughput_std_pps": row["throughput_pps"]["std"],
                    "throughput_min_pps": row["throughput_pps"]["min"],
                    "throughput_max_pps": row["throughput_pps"]["max"],
                    "total_time_mean_ms": row["total_time_ms"]["mean"],
                    "total_time_std_ms": row["total_time_ms"]["std"],
                    "fast_path_latency_mean_ms": row["fast_path_latency_ms"]["mean"],
                    "fast_path_latency_std_ms": row["fast_path_latency_ms"]["std"],
                    "gpu_latency_mean_ms": row["gpu_latency_ms"]["mean"],
                    "gpu_latency_std_ms": row["gpu_latency_ms"]["std"],
                    "packets_clean_mean": row["packets_clean"]["mean"],
                    "packets_drifted_mean": row["packets_drifted"]["mean"],
                    "batch_size": row["batch_size"]
                })

    def _write_iterations_csv(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/matrix_iterations_{timestamp}.csv"
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "phase", "api", "chaos_method", "reconciler", "iteration", "seed",
                "accuracy", "hosseini_resilience",
                "avg_latency_ms", "min_latency_ms", "max_latency_ms",
                "throughput_pps", "total_time_ms",
                "packets_processed", "packets_clean", "packets_drifted",
                "fast_path_latency_ms", "gpu_latency_ms",
                "batch_size", "drift_event_count"
            ])
            writer.writeheader()
            for it in results["iterations"]:
                writer.writerow({
                    "phase": it["phase"],
                    "api": it["api"],
                    "chaos_method": it["chaos_method"],
                    "reconciler": it["reconciler"],
                    "iteration": it["iteration"],
                    "seed": it["seed"],
                    "accuracy": it["accuracy"],
                    "hosseini_resilience": it["hosseini_resilience"],
                    "avg_latency_ms": it["avg_latency_ms"],
                    "min_latency_ms": it["min_latency_ms"],
                    "max_latency_ms": it["max_latency_ms"],
                    "throughput_pps": it["throughput_pps"],
                    "total_time_ms": it["total_time_ms"],
                    "packets_processed": it["packets_processed"],
                    "packets_clean": it["packets_clean"],
                    "packets_drifted": it["packets_drifted"],
                    "fast_path_latency_ms": it["fast_path_latency_ms"],
                    "gpu_latency_ms": it["gpu_latency_ms"],
                    "batch_size": it["batch_size"],
                    "drift_event_count": it["drift_event_count"]
                })

    def _write_latex(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/ieee_table_{timestamp}.tex"
        with open(filepath, 'w') as f:
            meta = results.get("run_metadata", {})
            hw = meta.get("hardware", {})
            reps = results.get("repetitions", 1)
            f.write(f"% Hosseini et al. (2016) Resilience Index — {reps} iterations per combination\n")
            f.write(f"% Hardware: {hw.get('model', 'unknown')} | VRAM: {hw.get('vram_gb', 0)} GB | Driver: {hw.get('driver', 'unknown')}\n")
            f.write(f"% CPU: {hw.get('cpu', 'unknown')} | Motherboard: {hw.get('motherboard', 'unknown')}\n")
            f.write(f"% Batch: {hw.get('batch_size', 1)} | Concurrent: {hw.get('concurrent_runs', 1)} | Iterations: {reps}\n\n")

            f.write("\\begin{table}[htbp]\n")
            f.write("\\caption{Aggregated Resilience Metrics ($n=" + str(reps) + "$ iterations) --- " + hw.get("model", self.hardware_profile) + "}\n")
            f.write("\\begin{tabular}{l l l r r r r}\n")
            f.write("\\hline\n")
            f.write("Phase & API & Reconciler & Accuracy & Hosseini Index & Throughput (pps) & Batch \\\\\n")
            f.write("\\hline\n")

            for row in results["matrix"]:
                phase = row["phase"].replace("_", "\\_")
                api = row["api"].replace("_", "\\_")
                rec = row["reconciler"].replace("_", "\\_")
                am = row["accuracy"]["mean"]
                as_ = row["accuracy"]["std"]
                hm = row["hosseini_resilience"]["mean"]
                hs = row["hosseini_resilience"]["std"]
                tm = row["throughput_pps"]["mean"]
                ts = row["throughput_pps"]["std"]
                f.write(f"{phase} & {api} & {rec} & ${am:.3f}\\pm{as_:.3f}$ & ${hm:.3f}\\pm{hs:.3f}$ & ${tm:.0f}\\pm{ts:.0f}$ & {row['batch_size']} \\\\\n")

            f.write("\\hline\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")

    def _write_json(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/full_results_{timestamp}.json"
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)