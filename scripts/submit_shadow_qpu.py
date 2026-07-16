#!/usr/bin/env python3
"""
submit_shadow_qpu.py — Offline replay script to run live-logged shadow features 
on physical QPUs (IBM Quantum or LUMI-Q) in a single batch.

Usage:
    python3 scripts/submit_shadow_qpu.py --log data/reports/live_f1/shadow_log_TIMESTAMP.json --backend ibm_quantum
"""

import os
import sys
import json
import argparse
import numpy as np

# SciPy / Qiskit compatibility monkeypatch
if not hasattr(np, "long"):
    np.long = int
if not hasattr(np, "ulong"):
    np.ulong = int

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.routing.quantum_router import QuantumRouter
from src.routing.quantum_backends import VLQBackend

def main():
    parser = argparse.ArgumentParser(description="Submit logged shadow features to QPU")
    parser.add_argument("--log", type=str, required=True,
                        help="Path to the shadow_log_*.json file generated during the live run")
    parser.add_argument("--backend", type=str, default="ibm_quantum",
                        choices=["aer_simulator", "ibm_quantum", "lumi_q"],
                        help="Quantum hardware/simulator backend to target")
    parser.add_argument("--shots", type=int, default=1024,
                        help="Number of shots per circuit execution (default: 1024)")
    parser.add_argument("--model-params", type=str, default="configs/quantum_router_params.json",
                        help="Path to VQC model parameters JSON file (default: configs/quantum_router_params.json)")
    args = parser.parse_args()

    if not os.path.exists(args.log):
        print(f"ERROR: Log file not found: {args.log}")
        sys.exit(1)

    print(f"=== Replaying Shadow Log on Physical QPU ===")
    print(f"Log File: {args.log}")
    print(f"Target Backend: {args.backend}")
    print(f"Shots: {args.shots}")
    print()

    # Load shadow features
    with open(args.log, "r") as f:
        log_data = json.load(f)

    total_packets = len(log_data)
    print(f"Loaded {total_packets} shadow logged packet features.")

    # ── VLQ (Ostrava) backend path ────────────────────────────────────────────
    vlq_backend = None
    if args.backend == "vlq" or args.backend == "lumi_q":
        vlq_project  = os.getenv("VLQ_PROJECT", "")
        vlq_resource = os.getenv("VLQ_RESOURCE", "")

        # Load from .env.vlq if not already set
        if (not vlq_project or not vlq_resource) and os.path.exists(".env.vlq"):
            with open(".env.vlq") as ef:
                for line in ef:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            vlq_project  = os.getenv("VLQ_PROJECT", "")
            vlq_resource = os.getenv("VLQ_RESOURCE", "")

        if not vlq_project or not vlq_resource:
            print("ERROR: VLQ_PROJECT and VLQ_RESOURCE must be set (env vars or .env.vlq).")
            sys.exit(1)

        print(f"[Init] Connecting to VLQ backend (project={vlq_project}, resource={vlq_resource}) …")
        try:
            vlq_backend = VLQBackend(project=vlq_project, resource=vlq_resource)
            vlq_backend._init()   # triggers LEXIS browser auth
        except Exception as e:
            print(f"ERROR: Failed to connect to VLQ backend: {e}")
            sys.exit(1)
        print("[VLQ] Connected to VLQ QPU successfully.")

    else:
        # ── IBM Quantum path ──────────────────────────────────────────────────
        token = os.getenv("QISKIT_IBM_TOKEN") or os.getenv("IBM_QUANTUM_TOKEN")
        if not token and args.backend == "ibm_quantum" and sys.stdin.isatty():
            import getpass
            token = getpass.getpass("Enter IBM Quantum API Key: ").strip()

        if token:
            os.environ["QISKIT_IBM_TOKEN"] = token
            if len(token) == 44 or token.startswith("ApiKey-"):
                os.environ["QISKIT_IBM_CHANNEL"] = "ibm_cloud"
                if "QISKIT_IBM_INSTANCE" not in os.environ:
                    os.environ["QISKIT_IBM_INSTANCE"] = "crn:v1:bluemix:public:quantum-computing:us-east:a/139dcf0745314450af23aa33e3f8029a:d626fe8a-08ca-47ab-9412-7a93f954e2b0::"
            else:
                os.environ["QISKIT_IBM_CHANNEL"] = "ibm_quantum_platform"

        print(f"[Init] Initializing router backend '{args.backend}'...")
        try:
            router = QuantumRouter(backend=args.backend, shots=args.shots, model_params_path=args.model_params)
            router._init_backend()
        except Exception as e:
            print(f"ERROR: Failed to initialize QPU backend: {e}")
            for k in ["QISKIT_IBM_TOKEN", "QISKIT_IBM_CHANNEL", "QISKIT_IBM_INSTANCE"]:
                os.environ.pop(k, None)
            sys.exit(1)

    # Securely wipe the token from process environment and memory immediately
    if "QISKIT_IBM_TOKEN" in os.environ:
        del os.environ["QISKIT_IBM_TOKEN"]
    if "QISKIT_IBM_CHANNEL" in os.environ:
        del os.environ["QISKIT_IBM_CHANNEL"]
    if "QISKIT_IBM_INSTANCE" in os.environ:
        del os.environ["QISKIT_IBM_INSTANCE"]
    if "IBM_QUANTUM_TOKEN" in os.environ:
        del os.environ["IBM_QUANTUM_TOKEN"]
    token = None
    print("[QPU] Securely wiped API key from process environment memory.")

    print("[QPU] Compiling and transpiling circuits for execution...")

    # Extract features from log
    feature_list = []
    emulator_decisions = []

    for idx, entry in enumerate(log_data):
        feature_list.append(np.array(entry["features"]))
        emulator_decisions.append(entry["emulator_decision"])

    # Batch submit to QPU
    print(f"[QPU] Submitting batch of {total_packets} circuits to the QPU...")
    qpu_decisions = []

    try:
        if vlq_backend is not None:
            # ── VLQ path: use VLQBackend.execute_batch ────────────────────────
            from src.routing.quantum_router import QuantumRouter as _QR
            _tmp_router = _QR(backend="aer_simulator", shots=args.shots)
            from qiskit import transpile as _transpile
            circuits = []
            for feat in feature_list:
                qc = _tmp_router._build_vqc_circuit(feat)
                bound = _tmp_router._bind_features(qc, feat)
                circuits.append(bound)
            all_counts = vlq_backend.execute_batch(circuits, shots=args.shots)
            classes = {0: "levenshtein", 1: "regex", 2: "bert", 3: "gemma_e4b"}
            for counts in all_counts:
                best = max(counts, key=counts.get)
                idx = int(best, 2) % 4
                qpu_decisions.append(classes[idx])
            print("[VLQ] Batch execution completed successfully.")
        else:
            # ── IBM / Aer path ────────────────────────────────────────────────
            qpu_results = router.route_batch(np.array(feature_list))
            qpu_decisions = [res[0] for res in qpu_results]
            print("[QPU] Batch execution completed successfully.")
    except Exception as e:
        print(f"ERROR: QPU execution failed: {e}")
        print("Make sure your credentials are correct and you have access to the device.")
        sys.exit(1)

    # Compare emulator vs physical QPU decisions
    agreement_count = 0
    comparison_log = []
    
    for i in range(total_packets):
        match = (qpu_decisions[i] == emulator_decisions[i])
        if match:
            agreement_count += 1
        comparison_log.append({
            "packet_idx": log_data[i]["packet_idx"],
            "features": log_data[i]["features"],
            "emulator_decision": emulator_decisions[i],
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
    report_path = f"data/reports/live_f1/qpu_replay_report_{timestamp}.json"
    
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
