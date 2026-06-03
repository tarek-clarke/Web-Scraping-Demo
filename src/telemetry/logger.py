import json
import csv
import time
from typing import Dict, List
from datetime import datetime

class TelemetryLogger:
    def __init__(self, hardware_profile: str):
        self.hardware_profile = hardware_profile
        self.output_dir = f"../../data/reports/{hardware_profile}"
        import os
        os.makedirs(self.output_dir, exist_ok=True)

    def log_results(self, results: Dict):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        self._write_csv(results, timestamp)
        self._write_latex(results, timestamp)
        self._write_json(results, timestamp)

    def _write_csv(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/matrix_results_{timestamp}.csv"
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "api", "chaos_method", "reconciler", "accuracy",
                "avg_latency_ms", "total_time_ms", "throughput_pps", "packets_processed", "batch_size"
            ])
            writer.writeheader()
            
            for row in results["matrix"]:
                writer.writerow(row)

    def _write_latex(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/ieee_table_{timestamp}.tex"
        
        with open(filepath, 'w') as f:
            f.write("\\begin{table}[htbp]\n")
            f.write("\\caption{Resilience Matrix Results - " + self.hardware_profile + "}\n")
            f.write("\\begin{tabular}{l l l r r r r r}\n")
            f.write("\\hline\n")
            f.write("API & Chaos & Reconciler & Accuracy & Latency (ms) & Time (ms) & Throughput (pps) & Batch Size \\\\\n")
            f.write("\\hline\n")
            
            for row in results["matrix"]:
                api = row["api"].replace("_", "\\_")
                chaos = row["chaos_method"].replace("_", "\\_")
                rec = row["reconciler"].replace("_", "\\_")
                f.write(f"{api} & {chaos} & {rec} & {row['accuracy']:.3f} & {row['avg_latency_ms']:.2f} & {row['total_time_ms']:.2f} & {row['throughput_pps']:.0f} & {row['batch_size']} \\\\\n")
            
            f.write("\\hline\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{table}\n")

    def _write_json(self, results: Dict, timestamp: str):
        filepath = f"{self.output_dir}/full_results_{timestamp}.json"
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)
