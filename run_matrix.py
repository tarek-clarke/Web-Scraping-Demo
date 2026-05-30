import os
import sys
import subprocess
import json
from uuid import uuid4

def main():
    print("================================================================================")
    print(" STATEFUL MATRIX ORCHESTRATOR")
    print("================================================================================")
    
    # The optimized constrained matrix:
    # Scale: 10000
    # Probability: 0.01 (1%)
    # Frequency: 1000hz
    # Iterations: 3
    # APIs: finnhub, openmeteo, spacex, openf1
    # Generators: json, schema, gemma
    
    scale = 10000
    probability = 0.05
    frequency = 1000
    iterations = 3
    apis = ["finnhub", "openmeteo", "spacex", "openf1"]
    strategies = ["json", "schema", "gemma"]
    
    total_runs = len(apis) * len(strategies) * iterations
    
    state_file = "matrix_state.json"
    state = {"completed_runs": []}
    
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            try:
                state = json.load(f)
                print(f"[*] Loaded state file. Resuming matrix... ({len(state['completed_runs'])}/{total_runs} completed)")
            except json.JSONDecodeError:
                pass
                
    run_idx = 0
    for i in range(1, iterations + 1):
        for api in apis:
            for strategy in strategies:
                run_idx += 1
                
                # Unique key to track this exact combinatorial instance
                state_key = f"run_{i}_{api}_{strategy}"
                
                if state_key in state["completed_runs"]:
                    continue
                    
                print(f"\n================================================================================")
                print(f" [MATRIX RUN {run_idx}/{total_runs}] Iteration: {i} | API: {api} | Generator: {strategy}")
                print(f"================================================================================")
                
                run_id = uuid4().hex
                
                # 1. Generate Stream
                cmd_gen = [
                    "python", "chaos_generator/generate_chaos_dataset.py",
                    "--packets", str(scale),
                    "--chaos-probability", str(probability),
                    "--frequency-hz", str(frequency),
                    "--api", api,
                    "--strategy", strategy,
                    "--run-id", run_id,
                    "--run-number", str(i)
                ]
                
                print(f"[*] Generating streaming dataset...")
                subprocess.run(cmd_gen, check=True)
                
                dataset_path = f"chaos_generator/datasets/stream_{api}_{strategy}_{probability}_{run_id}.jsonl"
                
                # 2. Evaluate Stream
                cmd_eval = [
                    "python", "semantic_benchmark/run_semantic_benchmark.py",
                    "--dataset-path", dataset_path
                ]
                
                # Use PYTHONIOENCODING=utf-8 to prevent charmap crashes
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                
                print(f"[*] Evaluating streaming dataset...")
                subprocess.run(cmd_eval, env=env, check=True)
                
                # 3. Commit State
                state["completed_runs"].append(state_key)
                with open(state_file, "w") as f:
                    json.dump(state, f, indent=2)
                    
                # Optional: Delete dataset to save disk space
                # if os.path.exists(dataset_path):
                #     os.remove(dataset_path)

    print("\n[✓] MATRIX EXECUTION COMPLETE")

if __name__ == "__main__":
    main()
