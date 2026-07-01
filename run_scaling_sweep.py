#!/usr/bin/env python3
import time
import json
import os
import numpy as np

try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False

def run_bench(qubits, reps, device='GPU'):
    if not QISKIT_AVAILABLE:
        raise ImportError("Qiskit or Qiskit Aer is not installed.")
    
    qc = QuantumCircuit(qubits)
    for r in range(reps):
        for i in range(qubits):
            qc.rx(np.random.rand() * np.pi, i)
        for i in range(qubits - 1):
            qc.cx(i, i+1)
    qc.measure_all()
    
    sim = AerSimulator(device=device)
    t_start = time.perf_counter()
    transpiled = transpile(qc, sim)
    sim.run(transpiled, shots=1024).result()
    return time.perf_counter() - t_start

def main():
    os.makedirs("data/reports", exist_ok=True)
    if not QISKIT_AVAILABLE:
        print("ERROR: Qiskit or Qiskit Aer not installed. Cannot run scaling sweep.")
        return

    results = []
    print("=== Starting Qiskit GPU Simulator Scaling Sweep ===")
    for q in [8, 12, 16, 20]:
        for r in [1, 2, 3]:
            try:
                dur = run_bench(q, r, device='GPU')
                print(f"[Sweep] Qubits: {q}, Reps: {r} -> GPU Sim Time: {dur:.4f}s")
                results.append({"qubits": q, "reps": r, "time_seconds": dur})
            except Exception as e:
                print(f"[Sweep] Failed Qubits: {q}, Reps: {r} -> {e}")

    output_path = "data/reports/quantum_gpu_scaling_sweep.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {output_path}")

if __name__ == "__main__":
    main()
