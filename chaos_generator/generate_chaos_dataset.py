import os
import sys
import json
import argparse
import random
import time
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.finnhub import FinnhubAPI
from api.openmeteo import OpenMeteoAPI
from api.spacex import SpaceXAPI
from api.openf1 import OpenF1API
from chaos_generator.chaos.strategy import select_chaos

def parse_args():
    parser = argparse.ArgumentParser(description="Procedural Chaos Streaming Dataset Generator")
    parser.add_argument("--output-dir", default="chaos_generator/datasets", help="Directory to save datasets")
    parser.add_argument("--packets", type=int, default=10000, help="Number of packets per run")
    parser.add_argument("--chaos-probability", type=float, default=0.01, help="Probability of chaos injection (e.g. 0.01 for 1%)")
    parser.add_argument("--api", type=str, default="finnhub", help="API Source to simulate")
    parser.add_argument("--strategy", type=str, default="json", help="Chaos strategy to apply")
    parser.add_argument("--frequency-hz", type=int, default=1000, help="Simulated ingress frequency (hz)")
    parser.add_argument("--run-id", type=str, default=None, help="Run UUID")
    parser.add_argument("--run-number", type=int, default=1, help="Run number iteration")
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

    if args.api not in apis:
        raise ValueError(f"Unknown API: {args.api}")

    api = apis[args.api]
    
    try:
        base_data = api.fetch_data()
    except Exception as e:
        print(f"[!] Warning: failed to fetch live data for {args.api} ({e}). Using mock/static fallback.")
        base_data = {"price": 100.0, "canonical": "price"}

    run_id = args.run_id if args.run_id else uuid4().hex
    
    out_filename = f"stream_{args.api}_{args.strategy}_{args.chaos_probability}_{run_id}.jsonl"
    jsonl_path = os.path.join(args.output_dir, out_filename)

    chaos_engine = select_chaos(args.strategy, args.chaos_probability)
    
    # Calculate simulated delay per packet
    delay_s = 1.0 / args.frequency_hz
    current_sim_time = time.time()

    print(f"[*] Starting NDJSON stream generation for {args.api} ({args.packets} packets, {args.chaos_probability*100}% chaos, {args.frequency_hz}hz)...")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for i in range(args.packets):
            event_id = uuid4().hex
            current_sim_time += delay_s
            timestamp_iso = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(current_sim_time)) + f".{int((current_sim_time % 1) * 1000):03d}Z"
            
            # Decide if we apply chaos probabilistically
            if random.random() < args.chaos_probability:
                try:
                    mutated, drift_type, _ = chaos_engine(
                        base_data, 
                        drift_logger=None, 
                        run_number=args.run_number, 
                        api_source=args.api,
                        run_id=run_id,
                        event_id=event_id
                    )
                    if drift_type is None:
                        drift_type = "none"
                except Exception as e:
                    # Fallback to pristine if chaos fails
                    mutated = base_data
                    drift_type = "none"
            else:
                mutated = base_data
                drift_type = "none"

            record = {
                "packet_id": f"pkt_{uuid4().hex[:12]}",
                "run_id": run_id,
                "run_number": args.run_number,
                "timestamp": timestamp_iso,
                "workload_scale": args.packets,
                "simulated_frequency": f"{args.frequency_hz}hz",
                "api_profile": args.api,
                "chaos_probability": args.chaos_probability,
                "chaos_strategy": args.strategy,
                "drift_type": drift_type,
                "drift_present": (drift_type != "none"),
                "target_key": base_data.get("canonical", list(base_data.keys())[0]),
                "original_payload": base_data,
                "mutated_payload": mutated
            }
            
            f.write(json.dumps(record) + "\n")
            
            if (i+1) % 1000 == 0:
                print(f"    - Generated {i+1}/{args.packets} packets...")

    print(f"[✓] NDJSON stream generated: {jsonl_path}")

if __name__ == "__main__":
    main()
