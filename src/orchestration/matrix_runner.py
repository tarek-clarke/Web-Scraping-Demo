import json
import time
import random
import hashlib
import numpy as np
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from ..chaos.injector import ChaosInjector
from ..reconciliation.engine import ReconciliationEngine
from ..telemetry.logger import TelemetryLogger

class MatrixRunner:
    def __init__(self, hardware_profile: Dict, concurrent_runs: int = 1, batch_size: int = 4,
                 repetitions: int = 3, chaos_rate: float = 0.05, only_api: str = None,
                 skip_reconcilers: List[str] = None, skip_chaos_methods: List[str] = None,
                 run_phases: List[str] = None, quantum_backend: str = "aer_simulator"):
        hw_type = hardware_profile.get("type", "cpu")
        hw_model = hardware_profile.get("model")
        self.hardware_type = hw_type
        self.hardware_profile = hardware_profile
        self.concurrent_runs = concurrent_runs
        self.batch_size = batch_size
        self.repetitions = repetitions
        self.chaos_injector = ChaosInjector(chaos_rate=chaos_rate)
        self.reconciliation_engine = ReconciliationEngine(hw_type, batch_size)
        self.telemetry = TelemetryLogger(hw_type, hw_model)
        self._drift_cache: Dict[str, List[Dict]] = {}
        self._sub_type_cache: Dict[str, Dict[int, str]] = {}
        self._results_lock = Lock()
        self._progress_count = 0
        self._progress_total = 0
        self.quantum_backend = quantum_backend

        self.apis = ["openf1", "finnhub", "spacex", "openweather", "clinical"]
        if only_api:
            self.apis = [only_api]

        self.chaos_methods = ["qwen", "json_manip", "schema_alter"]

        if skip_chaos_methods:
            self.chaos_methods = [m for m in self.chaos_methods if m not in set(skip_chaos_methods)]

        skip = set(skip_reconcilers or [])
        all_reconcilers = ["levenshtein", "regex", "bert", "gemma_e4b"]
        self.reconcilers = [r for r in all_reconcilers if r not in skip]

        all_phases = [
            ("fast", ["levenshtein", "regex"]),
            ("bert", ["bert"]),
            ("gemma", ["gemma_e4b"]),
            ("quantum", ["quantum_routed"]),
        ]
        self.phases = [
            (name, [r for r in recs if (r == "quantum_routed" or r not in skip)])
            for name, recs in all_phases
        ]
        if run_phases:
            self.phases = [(name, recs) for name, recs in self.phases if name in run_phases]
        self.phases = [(name, recs) for name, recs in self.phases if recs]
        
        # Initialize quantum components if quantum phase is selected
        self.quantum_routers = {}
        self.feature_extractor = None
        if any(name == "quantum" for name, _ in self.phases):
            try:
                from ..routing import FeatureExtractor
                self.feature_extractor = FeatureExtractor()
            except ImportError:
                print("[WARNING] Quantum routing modules not available. Have you installed requirements-quantum.txt?")

    def _get_quantum_router(self, api: str):
        """Lazily initialize and cache the quantum router for a specific API."""
        if api not in self.quantum_routers:
            try:
                from ..routing import QuantumRouter
                import os
                config_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "configs",
                    f"trained_router_{api}.json"
                )
                # Fall back to global parameters if API-specific parameters are missing
                if not os.path.exists(config_path):
                    config_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        "configs",
                        "trained_router_params.json"
                    )
                router = QuantumRouter(
                    backend=self.quantum_backend,
                    model_params_path=config_path if os.path.exists(config_path) else None
                )
                self.quantum_routers[api] = router
            except ImportError:
                self.quantum_routers[api] = None
        return self.quantum_routers[api]

    def _cache_key(self, api_packets: List[Dict], chaos_method: str, seed: int) -> str:
        h = hashlib.md5(str(len(api_packets)).encode()).hexdigest()
        return f"{api_packets[0]['source']}_{chaos_method}_{seed}_{h}"

    def _get_drifted(self, api_packets: List[Dict], chaos_method: str, seed: int) -> Tuple[List[Dict], Dict[int, str]]:
        key = self._cache_key(api_packets, chaos_method, seed)
        if key not in self._drift_cache:
            random.seed(seed)
            drifted = self.chaos_injector.inject(api_packets, force_method=chaos_method, seed=seed)
            sub_type_map = {}
            for i in range(len(api_packets)):
                sub_type_map[i] = self.chaos_injector.get_sub_type(i, seed)
            self._drift_cache[key] = drifted
            self._sub_type_cache[key] = sub_type_map
        
        import copy
        return copy.deepcopy(self._drift_cache[key]), self._sub_type_cache[key]

    def _get_ground_truth_status(self, src_field: str, dst_field: str, original_data: Dict, drifted_data: Dict) -> str:
        if not isinstance(dst_field, str):
            return "FAILURE"
        orig_keys = set(original_data.keys())
        drift_keys = set(drifted_data.keys())
        if dst_field not in drift_keys:
            return "FAILURE"
        if src_field in orig_keys and src_field not in drift_keys and dst_field in drift_keys:
            return "SUCCESS"
        if src_field in orig_keys and src_field in drift_keys:
            if orig_keys == drift_keys:
                return "SUCCESS"
            else:
                return "FALSE_POSITIVE"
        return "FAILURE"

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
            self._progress_count = 0
            self._progress_total = sum(
                1 for api in self.apis
                if any(p.get("source") == api for p in packets)
            ) * len(self.chaos_methods) * len(reconcilers)

            use_threads = phase_name != "gemma"
            iteration_data = {}

            if use_threads:
                with ThreadPoolExecutor(max_workers=self.concurrent_runs) as executor:
                    futures = []
                    for api in self.apis:
                        api_packets = [p for p in packets if p.get("source") == api]
                        if not api_packets:
                            print(f"  Skipping {api}: no packets found")
                            continue
                        for chaos_method in self.chaos_methods:
                            seed = random.randint(0, 2**31)
                            for reconciler in reconcilers:
                                future = executor.submit(
                                    self._run_combination,
                                    api_packets, api, chaos_method, reconciler,
                                    phase_name, 1, seed
                                )
                                futures.append(future)

                    for future in as_completed(futures):
                        it = future.result()
                        results["iterations"].append(it)
                        results["drift_events"].extend(it.pop("_drift_events", []))
                        key = (it["phase"], it["api"], it["chaos_method"], it["reconciler"])
                        if key not in iteration_data:
                            iteration_data[key] = []
                        iteration_data[key].append(it)
            else:
                for api in self.apis:
                    api_packets = [p for p in packets if p.get("source") == api]
                    if not api_packets:
                        print(f"  Skipping {api}: no packets found")
                        continue
                    for chaos_method in self.chaos_methods:
                        seed = random.randint(0, 2**31)
                        for reconciler in reconcilers:
                            it = self._run_combination(
                                api_packets, api, chaos_method, reconciler,
                                phase_name, 1, seed
                            )
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
        self._sub_type_cache.clear()
        self.telemetry.log_results(results)
        return results

    def _run_combination(self, packets: List[Dict], api: str, chaos_method: str,
                         reconciler: str, phase: str, iteration: int, seed: int) -> Dict:
        import copy
        packets = copy.deepcopy(packets)
        total_start = time.perf_counter()

        drifted, sub_type_map = self._get_drifted(packets, chaos_method, seed)

        fast_path_start = time.perf_counter()
        clean_indices = []
        drifted_indices = []
        original_data_list = []

        for idx, (orig, drift) in enumerate(zip(packets, drifted)):
            if orig == drift:
                clean_indices.append(idx)
            else:
                drifted_indices.append(idx)
                original_data_list.append((idx, orig.get("data", {}), drift.get("data", {})))

        fast_path_ms = (time.perf_counter() - fast_path_start) * 1000

        gpu_start = time.perf_counter()
        drift_events = []
        accuracies = []
        latencies = []

        if reconciler == "bert" and original_data_list:
            pairs = [(orig, drift) for _, orig, drift in original_data_list]
            rec_results = self.reconciliation_engine.reconcile_bert_batch(pairs)
            for (idx, orig_data, drift_data), rec_result in zip(original_data_list, rec_results):
                sub_type = sub_type_map.get(idx, "unknown")
                accuracies.append(rec_result["accuracy"])
                latencies.append(rec_result["latency_ms"])

                for src, dst in rec_result.get("mapped_fields", []):
                    status = self._get_ground_truth_status(src, dst, orig_data, drift_data)
                    drift_events.append({
                        "phase": phase, "api": api, "chaos_method": chaos_method,
                        "reconciler": reconciler, "iteration": iteration,
                        "packet_idx": idx, "source_field": src, "drifted_field": dst,
                        "chaos_sub_type": sub_type, "reconciliation_status": status,
                    })

                for src in rec_result.get("unmapped_fields", []):
                    drift_events.append({
                        "phase": phase, "api": api, "chaos_method": chaos_method,
                        "reconciler": reconciler, "iteration": iteration,
                        "packet_idx": idx, "source_field": src, "drifted_field": None,
                        "chaos_sub_type": sub_type, "reconciliation_status": "FAILURE",
                    })
        elif reconciler == "gemma_e4b" and original_data_list:
            pairs = [(orig, drift) for _, orig, drift in original_data_list]
            total_drift = len(pairs)
            label = f"{api}/{chaos_method}/{reconciler}"
            def _cb(i, total):
                print(f"    {label} packet {i+1}/{total}", flush=True)
            rec_results = self.reconciliation_engine.reconcile_gemma_batch(pairs, progress_cb=_cb)
            for (idx, orig_data, drift_data), rec_result in zip(original_data_list, rec_results):
                sub_type = sub_type_map.get(idx, "unknown")
                accuracies.append(rec_result["accuracy"])
                latencies.append(rec_result["latency_ms"])

                for src, dst in rec_result.get("mapped_fields", []):
                    status = self._get_ground_truth_status(src, dst, orig_data, drift_data)
                    drift_events.append({
                        "phase": phase, "api": api, "chaos_method": chaos_method,
                        "reconciler": reconciler, "iteration": iteration,
                        "packet_idx": idx, "source_field": src, "drifted_field": dst,
                        "chaos_sub_type": sub_type, "reconciliation_status": status,
                    })

                for src in rec_result.get("unmapped_fields", []):
                    drift_events.append({
                        "phase": phase, "api": api, "chaos_method": chaos_method,
                        "reconciler": reconciler, "iteration": iteration,
                        "packet_idx": idx, "source_field": src, "drifted_field": None,
                        "chaos_sub_type": sub_type, "reconciliation_status": "FAILURE",
                    })
        elif reconciler == "quantum_routed" and original_data_list:
            router = self._get_quantum_router(api)
            if not router:
                print(f"Skipping quantum_routed for {api} because quantum_router is not initialized")
            else:
                for batch_start in range(0, len(drifted_indices), self.batch_size):
                    batch_indices = drifted_indices[batch_start:batch_start + self.batch_size]
                    for bi, idx in enumerate(batch_indices):
                        di = batch_start + bi
                        orig_data = original_data_list[di][1]
                        drift_data = original_data_list[di][2]
                        sub_type = sub_type_map.get(idx, "unknown")

                        rec_result = self.reconciliation_engine.route_and_reconcile(
                            {"data": orig_data, "source": api},
                            {"data": drift_data, "source": api},
                            router,
                            self.feature_extractor
                        )
                        accuracies.append(rec_result["accuracy"])
                        latencies.append(rec_result["latency_ms"])
                        
                        actual_reconciler = rec_result["routing_decision"]

                        for src, dst in rec_result.get("mapped_fields", []):
                            status = self._get_ground_truth_status(src, dst, orig_data, drift_data)
                            drift_events.append({
                                "phase": phase, "api": api, "chaos_method": chaos_method,
                                "reconciler": actual_reconciler, "iteration": iteration,
                                "packet_idx": idx, "source_field": src, "drifted_field": dst,
                                "chaos_sub_type": sub_type, "reconciliation_status": status,
                                "quantum_routed": True,
                            })

                        for src in rec_result.get("unmapped_fields", []):
                            drift_events.append({
                                "phase": phase, "api": api, "chaos_method": chaos_method,
                                "reconciler": actual_reconciler, "iteration": iteration,
                                "packet_idx": idx, "source_field": src, "drifted_field": None,
                                "chaos_sub_type": sub_type, "reconciliation_status": "FAILURE",
                                "quantum_routed": True,
                            })
        else:
            for batch_start in range(0, len(drifted_indices), self.batch_size):
                batch_indices = drifted_indices[batch_start:batch_start + self.batch_size]
                for bi, idx in enumerate(batch_indices):
                    di = batch_start + bi
                    orig_data = original_data_list[di][1]
                    drift_data = original_data_list[di][2]
                    sub_type = sub_type_map.get(idx, "unknown")

                    rec_result = self.reconciliation_engine.reconcile(
                        {"data": orig_data},
                        {"data": drift_data},
                        reconciler
                    )
                    accuracies.append(rec_result["accuracy"])
                    latencies.append(rec_result["latency_ms"])

                    for src, dst in rec_result.get("mapped_fields", []):
                        status = self._get_ground_truth_status(src, dst, orig_data, drift_data)
                        drift_events.append({
                            "phase": phase, "api": api, "chaos_method": chaos_method,
                            "reconciler": reconciler, "iteration": iteration,
                            "packet_idx": idx, "source_field": src, "drifted_field": dst,
                            "chaos_sub_type": sub_type, "reconciliation_status": status,
                        })

                    for src in rec_result.get("unmapped_fields", []):
                        drift_events.append({
                            "phase": phase, "api": api, "chaos_method": chaos_method,
                            "reconciler": reconciler, "iteration": iteration,
                            "packet_idx": idx, "source_field": src, "drifted_field": None,
                            "chaos_sub_type": sub_type, "reconciliation_status": "FAILURE",
                        })

        gpu_ms = (time.perf_counter() - gpu_start) * 1000
        total_time = (time.perf_counter() - total_start) * 1000
        throughput = len(packets) / (total_time / 1000) if total_time > 0 else 0
        acc = sum(accuracies) / len(accuracies) if accuracies else 0.0
        hosseini = self._hosseini_resilience(acc, 1.0, total_time / 1000)

        result = {
            "phase": phase, "api": api, "chaos_method": chaos_method,
            "reconciler": reconciler, "iteration": iteration, "seed": seed,
            "accuracy": acc,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "min_latency_ms": min(latencies) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
            "total_time_ms": total_time,
            "throughput_pps": throughput,
            "packets_processed": len(packets),
            "packets_clean": len(clean_indices),
            "packets_drifted": len(drifted_indices),
            "fast_path_latency_ms": fast_path_ms,
            "gpu_latency_ms": gpu_ms,
            "batch_size": self.batch_size,
            "hosseini_resilience": hosseini,
            "drift_event_count": len(drift_events),
            "_drift_events": drift_events
        }

        with self._results_lock:
            self._progress_count += 1
            print(f"    [{self._progress_count}/{self._progress_total}] {api}/{chaos_method}/{reconciler} done ({total_time:.0f}ms, acc={acc:.2f})")

        return result

    def _aggregate(self, iters: List[Dict]) -> Dict:
        accs = [i["accuracy"] for i in iters]
        hoss = [i["hosseini_resilience"] for i in iters]
        lats = [i["avg_latency_ms"] for i in iters]
        thrs = [i["throughput_pps"] for i in iters]
        times = [i["total_time_ms"] for i in iters]
        events = [i["drift_event_count"] for i in iters]
        fp_lats = [i["fast_path_latency_ms"] for i in iters]
        gpu_lats = [i["gpu_latency_ms"] for i in iters]
        clean = [i["packets_clean"] for i in iters]
        drifted = [i["packets_drifted"] for i in iters]

        def stats(vals):
            return {
                "mean": float(np.mean(vals)) if vals else 0.0,
                "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                "min": float(np.min(vals)) if vals else 0.0,
                "max": float(np.max(vals)) if vals else 0.0
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
            "fast_path_latency_ms": stats(fp_lats),
            "gpu_latency_ms": stats(gpu_lats),
            "packets_clean": stats(clean),
            "packets_drifted": stats(drifted),
            "batch_size": iters[0]["batch_size"]
        }

    def _hosseini_resilience(self, degraded: float, baseline: float, duration_s: float) -> float:
        if baseline == 0 or duration_s == 0:
            return 0.0
        return float(np.clip((degraded * duration_s) / (baseline * duration_s), 0.0, 1.0))
