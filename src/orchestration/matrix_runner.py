import json
import time
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..chaos.injector import ChaosInjector
from ..reconciliation.engine import ReconciliationEngine
from ..telemetry.logger import TelemetryLogger

class MatrixRunner:
    def __init__(self, hardware_profile: str, concurrent_runs: int = 1, batch_size: int = 4):
        self.hardware_profile = hardware_profile
        self.concurrent_runs = concurrent_runs
        self.batch_size = batch_size
        self.chaos_injector = ChaosInjector(chaos_rate=0.05)
        self.reconciliation_engine = ReconciliationEngine(hardware_profile, batch_size)
        self.telemetry = TelemetryLogger(hardware_profile)

        self.apis = ["openf1", "finnhub", "spacex", "openmeteo"]
        self.chaos_methods = ["gemma", "json_manip", "schema_alter"]
        self.phases = [
            ("fast", ["levenshtein", "regex"]),
            ("bert", ["bert"]),
            ("gemma_e4b", ["gemma_e4b"]),
            ("gemma_31b", ["gemma_31b"])
        ]

    def run(self, packets: List[Dict]) -> Dict:
        results = {
            "hardware": self.hardware_profile,
            "timestamp": time.time(),
            "batch_size": self.batch_size,
            "concurrent_runs": self.concurrent_runs,
            "phases": [],
            "matrix": []
        }

        for phase_name, reconcilers in self.phases:
            print(f"\n=== Phase: {phase_name} ({reconcilers}) ===")
            phase_start = time.perf_counter()

            with ThreadPoolExecutor(max_workers=self.concurrent_runs) as executor:
                futures = []

                for api in self.apis:
                    api_packets = [p for p in packets if p.get("source") == api]
                    for chaos_method in self.chaos_methods:
                        for reconciler in reconcilers:
                            future = executor.submit(
                                self._run_combination,
                                api_packets, api, chaos_method, reconciler
                            )
                            futures.append(future)

                for future in as_completed(futures):
                    result = future.result()
                    results["matrix"].append(result)

            phase_time = (time.perf_counter() - phase_start) * 1000
            results["phases"].append({
                "name": phase_name,
                "reconcilers": reconcilers,
                "time_ms": phase_time
            })
            print(f"  Completed in {phase_time:.0f} ms")

        self.telemetry.log_results(results)
        return results

    def _run_combination(self, packets: List[Dict], api: str, chaos_method: str, reconciler: str) -> Dict:
        start_time = time.perf_counter()

        drifted = self.chaos_injector.inject(packets)

        accuracies = []
        latencies = []

        for i, (orig, drift) in enumerate(zip(packets, drifted)):
            if orig != drift:
                rec_result = self.reconciliation_engine.reconcile(orig, drift, reconciler)
                accuracies.append(rec_result["accuracy"])
                latencies.append(rec_result["latency_ms"])

        total_time = (time.perf_counter() - start_time) * 1000
        throughput = len(packets) / (total_time / 1000) if total_time > 0 else 0

        return {
            "api": api,
            "chaos_method": chaos_method,
            "reconciler": reconciler,
            "accuracy": sum(accuracies) / len(accuracies) if accuracies else 0.0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "total_time_ms": total_time,
            "throughput_pps": throughput,
            "packets_processed": len(packets),
            "batch_size": self.batch_size
        }
