import os
import csv
import json
import time
import concurrent.futures
from datetime import datetime

try:
    import cpp_accel
except ImportError:
    cpp_accel = None

from models.device_selector import get_device_info
from models.bert_model import BERTModel
from models.gemma_model import GemmaModel
from chaos.strategy import select_chaos
from drift_logging.drift_logger import DriftLogger
from resilience.scoring import ResilienceScoring
from semantic.compare import SchemaComparer

from api.finnhub import FinnhubAPI
from api.openmeteo import OpenMeteoAPI
from api.spacex import SpaceXAPI
from api.openf1 import OpenF1API

PACKET_PROFILES = {
    "short": 30000,
    "long": 3000000
}

FREQUENCY_PROFILES = {
    "100hz": 100,
    "1000hz": 1000,
    "1mhz": 1000000
}

CHAOS_LEVELS = {
    "high": 0.05,
    "medium": 0.01,
    "low": 0.005
}

class ExperimentRunner:
    def __init__(self):
        self.device_info = get_device_info()
        self.hardware = self.device_info["device"].upper()
        # Clean name for path compatibility
        self.hardware_model = self.device_info["model"].replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
        self.cloud = self.device_info["cloud"]
        
        # Shared models to optimize memory loading
        self.bert = BERTModel()
        self.gemma = GemmaModel()
        self.comparer = SchemaComparer(self.bert, self.gemma)
        self.logger = DriftLogger()

        # Map API keys to instances
        self.apis = {
            "finnhub": FinnhubAPI(),
            "openmeteo": OpenMeteoAPI(),
            "spacex": SpaceXAPI(),
            "openf1": OpenF1API()
        }

    def run_single_stream(self, api_name: str, packet_profile: str, 
                          frequency_profile: str, chaos_strategy: str, 
                          chaos_level: str, run_number: int, concurrency: int = 1) -> dict:
        """
        Executes a single experiment run.
        """
        api = self.apis[api_name]
        base_sample = api.fetch_data()
        
        n_packets = PACKET_PROFILES.get(packet_profile, 30000)
        target_hz = FREQUENCY_PROFILES.get(frequency_profile, 100)
        prob = CHAOS_LEVELS.get(chaos_level, 0.01)
        
        chaos_injector = select_chaos(chaos_strategy, prob, self.gemma)
        
        # Determine paths
        # Format: results/<hardware>/<cloud>/<api>/<profile>/<frequency>/<chaos>/run_<n>
        # If concurrency=2, use results/<hardware>/<cloud>/concurrency/<api>/...
        if concurrency == 2:
            dir_path = f"results/{self.hardware_model}/{self.cloud}/concurrency/{api_name}/{packet_profile}/{frequency_profile}/{chaos_strategy}"
        else:
            dir_path = f"results/{self.hardware_model}/{self.cloud}/{api_name}/{packet_profile}/{frequency_profile}/{chaos_strategy}"
            
        os.makedirs(dir_path, exist_ok=True)
        json_path = os.path.join(dir_path, f"run_{run_number}.json")
        csv_path = os.path.join(dir_path, f"run_{run_number}.csv")
        
        # Check if files exist (3-run rule check)
        if os.path.exists(json_path) and os.path.exists(csv_path):
            print(f"[Runner] Run {run_number} for {api_name} under {chaos_strategy}/{chaos_level} already exists. Skipping.")
            with open(json_path, "r") as f:
                return json.load(f)

        start_run_time = time.perf_counter()
        print(f"[Runner] Starting Run {run_number} for {api_name} (Packets: {n_packets}, Freq: {target_hz}Hz, Chaos: {chaos_strategy} at {chaos_level})")
        
        # Simulate packet ingestion and apply chaos
        # To handle 1 MHz / 3 million packets without taking hours, we simulate a tight looping packet stream,
        # apply the mutations, and run schema reconciliation on drifted samples.
        start_time = time.perf_counter()
        
        drift_events_detected = 0
        drift_events_recovered = 0
        total_drift_events = 0
        
        # Keep track of reconciler latencies and confidence scores
        latencies = {"levenshtein": [], "regex": [], "bert": [], "gemma": []}
        confidences = {"levenshtein": [], "regex": [], "bert": [], "gemma": []}
        
        canonical_key = base_sample["canonical"]
        canonical_keys = [canonical_key] # For single value API, we look at the main canonical key
        
        # Add some other noise candidate keys to canonical list for realistic choice
        canonical_keys.extend(["timestamp", "value", "id", "status", "ambient_humidity"])
        
        if cpp_accel is not None:
            # Accelerated C++ execution matrix
            cpp_res = cpp_accel.run_packet_loop(
                base_sample,
                n_packets,
                chaos_strategy,
                prob,
                chaos_injector,
                api_name,
                run_number,
                canonical_keys
            )
            total_drift_events = cpp_res["total_drift_events"]
            drift_events_detected = cpp_res["drift_events_detected"]
            
            # Flush batched logs to logger to reduce Python overhead
            for entry in cpp_res["batched_logs"]:
                self.logger.log_event(
                    api_source=api_name,
                    run_number=run_number,
                    chaos_strategy=chaos_strategy,
                    chaos_level=prob,
                    drift_type=entry["drift_type"],
                    original_field=entry["original_field"],
                    mutated_field=entry["mutated_field"],
                    metadata=entry["metadata"]
                )
                
            # Complete the deep-learning reconcilers (BERT, Gemma) in Python for the sampled keys
            for entry in cpp_res["reconciler_outcomes"]:
                drifted_key = entry["drifted_key"]
                lev_res = entry["levenshtein"]
                regex_res = entry["regex"]
                
                # Fetch BERT & Gemma matches
                bert_res = self.comparer.bert.reconcile(canonical_keys, drifted_key)
                gemma_res = self.comparer.gemma.reconcile(canonical_keys, drifted_key)
                
                # Aggregate metrics
                latencies["levenshtein"].append(lev_res["latency_ms"])
                confidences["levenshtein"].append(lev_res["confidence"])
                
                latencies["regex"].append(regex_res["latency_ms"])
                confidences["regex"].append(regex_res["confidence"])
                
                latencies["bert"].append(bert_res["latency_ms"])
                confidences["bert"].append(bert_res["confidence"])
                
                latencies["gemma"].append(gemma_res["latency_ms"])
                confidences["gemma"].append(gemma_res["confidence"])
                
                if gemma_res["match"] == canonical_key:
                    drift_events_recovered += 1
        else:
            # Tight packet loop simulation
            chunk_size = 1000
            for chunk in range(0, n_packets, chunk_size):
                # Process packets in batches
                current_chunk = min(chunk_size, n_packets - chunk)
                for _ in range(current_chunk):
                    # Generate sample packet
                    mutated = chaos_injector.apply_chaos(
                        base_sample, 
                        drift_logger=self.logger, 
                        run_number=run_number, 
                        api_source=api_name
                    )
                    
                    # Check if drift occurred by verifying if key or structure changed
                    drifted_key = None
                    for key in mutated.keys():
                        if key not in canonical_keys:
                            drifted_key = key
                            break
                            
                    if drifted_key:
                        total_drift_events += 1
                        
                        # Evaluate reconcilers on drifted keys (sample evaluation to stay highly performing)
                        if total_drift_events <= 100 or chunk % 50 == 0:
                            drift_events_detected += 1 # Any algorithm finding a match is a detection
                            
                            outcomes = self.comparer.compare_algorithms(canonical_keys, drifted_key)
                            
                            # Track confidence & latency
                            for alg in ["levenshtein", "regex", "bert", "gemma"]:
                                latencies[alg].append(outcomes[alg]["latency_ms"])
                                confidences[alg].append(outcomes[alg]["confidence"])
                                
                                # Recovery check (matching to exact canonical)
                                if outcomes[alg]["match"] == canonical_key:
                                    # Standard weight recovery
                                    if alg == "gemma":
                                        drift_events_recovered += 1
        
        elapsed = time.perf_counter() - start_time
        
        # T = throughput packets/sec
        throughput = n_packets / max(1e-6, elapsed)
        # Cap throughput simulation to frequency target
        throughput = min(throughput, float(target_hz))
        
        # Compute detection and recovery rates
        detection_rate = drift_events_detected / max(1, total_drift_events)
        recovery_score = drift_events_recovered / max(1, drift_events_detected)
        
        # Calculate P95 latency across all algorithms
        all_lats = []
        for alg_lats in latencies.values():
            all_lats.extend(alg_lats)
            
        all_lats.sort()
        p95_lat = all_lats[int(len(all_lats) * 0.95)] if all_lats else 5.0
        
        # Latency score normalized (using 10ms as high-performing baseline)
        latency_score = min(1.0, 10.0 / max(1e-6, p95_lat))
        
        # Calculate resilience scores P and P2
        resilience = ResilienceScoring.calculate_scores(
            throughput_pps=throughput,
            target_hz=target_hz,
            detection_rate=detection_rate,
            recovery_score=recovery_score,
            p95_latency_ms=p95_lat,
            baseline_p95_ms=10.0
        )
        
        # Calculate total run runtime
        total_runtime_sec = time.perf_counter() - start_run_time

        # Retrieve bootstrap info
        bootstrap_info = {}
        if os.path.exists(".initialized"):
            try:
                with open(".initialized", "r") as f:
                    bootstrap_info = json.load(f)
            except Exception:
                pass
        
        bootstrap_status = "cached"
        if bootstrap_info.get("fresh_install") is True:
            bootstrap_status = "fresh_install"
        bootstrap_time = bootstrap_info.get("bootstrap_duration_sec", 0.0)

        # Selected and actual device mapping
        selected_device = "gpu" if self.hardware in ["CUDA", "ROCM", "MPS"] else "cpu"
        hw_backend = self.device_info.get("hardware_backend", "CPU fallback")
        if hw_backend == "NVIDIA CUDA":
            actual_device = "CUDA"
        elif hw_backend == "AMD ROCm":
            actual_device = "ROCm"
        elif hw_backend == "Intel GPU":
            actual_device = "IntelGPU"
        elif hw_backend == "Apple Silicon MPS":
            actual_device = "MPS"
        else:
            actual_device = "CPU"

        # Format results
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api": api_name,
            "run_number": run_number,
            "packet_profile": packet_profile,
            "frequency_profile": frequency_profile,
            "chaos_strategy": chaos_strategy,
            "chaos_level": chaos_level,
            "concurrency": concurrency,
            "throughput_pps": throughput,
            "total_packets": n_packets,
            "elapsed_seconds": elapsed,
            "total_runtime_sec": total_runtime_sec,
            "selected_device": selected_device,
            "actual_device": actual_device,
            "hardware_model": self.device_info["model"],
            "cloud_platform": self.cloud,
            "bootstrap_status": bootstrap_status,
            "bootstrap_initialization_time": bootstrap_time,
            "total_drift_events": total_drift_events,
            "detection_rate": detection_rate,
            "recovery_score": recovery_score,
            "p95_latency_ms": p95_lat,
            "latency_score": latency_score,
            "resilience_P": resilience["P"],
            "resilience_P2": resilience["P2"],
            "averages": {
                "levenshtein_latency": sum(latencies["levenshtein"]) / max(1, len(latencies["levenshtein"])),
                "regex_latency": sum(latencies["regex"]) / max(1, len(latencies["regex"])),
                "bert_latency": sum(latencies["bert"]) / max(1, len(latencies["bert"])),
                "gemma_latency": sum(latencies["gemma"]) / max(1, len(latencies["gemma"])),
                "levenshtein_confidence": sum(confidences["levenshtein"]) / max(1, len(confidences["levenshtein"])),
                "regex_confidence": sum(confidences["regex"]) / max(1, len(confidences["regex"])),
                "bert_confidence": sum(confidences["bert"]) / max(1, len(confidences["bert"])),
                "gemma_confidence": sum(confidences["gemma"]) / max(1, len(confidences["gemma"]))
            }
        }
        
        # Save JSON
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2)
            
        # Save CSV
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(results.keys())
            writer.writerow([json.dumps(v) if isinstance(v, dict) else v for v in results.values()])
            
        # Flush buffered events to files before updating the runtime
        self.logger.flush()

        # Dynamically append/update runtime in drift logs
        self.logger.add_runtime_to_drift_logs(api_name, run_number, total_runtime_sec)

        return results

    def run_concurrent_streams(self, api_name: str, packet_profile: str, 
                               frequency_profile: str, chaos_strategy: str, 
                               chaos_level: str, run_number: int) -> dict:
        """
        Runs two streams in parallel and records concurrency metrics.
        """
        print(f"[Runner] Initiating Concurrent (2-Stream) Execution for {api_name}...")
        
        start_time = time.perf_counter()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(
                self.run_single_stream, api_name, packet_profile, frequency_profile, 
                chaos_strategy, chaos_level, run_number, concurrency=2
            )
            future2 = executor.submit(
                self.run_single_stream, api_name, packet_profile, frequency_profile, 
                chaos_strategy, chaos_level, run_number, concurrency=2
            )
            
            res1 = future1.result()
            res2 = future2.result()
            
        total_elapsed = time.perf_counter() - start_time
        
        # Combine & evaluate overhead
        overhead_percent = ((total_elapsed - max(res1["elapsed_seconds"], res2["elapsed_seconds"])) / max(1e-6, total_elapsed)) * 100.0
        
        concurrency_results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api": api_name,
            "run_number": run_number,
            "concurrency": 2,
            "total_elapsed_seconds": total_elapsed,
            "overhead_percent": max(0.0, overhead_percent),
            "stream_1": res1,
            "stream_2": res2
        }
        
        # Save to concurrency directory
        dir_path = f"results/{self.hardware_model}/{self.cloud}/concurrency/{api_name}/{packet_profile}/{frequency_profile}/{chaos_strategy}"
        os.makedirs(dir_path, exist_ok=True)
        
        with open(os.path.join(dir_path, f"concurrency_run_{run_number}.json"), "w") as f:
            json.dump(concurrency_results, f, indent=2)
            
        return concurrency_results
