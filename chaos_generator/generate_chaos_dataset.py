import os
import sys
import json
import csv
import argparse
import random
from uuid import uuid4

# Allow importing from root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.finnhub import FinnhubAPI
from api.openmeteo import OpenMeteoAPI
from api.spacex import SpaceXAPI
from api.openf1 import OpenF1API
from chaos_generator.chaos.strategy import select_chaos

def parse_args():
    parser = argparse.ArgumentParser(description="Procedural Chaos Dataset Generator")
    parser.add_argument("--output-dir", default="chaos_generator/datasets", help="Directory to save static datasets")
    parser.add_argument("--runs-per-config", type=int, default=5, help="Number of mutated samples per configuration")
    parser.add_argument("--levels", nargs="+", default=["5"], help="Chaos intensity levels (e.g. 5)")
    parser.add_argument("--strategies", nargs="+", default=["json", "schema", "gemma"], help="Chaos strategies to apply")
    return parser.parse_args()

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    apis = {
        "finnhub": FinnhubAPI(),
        "openmeteo": OpenMeteoAPI(),
        "spacex": SpaceXAPI(),
        "openf1": OpenF1API(),
    }

    print(f"[*] Starting procedural chaos generation...")
    print(f"[*] Strategies: {args.strategies}")
    print(f"[*] Intensity levels: {args.levels}")
    print(f"[*] Runs per config: {args.runs_per_config}")

    dataset = []
    
    # Fetch baseline data from APIs once to ensure consistency
    baselines = {}
    for name, api in apis.items():
        try:
            baselines[name] = api.fetch_data()
            print(f"[✓] Fetched base data for API '{name}' successfully.")
        except Exception as e:
            print(f"[!] Warning: failed to fetch live data for {name} ({e}). Using mock/static fallback.")
            # Standard fallback is handled inside fetch_data, so this should not be reached normally
            baselines[name] = {"price": 100.0, "canonical": "price"}

    # Generate mutations
    for api_name, base_data in baselines.items():
        for strategy in args.strategies:
            for level in args.levels:
                for run_num in range(1, args.runs_per_config + 1):
                    # Select and run chaos
                    try:
                        chaos_engine = select_chaos(strategy, level)
                        event_id = uuid4().hex
                        run_id = uuid4().hex
                        
                        # Apply chaos
                        mutated, drift_type, _ = chaos_engine(
                            base_data, 
                            drift_logger=None, 
                            run_number=run_num, 
                            api_source=api_name,
                            run_id=run_id,
                            event_id=event_id
                        )
                        
                        # Fallback classification if drift_type was not logged
                        if drift_type is None:
                            drift_type = "none"

                        record = {
                            "sample_id": f"sample_{uuid4().hex[:12]}",
                            "api_name": api_name,
                            "chaos_strategy": strategy,
                            "chaos_level": level,
                            "run_number": run_num,
                            "run_id": run_id,
                            "event_id": event_id,
                            "drift_type": drift_type,
                            "original_payload": base_data,
                            "mutated_payload": mutated,
                            "drift_present": (drift_type != "none" and drift_type is not None)
                        }
                        dataset.append(record)
                    except Exception as e:
                        print(f"[!] Error mutating {api_name} with {strategy} level {level}: {e}")

    # Write output as JSON
    json_path = os.path.join(args.output_dir, "chaos_dataset.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    print(f"[✓] Procedural chaos dataset written as JSON to: {json_path}")

    # Write flat aggregate CSV summary
    csv_path = os.path.join(args.output_dir, "chaos_dataset_summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "sample_id", 
            "api_name", 
            "chaos_strategy", 
            "chaos_level", 
            "run_number", 
            "drift_type", 
            "drift_present"
        ])
        for record in dataset:
            writer.writerow([
                record["sample_id"],
                record["api_name"],
                record["chaos_strategy"],
                record["chaos_level"],
                record["run_number"],
                record["drift_type"],
                record["drift_present"]
            ])
    print(f"[✓] Aggregate summary written as CSV to: {csv_path}")
    print(f"[✓] Generated a total of {len(dataset)} samples.")

if __name__ == "__main__":
    main()
