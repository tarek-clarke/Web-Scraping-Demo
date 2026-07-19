#!/usr/bin/env python3
"""
get_qpu_results.py — Retrieve job results from IBM Quantum/Cloud using a completed Job ID,
compare them with the emulator decisions in the shadow log, and save a report.

Usage:
    python3 scripts/get_qpu_results.py --job <JOB_ID> --log data/reports/live_f1/shadow_log_TIMESTAMP.json
"""

import os
import sys
import json
import argparse
import getpass
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.routing.quantum_router import QuantumRouter

def main():
    parser = argparse.ArgumentParser(description="Retrieve completed QPU job results and generate report")
    parser.add_argument("--job", type=str, required=True,
                        help="IBM Job ID (e.g., d944g9mvtlqs73fts4ng)")
    parser.add_argument("--log", type=str, required=True,
                        help="Path to the corresponding shadow_log_*.json file")
    args = parser.parse_args()

    if not os.path.exists(args.log):
        print(f"ERROR: Shadow log file not found: {args.log}")
        sys.exit(1)

    print(f"=== Retrieving QPU Job {args.job} ===")
    print(f"Shadow Log File: {args.log}")
    print()

    # Load shadow features
    with open(args.log, "r") as f:
        log_data = json.load(f)

    total_packets = len(log_data)
    print(f"Loaded {total_packets} shadow logged packet features.")

    # Secure API Key Entry
    token = os.getenv("QISKIT_IBM_TOKEN") or os.getenv("IBM_QUANTUM_TOKEN")
    if not token:
        token = getpass.getpass("Enter IBM Quantum API Key: ").strip()

    instance = os.getenv("QISKIT_IBM_INSTANCE") or "crn:v1:bluemix:public:quantum-computing:us-east:a/139dcf0745314450af23aa33e3f8029a:e8e44711-fb96-4664-bca6-9cee8b03bd90::"
    channel = "ibm_cloud" if (len(token) == 44 or token.startswith("ApiKey-")) else "ibm_quantum_platform"

    print("[QPU] Connecting to QiskitRuntimeService...")
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        service = QiskitRuntimeService(token=token, channel=channel, instance=instance)
        job = service.job(args.job)
        print(f"[QPU] Found job {args.job}. Status: {job.status()}")
        
        # Securely wipe token from memory
        token = None
        
        print("[QPU] Fetching job results...")
        result = job.result()
        print("[QPU] Results downloaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to retrieve job results: {e}")
        sys.exit(1)

    # Process results
    agreement_count = 0
    comparison_log = []

    # RECONCILER CLASSES mapping
    reconciler_classes = {
        0: "levenshtein",
        1: "regex",
        2: "bert",
        3: "gemma_e4b",
    }

    try:
        # SamplerV2 result format
        for idx, entry in enumerate(log_data):
            pub_result = result[idx]
            # Get counts for register 'c' (or the first available register)
            reg_name = list(pub_result.data.keys())[0]
            counts = getattr(pub_result.data, reg_name).get_counts()
            
            best_bitstring = max(counts, key=counts.get)
            class_idx = int(best_bitstring, 2)
            if class_idx >= 3:
                class_idx = 2  # clamp/default to BERT
            
            qpu_decision = reconciler_classes[class_idx]
            emulator_decision = entry["emulator_decision"]
            match = (qpu_decision == emulator_decision)
            
            if match:
                agreement_count += 1

            comparison_log.append({
                "packet_idx": entry["packet_idx"],
                "features": entry["features"],
                "emulator_decision": emulator_decision,
                "qpu_decision": qpu_decision,
                "counts": counts,
                "agreement": match
            })
    except Exception as e:
        # Try legacy job.result() counts if V2 structure fails
        print(f"[WARNING] V2 parsing failed ({e}). Trying legacy V1 format...")
        try:
            counts_list = result.get_counts()
            if not isinstance(counts_list, list):
                counts_list = [counts_list]
            
            for idx, entry in enumerate(log_data):
                counts = counts_list[idx]
                best_bitstring = max(counts, key=counts.get)
                class_idx = int(best_bitstring, 2)
                if class_idx >= 3:
                    class_idx = 2
                
                qpu_decision = reconciler_classes[class_idx]
                emulator_decision = entry["emulator_decision"]
                match = (qpu_decision == emulator_decision)
                
                if match:
                    agreement_count += 1

                comparison_log.append({
                    "packet_idx": entry["packet_idx"],
                    "features": entry["features"],
                    "emulator_decision": emulator_decision,
                    "qpu_decision": qpu_decision,
                    "counts": counts,
                    "agreement": match
                })
        except Exception as ex:
            print(f"ERROR: Failed to parse QPU results: {ex}")
            sys.exit(1)

    agreement_rate = (agreement_count / total_packets) * 100 if total_packets > 0 else 0.0

    print("\n" + "=" * 60)
    print("  QPU RESULTS RETRIEVED & COMPARED")
    print("=" * 60)
    print(f"Job ID:                   {args.job}")
    print(f"Total Packets:            {total_packets}")
    print(f"Emulator/QPU Agreement:  {agreement_count} / {total_packets} ({agreement_rate:.2f}%)")
    print("=" * 60)

    # Save replay report
    timestamp = os.path.basename(args.log).replace("shadow_log_", "").replace(".json", "")
    report_path = f"data/reports/live_f1/qpu_replay_report_{timestamp}.json"
    
    report = {
        "job_id": args.job,
        "log_source": args.log,
        "total_packets": total_packets,
        "agreement_rate": round(agreement_rate, 2),
        "results": comparison_log
    }

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Comparison report saved to: {report_path}")

if __name__ == "__main__":
    main()
