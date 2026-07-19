#!/usr/bin/env python3
"""
fetch_qpu_results.py — Retrieve and process completed IBM Quantum batch jobs.

Usage:
    python3 scripts/fetch_qpu_results.py --job-id d9dd55sjeosc73fhd94g --log data/reports/shadow_routing_10rep_quantum/run_1/shadow_log_TIMESTAMP.json
"""

import os
import sys
import json
import argparse
import numpy as np
from qiskit_ibm_runtime import QiskitRuntimeService

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.routing.quantum_router import QuantumRouter

def main():
    parser = argparse.ArgumentParser(description="Fetch and process QPU results")
    parser.add_argument("--job-id", type=str, required=True, help="IBM Quantum Job ID")
    parser.add_argument("--log", type=str, required=True, help="Original shadow log used for submission")
    parser.add_argument("--backend", type=str, default="ibm_quantum", help="Target Backend string used to save the suffix")
    parser.add_argument("--shots", type=int, default=1024, help="Number of shots")
    args = parser.parse_args()

    # Load shadow features
    with open(args.log, "r") as f:
        log_data = json.load(f)

    total_packets = len(log_data)
    print(f"Loaded {total_packets} shadow logged packet features.")

    # Retrieve credentials
    token = os.getenv("QISKIT_IBM_TOKEN") or os.getenv("IBM_QUANTUM_TOKEN")
    if not token and sys.stdin.isatty():
        import getpass
        token = getpass.getpass("Enter IBM Quantum API Key: ").strip()

    if not token:
        print("ERROR: QISKIT_IBM_TOKEN or IBM_QUANTUM_TOKEN must be set.")
        sys.exit(1)

    channel = os.getenv("QISKIT_IBM_CHANNEL") or "ibm_cloud"
    instance = os.getenv("QISKIT_IBM_INSTANCE") or "crn:v1:bluemix:public:quantum-computing:us-east:a/139dcf0745314450af23aa33e3f8029a:e8e44711-fb96-4664-bca6-9cee8b03bd90::"

    print(f"Connecting to IBM Quantum Service (Channel: {channel})...")
    service = QiskitRuntimeService(token=token, channel=channel, instance=instance)
    
    print(f"Retrieving job {args.job_id}...")
    job = service.job(args.job_id)
    status = job.status()
    print(f"Job Status: {status}")
    
    if status != "DONE":
        print("Job is not finished yet. Try again later.")
        sys.exit(1)
        
    print("Fetching results...")
    result = job.result()
    
    router = QuantumRouter(shots=args.shots)
    qpu_decisions = []
    
    # Process results identical to QuantumRouter.route_batch
    for idx in range(total_packets):
        pub_result = result[idx]
        reg_name = list(pub_result.data.keys())[0]
        counts = getattr(pub_result.data, reg_name).get_counts()
        
        best_bitstring = max(counts, key=counts.get)
        class_idx = int(best_bitstring, 2)
        if class_idx >= router.num_classes:
            class_idx = 2
        reconciler = router.RECONCILER_CLASSES[class_idx]
        qpu_decisions.append(reconciler)

    print("[QPU] Batch execution results decoded successfully.")
    
    # Compare emulator vs physical QPU decisions
    agreement_count = 0
    comparison_log = []
    
    for i in range(total_packets):
        emulator_decision = log_data[i]["emulator_decision"]
        match = (qpu_decisions[i] == emulator_decision)
        if match:
            agreement_count += 1
        comparison_log.append({
            "packet_idx": log_data[i]["packet_idx"],
            "features": log_data[i]["features"],
            "emulator_decision": emulator_decision,
            "qpu_decision": qpu_decisions[i],
            "agreement": match
        })

    agreement_rate = (agreement_count / total_packets) * 100 if total_packets > 0 else 0.0

    print("\n" + "=" * 60)
    print("  QPU EXECUTION RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Packets Replayed:   {total_packets}")
    print(f"Emulator/QPU Agreement:  {agreement_count} / {total_packets} ({agreement_rate:.2f}%)")
    print("=" * 60)

    # Save replay report
    timestamp = os.path.basename(args.log).replace("shadow_log_", "").replace(".json", "")
    suffix = "_IBM_QPU" if args.backend == "ibm_quantum" else ("_VLQ_QPU" if args.backend in ["vlq", "lumi_q"] else "")
    report_path = f"data/reports/live_f1/qpu_replay_report_{timestamp}{suffix}.json"
    
    report = {
        "log_source": args.log,
        "backend": args.backend,
        "shots": args.shots,
        "total_packets": total_packets,
        "agreement_rate": round(agreement_rate, 2),
        "results": comparison_log
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Replay comparison report saved to: {report_path}")

if __name__ == "__main__":
    main()
