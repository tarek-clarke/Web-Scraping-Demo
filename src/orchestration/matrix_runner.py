import json
import time
import random
import hashlib
import numpy as np
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..chaos.injector import ChaosInjector
from ..reconciliation.engine import ReconciliationEngine
from ..telemetry.logger import TelemetryLogger

class MatrixRunner:
    def __init__(self, hardware_profile: Dict, concurrent_runs: int = 1, batch_size: int = 4, repetitions: int = 3):
        hw_type = hardware_profile.get("type", "cpu")
        hw_model = hardware_profile.get("model")
        self.hardware_type = hw_type
        self.hardware_profile = hardware_profile
        self.concurrent_runs = concurrent_runs
        self.batch_size = batch_size
        self.repetitions = repetitions
        self.chaos_injector = ChaosInjector(chaos_rate=0.05)
        self.reconciliation_engine = ReconciliationEngine(hw_type, batch_size)
        self.telemetry = TelemetryLogger(hw_type, hw_model)
        self._drift_cache: Dict[str, List[Dict]] = {}

        self.apis = ["openf1", "finnhub", "spacex", "openmeteo"]
        self.chaos_methods = ["gemma", "json_manip", "schema_alter"]
        self.phases = [
            ("fast", ["levenshtein", "regex"]),
            ("bert", ["bert"]),
            ("gemma_e4b", ["gemma_e4b"]),
            ("gemma_31b", ["gemma_31b"])
        ]

    def _cache_key(self, api_packets: List[Dict], chaos_method: str, seed: int) -> str:
        h = hashlib.md5(str(len(api_packets)).encode()).hexdigest()
        return f"{api_packets[0]['source']}_{chaos_method}_{seed}_{h}"

    def _get_drifted(self, api_packets: List[Dict], chaos_method: str, seed: int) -> List[Dict]:
        key = self._cache_key(api_packets, chaos_method, seed)
        if key not in self._drift_cache:
            random.seed(seed)
            self._drift_cache[key] = self.chaos_injector.inject(api_packets, force_method=chaos_method)
        return self._drift_cache[key]

    def run(self, packets: List[Dict]) -> Dict:
        results = {
            "timestamp": time.time(),
            "batch_size": self.batch_size,
            "concurrent_runs": self.concurrent_runs,
            "repetitions": self.repetitions,
            "phases": [],
            "iterations": [],
            "matrix": [],
            "drift_events": []
        }

        for phase_name, reconcilers in self.phases:
            print(f"\n=== Phase: {phase_name} ({reconcilers}) ===")
            phase_start = time.perf_counter()

            with ThreadPoolExecutor(max_workers=self.concurrent_runs) as executor:
                futures = []

                for api in self.apis:
                    api_packets = [p for p in packets if p.get("source") == api]
                    for chaos_method in self.chaos_methods:
                        seeds = [random.randint(0, 2**31) for _ in range(self.repetitions)]
                        for reconciler in reconcilers:
                            for rep in range(self.repetitions):
                                future = executor.submit(
                                    self._run_combination,
                                    api_packets, api, chaos_method, reconciler,
                                    phase_name, rep + 1, seeds[rep]
                                )
                                futures.append(future)

                iteration_data = {}
                for future in as_completed(futures):
                    it = future.result()
                    results["iterations"].append(it)
                    results["drift_events"].extend(it.pop("_drift_events", []))
                    key = (it["phase"], it["api"], it["chaos_method"], it["reconciler"])
                    if key not in iteration_data:
                        iteration_data[key] = []
                    iteration_data[key].append(it)

            for key, iters in iteration_data.items():
                agg = self._aggregate(iters)
                results["matrix"].append(agg)

            phase_time = (time.perf_counter() - phase_start) * 1000
            results["phases"].append({
                "name": phase_name,
                "reconcilers": reconcilers,
                "time_ms": phase_time
            })
            print(f"  Completed in {phase_time:.0f} ms")

        self._drift_cache.clear()
        self.telemetry.log_results(results)
        return results

    def _run_combination(self, packets: List[Dict], api: str, chaos_method: str,
                         reconciler: str, phase: str, iteration: int, seed: int) -> Dict:
        start_time = time.perf_counter()
        drifted = self._get_drifted(packets, chaos_method, seed)

        drift_events = []
        accuracies = []
        latencies = []
        all_mapped = []
        all_unmapped = []

        for idx, (orig, drift) in enumerate(zip(packets, drifted)):
            if orig != drift:
                rec_result = self.reconciliation_engine.reconcile(orig, drift, reconciler)
                accuracies.append(rec_result["accuracy"])
                latencies.append(rec_result["latency_ms"])
                all_mapped.append((idx, rec_result.get("mapped_fields", [])))
                all_unmapped.append((idx, rec_result.get("unmapped_fields", [])))

        for idx, mapped in all_mapped:
            for src, dst in mapped:
                drift_events.append({
                    "phase": phase, "api": api, "chaos_method": chaos_method,
                    "reconciler": reconciler, "iteration": iteration,
                    "packet_idx": idx, "source_field": src, "drifted_field": dst,
                })
        for idx, unmapped in all_unmapped:
            for src in unmapped:
                drift_events.append({
                    "phase": phase, "api": api, "chaos_method": chaos_method,
                    "reconciler": reconciler, "iteration": iteration,
                    "packet_idx": idx, "source_field": src, "drifted_field": None,
                })

        total_time = (time.perf_counter() - start_time) * 1000
        throughput = len(packets) / (total_time / 1000) if total_time > 0 else 0
        acc = sum(accuracies) / len(accuracies) if accuracies else 0.0
        hosseini = self._hosseini_resilience(acc, 1.0, total_time / 1000)

        return {
            "phase": phase, "api": api, "chaos_method": chaos_method,
            "reconciler": reconciler, "iteration": iteration, "seed": seed,
            "accuracy": acc,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "min_latency_ms": min(latencies) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
            "total_time_ms": total_time,
            "throughput_pps": throughput,
            "packets_processed": len(packets),
            "batch_size": self.batch_size,
            "hosseini_resilience": hosseini,
            "drift_event_count": len(drift_events),
            "_drift_events": drift_events
        }

    def _aggregate(self, iters: List[Dict]) -> Dict:
        accs = [i["accuracy"] for i in iters]
        hoss = [i["hosseini_resilience"] for i in iters]
        lats = [i["avg_latency_ms"] for i in iters]
        thrs = [i["throughput_pps"] for i in iters]
        times = [i["total_time_ms"] for i in iters]
        events = [i["drift_event_count"] for i in iters]

        def stats(vals):
            return {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "min": float(np.min(vals)),
                "max": float(np.max(vals))
            }

        return {
            "phase": iters[0]["phase"], "api": iters[0]["api"],
            "chaos_method": iters[0]["chaos_method"],
            "reconciler": iters[0]["reconciler"],
            "n_iterations": len(iters),
            "accuracy": stats(accs),
            "hosseini_resilience": stats(hoss),
            "avg_latency_ms": stats(lats),
            "throughput_pps": stats(thrs),
            "total_time_ms": stats(times),
            "drift_events": stats(events),
            "batch_size": iters[0]["batch_size"]
        }

    def _hosseini_resilience(self, degraded: float, baseline: float, duration_s: float) -> float:
        if baseline == 0 or duration_s == 0:
            return 0.0
        return float(np.clip((degraded * duration_s) / (baseline * duration_s), 0.0, 1.0))
