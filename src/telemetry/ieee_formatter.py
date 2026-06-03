import json
import csv
from typing import Dict, List

class IEEEFormatter:
    @staticmethod
    def format_summary_table(results: Dict) -> str:
        latex = []
        latex.append("\\begin{table}[htbp]")
        latex.append("\\caption{Aggregated Resilience Metrics}")
        latex.append("\\begin{tabular}{l r r r r r}")
        latex.append("\\hline")
        latex.append("Reconciler & Avg Accuracy & Avg Latency & Avg Throughput & Batch Size & Total Runs \\\\")
        latex.append("\\hline")
        
        reconciler_stats = {}
        for row in results["matrix"]:
            rec = row["reconciler"]
            if rec not in reconciler_stats:
                reconciler_stats[rec] = {"accuracy": [], "latency": [], "throughput": [], "batch_size": []}
            reconciler_stats[rec]["accuracy"].append(row["accuracy"])
            reconciler_stats[rec]["latency"].append(row["avg_latency_ms"])
            reconciler_stats[rec]["throughput"].append(row["throughput_pps"])
            reconciler_stats[rec]["batch_size"].append(row["batch_size"])
        
        for rec, stats in reconciler_stats.items():
            avg_acc = sum(stats["accuracy"]) / len(stats["accuracy"])
            avg_lat = sum(stats["latency"]) / len(stats["latency"])
            avg_thr = sum(stats["throughput"]) / len(stats["throughput"])
            avg_batch = sum(stats["batch_size"]) / len(stats["batch_size"])
            total = len(stats["accuracy"])
            latex.append(f"{rec} & {avg_acc:.3f} & {avg_lat:.2f} & {avg_thr:.0f} & {avg_batch:.0f} & {total} \\\\")
        
        latex.append("\\hline")
        latex.append("\\end{tabular}")
        latex.append("\\end{table}")
        
        return "\n".join(latex)

    @staticmethod
    def format_hardware_comparison(all_results: List[Dict]) -> str:
        latex = []
        latex.append("\\begin{table}[htbp]")
        latex.append("\\caption{Hardware Platform Comparison}")
        latex.append("\\begin{tabular}{l r r r r}")
        latex.append("\\hline")
        latex.append("Hardware & Avg Accuracy & Avg Latency & Avg Throughput & Batch Size \\\\")
        latex.append("\\hline")
        
        for results in all_results:
            hw = results["hardware"]
            accuracies = [r["accuracy"] for r in results["matrix"]]
            latencies = [r["avg_latency_ms"] for r in results["matrix"]]
            throughputs = [r["throughput_pps"] for r in results["matrix"]]
            batch_sizes = [r["batch_size"] for r in results["matrix"]]
            
            avg_acc = sum(accuracies) / len(accuracies) if accuracies else 0
            avg_lat = sum(latencies) / len(latencies) if latencies else 0
            avg_thr = sum(throughputs) / len(throughputs) if throughputs else 0
            avg_batch = sum(batch_sizes) / len(batch_sizes) if batch_sizes else 0
            
            latex.append(f"{hw} & {avg_acc:.3f} & {avg_lat:.2f} & {avg_thr:.0f} & {avg_batch:.0f} \\\\")
        
        latex.append("\\hline")
        latex.append("\\end{tabular}")
        latex.append("\\end{table}")
        
        return "\n".join(latex)
