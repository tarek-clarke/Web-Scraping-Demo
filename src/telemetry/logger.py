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
        self._write_experiment_configuration_latex(results, timestamp)
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
                "chaos_sub_type", "reconciliation_status", "quantum_routed",
                "payload_source", "chaos_type", "selected_reconciler", "optimal_reconciler", "routing_decision_match",
                "qpu_execution_time_ms", "classical_simulation_baseline_ms", "quantum_loop_iterations",
                "gate_fidelity_average", "qubit_coherence_status_score",
                "gpu_energy_draw_joules", "cpu_energy_draw_joules"
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
                    "reconciliation_status": e.get("reconciliation_status", ""),
                    "quantum_routed": e.get("quantum_routed", False),
                    "payload_source": e.get("payload_source", e["api"]),
                    "chaos_type": e.get("chaos_type", e["chaos_method"]),
                    "selected_reconciler": e.get("selected_reconciler", e["reconciler"]),
                    "optimal_reconciler": e.get("optimal_reconciler", ""),
                    "routing_decision_match": e.get("routing_decision_match", ""),
                    "qpu_execution_time_ms": e.get("qpu_execution_time_ms", 0.0),
                    "classical_simulation_baseline_ms": e.get("classical_simulation_baseline_ms", 0.0),
                    "quantum_loop_iterations": e.get("quantum_loop_iterations", 1),
                    "gate_fidelity_average": e.get("gate_fidelity_average", 0.99),
                    "qubit_coherence_status_score": e.get("qubit_coherence_status_score", 0.98),
                    "gpu_energy_draw_joules": e.get("gpu_energy_draw_joules", 0.0),
                    "cpu_energy_draw_joules": e.get("cpu_energy_draw_joules", 0.0)
                })

    def _write_manifest(self, results: Dict, timestamp: str):
        meta = results.get("run_metadata", {})
        hw = meta.get("hardware", {})
        events = results.get("drift_events", [])
        ibm_jobs = results.get("ibm_qpu_jobs", [])
        
        # Calculate confusion matrix summaries
        false_positives = 0
        false_negatives = 0
        true_positives = 0
        true_negatives = 0
        
        qpu_time = 0.0
        sim_time = 0.0
        gpu_energy = 0.0
        cpu_energy = 0.0
        
        for e in events:
            qpu_time += e.get("qpu_execution_time_ms", 0.0)
            sim_time += e.get("classical_simulation_baseline_ms", 0.0)
            gpu_energy += e.get("gpu_energy_draw_joules", 0.0)
            cpu_energy += e.get("cpu_energy_draw_joules", 0.0)
            
            sel = e.get("selected_reconciler", e.get("reconciler", ""))
            opt = e.get("optimal_reconciler", "")
            
            if opt:
                is_heavy_sel = sel in ["bert", "gemma_e4b"]
                is_heavy_opt = opt in ["bert", "gemma_e4b"]
                
                if is_heavy_sel and not is_heavy_opt:
                    false_positives += 1
                elif not is_heavy_sel and is_heavy_opt:
                    false_negatives += 1
                elif is_heavy_sel and is_heavy_opt:
                    true_positives += 1
                else:
                    true_negatives += 1

        total_drifted_packets = len(set(e["packet_idx"] for e in events))

        # Event rows repeat a batch's routing telemetry for each affected
        # field, so they are not valid for aggregation.  IBM Runtime job
        # metrics are the authoritative remote-QPU measurements.
        ibm_qpu_charge_seconds = sum(
            float(job["qpu_charge_time_seconds"])
            for job in ibm_jobs
            if job.get("qpu_charge_time_seconds") is not None
        )
        ibm_circuit_execution_ns = sum(
            float(job["circuits_execution_time_ns"])
            for job in ibm_jobs
            if job.get("circuits_execution_time_ns") is not None
        )
        
        # Estimate carbon offset
        # Baseline pure Gemma: 0.6s at 200W = 120 Joules per packet
        baseline_joules = total_drifted_packets * 0.6 * 200.0
        actual_joules = gpu_energy + cpu_energy
        saved_joules = max(0.0, baseline_joules - actual_joules)
        saved_kwh = saved_joules / 3.6e6
        grid_intensity = 300.0  # gCO2/kWh
        carbon_offset_mg = saved_kwh * grid_intensity * 1000.0 * 1000.0

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
            "total_drift_events": len(events),
            "total_qpu_execution_time_ms": round(ibm_circuit_execution_ns / 1e6, 2) if ibm_jobs else round(qpu_time, 2),
            "total_classical_simulation_baseline_ms": round(sim_time, 2),
            "ibm_qpu_jobs": ibm_jobs,
            "ibm_qpu_job_count": len(ibm_jobs),
            "ibm_qpu_charge_time_seconds": round(ibm_qpu_charge_seconds, 6),
            "ibm_circuits_execution_time_ns": round(ibm_circuit_execution_ns, 2),
            "host_observed_metrics": meta.get("host_observed_metrics", {}),
            "energy_scope": {
                "ibm_qpu": "IBM Runtime usage/circuit time only; no remote QPU energy or carbon telemetry is available.",
                "host": "Locally observed CPU/GPU energy and estimated carbon during this client-side run."
            },
            "gpu_energy_draw_joules": round(gpu_energy, 2),
            "cpu_energy_draw_joules": round(cpu_energy, 2),
            "estimated_carbon_offset_mg": round(carbon_offset_mg, 2),
            "confusion_matrix": {
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "true_positives": true_positives,
                "true_negatives": true_negatives
            },
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

    def _write_experiment_configuration_latex(self, results: Dict, timestamp: str):
        """Write a paste-ready provenance table for the paper methodology."""
        filepath = f"{self.output_dir}/experiment_configuration_{timestamp}.tex"
        meta = results.get("run_metadata", {})
        host = meta.get("host_observed_metrics", {})
        ibm_jobs = results.get("ibm_qpu_jobs", [])

        def esc(value):
            return str(value).replace("_", "\\_")

        rows = [
            ("Execution backend", meta.get("execution_backend", "unknown")),
            ("Corpus", f"{meta.get('total_packets', 0)} packets / 9 APIs"),
            ("Chaos configuration", f"{meta.get('chaos_rate', 0):.0%}; qwen, json-manip, schema-alter"),
            ("Benchmark seed", meta.get("benchmark_seed", "unknown")),
            ("Logical VQC", f"{meta.get('logical_qubits', 12)} qubits; {meta.get('shots_per_circuit', 1024)} shots"),
            ("Host energy source", host.get("measurement_quality", "not recorded") + " / " + host.get("cpu_power_source", "not recorded")),
        ]
        if ibm_jobs:
            rows.extend([
                ("IBM QPU jobs", len(ibm_jobs)),
                ("IBM charged QPU time", f"{sum(float(j.get('qpu_charge_time_seconds') or 0) for j in ibm_jobs):.3f} s"),
            ])
        if meta.get("execution_backend") == "aer_gpu":
            rows.append(("Aer execution policy", "GPU required; CPU fallback disabled"))

        with open(filepath, "w") as f:
            f.write("% Paste-ready experiment configuration/provenance table\n")
            f.write("\\begin{table}[htbp]\n")
            f.write("\\caption{Hardware-comparable routing experiment configuration.}\n")
            f.write("\\label{tab:routing-experiment-configuration}\n")
            f.write("\\centering\n")
            f.write("\\begin{tabular}{ll}\n\\hline\n")
            f.write("Parameter & Value \\\\" + "\n\\hline\n")
            for key, value in rows:
                f.write(f"{esc(key)} & {esc(value)} \\\\" + "\n")
            f.write("\\hline\n\\end{tabular}\n\\end{table}\n")

    def _write_json(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/full_results_{timestamp}.json"
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, cls=NpEncoder)

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)
