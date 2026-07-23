#!/usr/bin/env python3
"""
train_router.py — Train the QuantumRouter VQC model using historical benchmark data.
Generates training feature vectors (X) and target labels (y) based on optimal reconcilers,
trains the VQC circuit, and saves the parameters to configs/quantum_router_params.json.
"""

import os
import sys
import json
import random
import numpy as np

# SciPy / Qiskit compatibility monkeypatch for NumPy 1.24+
if not hasattr(np, "long"):
    np.long = int
if not hasattr(np, "ulong"):
    np.ulong = int

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.routing.quantum_router import QuantumRouter
from src.routing.feature_extractor import FeatureExtractor
from src.routing.training import RoutingTrainer
from src.chaos.json_chaos import JSONChaos
from src.chaos.schema_chaos import SchemaChaos

def generate_mock_packet(api: str, seq: int) -> dict:
    """Generates a base packet for the specified API to simulate original data."""
    if api == "openf1":
        return {
            "source": "openf1",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "driver_number": 1 + (seq % 5),
                "session_key": 11317,
                "lap_number": 10 + (seq % 20),
                "speed": 180.0 + (seq % 40),
                "throttle": 0.5 + ((seq % 10) / 20.0),
            }
        }
    elif api == "finnhub":
        return {
            "source": "finnhub",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "symbol": "AAPL",
                "price": 180.5 + (seq % 10),
                "volume": 10000 + (seq % 5000),
                "timestamp": 1718498000 + seq
            }
        }
    elif api == "spacex":
        return {
            "source": "spacex",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "flight_number": 100 + seq,
                "mission_name": f"Starlink-{seq}",
                "rocket_id": "falcon9",
                "launch_success": True
            }
        }
    elif api == "clinical":
        return {
            "source": "clinical",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "heart_rate": 72.0 + (seq % 10),
                "spo2": 98.0 - (seq % 2),
                "systolic_bp": 120.0 + (seq % 15),
                "diastolic_bp": 80.0 + (seq % 10),
                "respiratory_rate": 14.0 + (seq % 4)
            }
        }
    elif api == "hockey_nhl":
        return {
            "source": "hockey_nhl",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "game_id": 1000 + seq,
                "home_team": "BOS",
                "away_team": "NYR",
                "shots": 20 + (seq % 15),
                "penalties": seq % 8,
            }
        }
    elif api == "aviation_opensky":
        return {
            "source": "aviation_opensky",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "icao24": f"abc{seq:04d}",
                "callsign": f"FLT{seq:04d}",
                "altitude": 30000 + (seq % 3000),
                "velocity": 450 + (seq % 30),
                "heading": 180 + (seq % 45),
            }
        }
    elif api == "football_uefa":
        return {
            "source": "football_uefa",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "match_id": 5000 + seq,
                "home_team": "ARS",
                "away_team": "MCI",
                "possession_home": 48 + (seq % 6),
                "shots_on_target": 4 + (seq % 3),
            }
        }
    elif api == "smartcity_transit":
        return {
            "source": "smartcity_transit",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "vehicle_id": f"BUS-{seq:04d}",
                "route_id": 80 + (seq % 10),
                "delay_seconds": (seq % 12) * 5,
                "occupancy": 20 + (seq % 40),
            }
        }
    else:  # openweather
        return {
            "source": "openweather",
            "timestamp": "2026-07-04T00:00:00Z",
            "data": {
                "temp": 20.5 + (seq % 5),
                "humidity": 60 + (seq % 20),
                "wind_speed": 5.2 + (seq % 3),
                "description": "clear sky"
            }
        }

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Train Quantum Router VQC Model")
    parser.add_argument("--backend", type=str, default="aer_simulator",
                        help="Backend to run training on (e.g., aer_simulator, ibm_quantum)")
    parser.add_argument("--maxiter", type=int, default=40,
                        help="Maximum optimization iterations (default: 40)")
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="data/reports/quantum_MI250X_10rep_success",
        help="Benchmark results tree used to derive reconciler labels",
    )
    parser.add_argument(
        "--samples-per-group",
        type=int,
        default=100,
        help="Real benchmark packets sampled per (API, chaos method) pair",
    )
    parser.add_argument(
        "--packets-file",
        type=str,
        default="data/ingested/telemetry_clean_bench_22500.json",
        help="JSONL packet corpus used as the feature-generation pool",
    )
    parser.add_argument(
        "--max-packets-per-api",
        type=int,
        default=2500,
        help="Maximum corpus packets retained per API (default: all 2500)",
    )
    parser.add_argument(
        "--exclude-gemma",
        action="store_true",
        help="Exclude Gemma from the training labels and keep the router 3-class",
    )
    args = parser.parse_args()

    print("=== Training Quantum Router VQC Model ===")
    print(f"Target Backend: {args.backend}")
    print(f"Max Iterations: {args.maxiter}\n")
    
    # 1. Load historical benchmark data
    print(f"[Trainer] Loading benchmark data from {args.reports_dir}...")
    trainer = RoutingTrainer(args.reports_dir)
    try:
        trainer.load_data()
        print(trainer.summary())
    except Exception as e:
        print(f"ERROR: Failed to load benchmark data: {e}")
        sys.exit(1)
        
    best_df = trainer.compute_best_reconciler(exclude_gemma=args.exclude_gemma)
    
    # Create lookup map: (api, chaos_method) -> best reconciler class label
    reconciler_map = {}
    for _, row in best_df.iterrows():
        key = (row["api"], row["chaos_method"])
        reconciler_name = row["best_reconciler"]
        label = trainer.RECONCILER_LABEL_MAP.get(reconciler_name, 0)
        reconciler_map[key] = label
        print(f"  Mapping {key} -> {reconciler_name} (class {label})")

    # 2. Load the real nine-API corpus and generate packet-backed features.
    apis = [
        "openf1",
        "finnhub",
        "spacex",
        "openweather",
        "clinical",
        "hockey_nhl",
        "aviation_opensky",
        "football_uefa",
        "smartcity_transit",
    ]
    print(f"\n[Trainer] Loading packet corpus from {args.packets_file}...")
    packet_groups = {api: [] for api in apis}
    with open(args.packets_file, "r", encoding="utf-8") as packet_stream:
        for line in packet_stream:
            line = line.strip()
            if not line:
                continue
            packet = json.loads(line)
            api = packet.get("source")
            if api in packet_groups and len(packet_groups[api]) < args.max_packets_per_api:
                packet_groups[api].append(packet)
    corpus_count = sum(len(items) for items in packet_groups.values())
    print(f"[Trainer] Loaded {corpus_count} packets from the nine-API corpus")
    if corpus_count != 22500 and args.max_packets_per_api >= 2500:
        raise RuntimeError(
            f"Expected the 22,500-packet corpus, but loaded {corpus_count} active-API packets"
        )

    print("[Trainer] Generating packet-backed features and extracting VQC features...")
    extractor = FeatureExtractor()
    json_chaos = JSONChaos()
    schema_chaos = SchemaChaos()
    
    X_list = []
    y_list = []
    
    chaos_methods = ["qwen", "json_manip", "schema_alter"]
    
    # Sample deterministically from the full corpus for a balanced training
    # set.  The complete 22,500 packets are the source pool; repeating every
    # packet across every chaos method would inflate optimization cost without
    # adding independent labels.
    samples_per_group = args.samples_per_group
    rng = random.Random(20260723)
    
    for api in apis:
        for method in chaos_methods:
            label = reconciler_map.get((api, method))
            if label is None:
                raise KeyError(f"Missing benchmark label for {api}/{method}")
            
            source_packets = packet_groups[api]
            if not source_packets:
                raise RuntimeError(f"No packets found for active API {api}")
            selected = list(source_packets)
            rng.shuffle(selected)
            selected = selected[: min(samples_per_group, len(selected))]

            for packet in selected:
                orig = packet
                drifted = {
                    "source": orig["source"],
                    "timestamp": orig["timestamp"],
                    "data": orig["data"].copy()
                }
                
                # Apply appropriate chaos method
                data = drifted["data"]
                if method == "qwen":
                    # The Qwen pathway is represented here by a structured
                    # semantic perturbation that still exercises the feature
                    # extractor without depending on a large local model.
                    data = data.copy()
                    if "timestamp" in data:
                        data["timestamp"] = str(data["timestamp"])
                    if len(data) >= 2:
                        keys = list(data.keys())
                        data[keys[0]], data[keys[-1]] = data[keys[-1]], data[keys[0]]
                    modified = data
                elif method == "json_manip":
                    data = data.copy()
                    _, modified = json_chaos.inject_with_subtype(data)
                else:
                    data = data.copy()
                    _, modified = schema_chaos.alter_with_subtype(data)
                drifted["data"] = modified
                
                # Extract features
                try:
                    feat = extractor.extract(orig["data"], drifted["data"], api)
                    X_list.append(feat)
                    y_list.append(label)
                except Exception as e:
                    print(f"[WARNING] Feature extraction failed: {e}")
                    
    X_train = np.array(X_list)
    y_train = np.array(y_list)
    print(f"[Trainer] Generated X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
    
    # 3. Train the VQC model
    print(f"\n[Trainer] Initializing QuantumRouter and training VQC (COBYLA, maxiter={args.maxiter})...")
    
    # Handle secure token input for real hardware
    token = os.getenv("QISKIT_IBM_TOKEN") or os.getenv("IBM_QUANTUM_TOKEN")
    if token:
        os.environ["QISKIT_IBM_TOKEN"] = token
        if len(token) == 44 or token.startswith("ApiKey-"):
            os.environ["QISKIT_IBM_CHANNEL"] = "ibm_cloud"
            if "QISKIT_IBM_INSTANCE" not in os.environ:
                os.environ["QISKIT_IBM_INSTANCE"] = "crn:v1:bluemix:public:quantum-computing:us-east:a/139dcf0745314450af23aa33e3f8029a:d626fe8a-08ca-47ab-9412-7a93f954e2b0::"
        else:
            os.environ["QISKIT_IBM_CHANNEL"] = "ibm_quantum_platform"

    router = QuantumRouter(backend=args.backend, enable_gemma=not args.exclude_gemma)
    
    try:
        metrics = router.train(X_train, y_train, maxiter=args.maxiter)
        print("\n=== Training Complete ===")
        print(f"Training Accuracy: {metrics['train_accuracy']*100:.2f}%")
        print(f"Total Samples:     {metrics['n_samples']}")
        print(f"Classes Trained:   {metrics['n_classes']}")
        
        # Save trained parameters to configs/quantum_router_params.json
        config_dir = "configs"
        os.makedirs(config_dir, exist_ok=True)
        params_path = os.path.join(config_dir, "quantum_router_params.json")
        router.save_params(params_path)
        print(f"[Trainer] Trained VQC parameters saved to: {params_path}")
        
        # Also copy parameters to individual router config paths for all APIs
        for api in apis:
            api_path = os.path.join(config_dir, f"trained_router_{api}.json")
            router.save_params(api_path)
        print("[Trainer] Synchronized VQC parameters across all API endpoints.")
        
    except Exception as e:
        print(f"ERROR: VQC training failed: {e}")
        sys.exit(1)
    finally:
        # Securely wipe Qiskit credentials from memory
        for env_var in ["QISKIT_IBM_TOKEN", "QISKIT_IBM_CHANNEL", "QISKIT_IBM_INSTANCE", "IBM_QUANTUM_TOKEN"]:
            if env_var in os.environ:
                del os.environ[env_var]

if __name__ == "__main__":
    main()
