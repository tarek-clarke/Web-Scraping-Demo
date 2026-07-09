"""
train_vqc.py — Train VQC without scipy. Uses simple hill-climbing optimizer.
"""
import json, sys, os, random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_feature_extractor import QueryFeatureExtractor

SIMPLE_PREFIXES = {"fact", "sent", "summ", "ner"}
COMPLEX_PREFIXES = {"math", "debug", "logic", "codegen"}

def load_training_data():
    tasks = json.load(open("tasks_stress.json"))
    extractor = QueryFeatureExtractor()
    features, labels = [], []
    for task in tasks:
        prefix = task["task_id"].split("_")[0]
        features.append(extractor.extract(task["prompt"]))
        labels.append(0 if prefix in SIMPLE_PREFIXES else 1)
    return np.array(features), np.array(labels)

def build_and_run(features, params, backend, shots=512):
    from qiskit.circuit import QuantumCircuit
    from qiskit.circuit.library import ZZFeatureMap, RealAmplitudes
    from qiskit import transpile

    fm = ZZFeatureMap(feature_dimension=10, reps=2)
    ansatz = RealAmplitudes(num_qubits=10, reps=3)
    qc = QuantumCircuit(10, 1)
    qc.compose(fm, qubits=list(range(10)), inplace=True)
    qc.compose(ansatz, qubits=list(range(10)), inplace=True)
    qc.measure(0, 0)

    fm_params = sorted([p for p in qc.parameters if p.name.startswith("x")], key=lambda p: p.name)
    an_params = sorted([p for p in qc.parameters if not p.name.startswith("x")], key=lambda p: p.name)

    all_p = {}
    for p, v in zip(fm_params, features):
        all_p[p] = float(v)
    for p, v in zip(an_params, params):
        all_p[p] = float(v)

    bound = qc.assign_parameters(all_p)
    transpiled = transpile(bound, backend)
    job = backend.run(transpiled, shots=shots)
    counts = job.result().get_counts()
    return counts.get("1", 0) / shots

def train():
    from qiskit_aer import AerSimulator
    from qiskit.circuit.library import RealAmplitudes

    features, labels = load_training_data()
    print(f"Training: {len(features)} samples ({sum(labels)} complex, {len(labels)-sum(labels)} simple)")

    backend = AerSimulator()
    ansatz = RealAmplitudes(num_qubits=10, reps=3)
    num_params = len(ansatz.parameters)
    print(f"VQC: 10 qubits, {num_params} trainable parameters")

    def cost(params):
        losses = []
        for feat, label in zip(features, labels):
            pred = build_and_run(feat, params, backend, shots=128)
            losses.append((pred - label) ** 2)
        return sum(losses) / len(losses)

    print("Optimizing via hill climbing (30 iterations)...")
    best_params = np.zeros(num_params)
    best_cost = cost(best_params)
    print(f"  Initial cost: {best_cost:.4f}")

    for iteration in range(30):
        candidate = best_params + np.random.randn(num_params) * 0.1
        c = cost(candidate)
        if c < best_cost:
            best_cost = c
            best_params = candidate
            print(f"  Iter {iteration}: cost={c:.4f} (improved)")

    print(f"Final cost: {best_cost:.4f}")

    correct = 0
    for feat, label in zip(features, labels):
        pred = build_and_run(feat, best_params, backend, shots=512)
        if (1 if pred > 0.5 else 0) == label:
            correct += 1
    print(f"Training accuracy: {correct/len(labels):.2%}")

    params_dict = {p.name: float(best_params[i]) for i, p in enumerate(ansatz.parameters)}
    with open("track1_agent/vqc_parameters.json", "w") as f:
        json.dump(params_dict, f, indent=2)
    print("Parameters saved to track1_agent/vqc_parameters.json")
    return params_dict

if __name__ == "__main__":
    train()
