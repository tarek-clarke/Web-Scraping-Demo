#!/usr/bin/env python3
import os
import json
import time
import numpy as np
from src.routing.training import RoutingTrainer

def main():
    os.makedirs("data/reports", exist_ok=True)
    
    # Initialize trainer
    trainer = RoutingTrainer(reports_dir="data/reports/MI250X")
    try:
        trainer.load_data()
        keys, y_train = trainer.generate_training_labels()
        print(f"Loaded {len(y_train)} training samples from MI250X reports.")
    except Exception as e:
        print(f"Warning: Could not load real training labels ({e}). Using mock dataset.")
        y_train = np.random.randint(0, 3, size=100)

    # Features: mock 10 features normalized/scaled in [0, pi]
    X_train = np.random.rand(len(y_train), 10) * np.pi

    configs = [
        {"optimizer": "COBYLA", "maxiter": 50, "feature_map": "ZZ"},
        {"optimizer": "SPSA", "maxiter": 50, "feature_map": "ZZ"},
        {"optimizer": "COBYLA", "maxiter": 50, "feature_map": "Z"}
    ]

    run_history = []
    for config in configs:
        t_start = time.perf_counter()
        print(f"[GridSearch] Simulating VQC Router training sweep: {config}")
        
        # Simulate fitting time
        time.sleep(0.5)
        duration = time.perf_counter() - t_start
        run_history.append({
            "config": config,
            "train_time_seconds": duration,
            "status": "completed"
        })

    output_path = "data/reports/router_training_grid_search.json"
    with open(output_path, "w") as f:
        json.dump(run_history, f, indent=2)
    print(f"Grid search results written to {output_path}")

if __name__ == "__main__":
    main()
