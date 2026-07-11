#!/usr/bin/env python3
"""
train_router.py — Train the QuantumRouter VQC model using historical benchmark data.
Generates training feature vectors (X) and target labels (y) based on optimal reconcilers,
trains the VQC circuit, and saves the parameters to configs/quantum_router_params.json.
"""

import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.routing.quantum_router import QuantumRouter
from src.routing.feature_extractor import FeatureExtractor
from src.routing.training import RoutingTrainer
from src.chaos.json_chaos import JSONChaos
from src.chaos.schema_chaos import SchemaChaos
from scripts.generate_synthetic_race import generate_telemetry_packet

def generate_mock_packet(api: str, seq: int) -> dict:
    """Generates a base packet for the specified API to simulate original data."""
    if api == "openf1":
        return generate_telemetry_packet(driver=1, session_key=11317)
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
    args = parser.parse_args()

    print("=== Training Quantum Router VQC Model ===")
    print(f"Target Backend: {args.backend}")
    print(f"Max Iterations: {args.maxiter}\n")
    
    # 1. Load historical benchmark data
    print("[Trainer] Loading benchmark data from data/reports/MI250X...")
    trainer = RoutingTrainer("data/reports/MI250X")
    try:
        trainer.load_data()
        print(trainer.summary())
    except Exception as e:
        print(f"ERROR: Failed to load benchmark data: {e}")
        sys.exit(1)
        
    best_df = trainer.compute_best_reconciler(exclude_gemma=True)
    
    # Create lookup map: (api, chaos_method) -> best reconciler class label
    reconciler_map = {}
    for _, row in best_df.iterrows():
        key = (row["api"], row["chaos_method"])
        reconciler_name = row["best_reconciler"]
        label = trainer.RECONCILER_LABEL_MAP.get(reconciler_name, 0)
        reconciler_map[key] = label
        print(f"  Mapping {key} -> {reconciler_name} (class {label})")

    # 2. Generate training features and labels
    print("\n[Trainer] Generating training packets and extracting VQC features...")
    extractor = FeatureExtractor()
    json_chaos = JSONChaos()
    schema_chaos = SchemaChaos()
    
    X_list = []
    y_list = []
    
    apis = ["openf1", "finnhub", "spacex", "openweather", "clinical"]
    chaos_methods = ["json_manip", "schema_alter"]
    
    # Generate 5 samples per (api, chaos_method) combination to build a solid training set (50 total samples)
    samples_per_group = 5
    seq = 0
    
    for api in apis:
        for method in chaos_methods:
            label = reconciler_map.get((api, method), 0) # Default to 0 (levenshtein)
            
            for _ in range(samples_per_group):
                seq += 1
                orig = generate_mock_packet(api, seq)
                drifted = {
                    "source": orig["source"],
                    "timestamp": orig["timestamp"],
                    "data": orig["data"].copy()
                }
                
                # Apply appropriate chaos method
                data = drifted["data"]
                if method == "json_manip":
                    _, modified = json_chaos.inject_with_subtype(data)
                else:
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

    router = QuantumRouter(backend=args.backend, enable_gemma=False)
    
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
        
        # Also copy parameters to individual router config paths for all 5 APIs
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
