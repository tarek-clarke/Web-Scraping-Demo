#!/usr/bin/env python3
"""Multi-start training and selection for the canonical 13-qubit router.

Training is simulator-only.  Physical QPU minutes are reserved for the frozen
held-out evaluation.  Run independent starts in parallel (for example as a
LUMI Slurm array), then select exactly once using validation macro-F1.  The
held-out test split is evaluated only after the winner is selected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.routing.canonical_vqc import (
    ABSTAIN_CLASS_INDEX,
    ABSTAIN_CLASS_NAME,
    CIRCUIT_ID,
    DEFAULT_CLASS_NAMES,
    DEFAULT_FEATURE_COUNT,
    DEFAULT_REPS,
    ROUTING_OUTPUT_SHAPE,
    build_unitary_circuit,
    model_from_weights,
    qnn_interpret,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_metadata() -> Dict[str, object]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", *args],
                cwd=REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return "unknown"

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "dirty": bool(
            run("status", "--porcelain", "--untracked-files=no").strip()
        ),
    }


def load_oracle(path: Path) -> List[dict]:
    records: List[dict] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            record_id = record.get("record_id")
            if not record_id or record_id in seen:
                raise ValueError(
                    f"Missing or duplicate record_id at {path}:{line_number}"
                )
            seen.add(record_id)
            features = np.asarray(record.get("features"), dtype=float)
            if features.shape != (DEFAULT_FEATURE_COUNT,):
                raise ValueError(
                    f"{record_id} has feature shape {features.shape}; expected "
                    f"({DEFAULT_FEATURE_COUNT},)"
                )
            label = int(record.get("oracle_label", -1))
            if label < 0 or label >= len(DEFAULT_CLASS_NAMES):
                raise ValueError(f"{record_id} has invalid oracle label {label}")
            if record.get("split") not in {"train", "validation", "test"}:
                raise ValueError(f"{record_id} has invalid split {record.get('split')}")
            records.append(record)
    if not records:
        raise ValueError(f"Oracle contains no records: {path}")
    return records


def records_to_arrays(records: Sequence[dict]) -> Tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([record["features"] for record in records], dtype=float),
        np.asarray([record["oracle_label"] for record in records], dtype=int),
    )


def stratified_cap(records: Sequence[dict], cap: int, seed: int) -> List[dict]:
    if cap <= 0 or len(records) <= cap:
        return list(records)
    rng = np.random.default_rng(seed)
    grouped: Dict[int, List[dict]] = {
        label: [] for label in range(len(DEFAULT_CLASS_NAMES))
    }
    for record in records:
        grouped[int(record["oracle_label"])].append(record)
    selected: List[dict] = []
    nonempty = [label for label, rows in grouped.items() if rows]
    base = cap // len(nonempty)
    remainder = cap % len(nonempty)
    for position, label in enumerate(nonempty):
        rows = grouped[label]
        target = min(len(rows), base + (1 if position < remainder else 0))
        indices = rng.choice(len(rows), size=target, replace=False)
        selected.extend(rows[int(index)] for index in indices)
    rng.shuffle(selected)
    return selected


def create_qnn(
    *,
    backend_name: str,
    shots: int,
    seed: int,
):
    from qiskit_machine_learning.neural_networks import SamplerQNN

    circuit, feature_parameters, weight_parameters, output_qubits = (
        build_unitary_circuit(
            feature_count=DEFAULT_FEATURE_COUNT,
            num_classes=len(DEFAULT_CLASS_NAMES),
            reps=DEFAULT_REPS,
        )
    )
    pass_manager = None
    device: Dict[str, object] = {"backend": backend_name, "shots": shots}

    if backend_name == "aer_gpu":
        from qiskit.transpiler import generate_preset_pass_manager
        from qiskit_aer import AerSimulator
        from qiskit_aer.primitives import SamplerV2

        target_count = 0
        gpu_names: List[str] = []
        try:
            import torch

            if torch.cuda.is_available():
                target_count = int(torch.cuda.device_count())
                gpu_names = [
                    torch.cuda.get_device_name(index) for index in range(target_count)
                ]
        except (ImportError, RuntimeError):
            pass
        if target_count == 0:
            target_count = int(os.environ.get("SLURM_GPUS_ON_NODE", "0") or 0)
        if target_count == 0:
            visible = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
            if visible:
                target_count = len([item for item in visible.split(",") if item.strip()])
        if target_count < 1:
            raise RuntimeError(
                "Aer GPU training requested but no accelerator allocation was detected"
            )
        backend_options = {
            "method": "statevector",
            "device": "GPU",
            "batched_shots_gpu": True,
            "runtime_parameter_bind_enable": True,
        }
        simulator = AerSimulator(**backend_options)
        available = list(simulator.available_devices())
        if "GPU" not in available:
            raise RuntimeError(
                "Aer GPU training was requested but this build does not expose GPU"
            )
        # Execute a real probe because some ROCm builds advertise GPU before
        # failing during kernel launch.
        from qiskit import QuantumCircuit, transpile

        probe = QuantumCircuit(1, 1)
        probe.h(0)
        probe.measure(0, 0)
        simulator.run(transpile(probe, simulator), shots=1).result()
        sampler = SamplerV2(
            default_shots=shots,
            seed=seed,
            options={
                "backend_options": {
                    **backend_options,
                },
                "run_options": {"seed_simulator": seed},
            },
        )
        pass_manager = generate_preset_pass_manager(
            optimization_level=1,
            backend=simulator,
            seed_transpiler=seed,
        )
        device["available_devices"] = available
        device["gpu_scope"] = "all_scheduler_visible_devices"
        device["visible_gpu_count"] = target_count
        device["gpu_names"] = gpu_names
    elif backend_name == "statevector_cpu":
        from qiskit.primitives import StatevectorSampler

        sampler = StatevectorSampler(default_shots=shots, seed=seed)
    else:
        raise ValueError(
            f"Unsupported training backend {backend_name!r}; use aer_gpu or statevector_cpu"
        )

    qnn = SamplerQNN(
        circuit=circuit,
        sampler=sampler,
        input_params=feature_parameters,
        weight_params=weight_parameters,
        interpret=qnn_interpret(output_qubits),
        output_shape=ROUTING_OUTPUT_SHAPE,
        pass_manager=pass_manager,
    )
    return qnn, len(weight_parameters), device


def class_balancing_weights(labels: np.ndarray) -> np.ndarray:
    counts = Counter(int(label) for label in labels)
    weights = np.ones(len(labels), dtype=float)
    for label, count in counts.items():
        weights[labels == label] = len(labels) / (len(counts) * count)
    return weights


def probabilities(qnn, features: np.ndarray, weights: np.ndarray) -> np.ndarray:
    output = np.asarray(qnn.forward(features, weights), dtype=float)
    if output.ndim == 3 and output.shape[1] == 1:
        output = output[:, 0, :]
    if output.shape != (len(features), ROUTING_OUTPUT_SHAPE):
        raise RuntimeError(f"Unexpected QNN output shape: {output.shape}")
    row_sums = output.sum(axis=1, keepdims=True)
    return np.divide(
        output,
        row_sums,
        out=np.full_like(output, 1.0 / ROUTING_OUTPUT_SHAPE),
        where=row_sums > 0,
    )


def classification_metrics(
    records: Sequence[dict],
    predicted: np.ndarray,
    predicted_probabilities: np.ndarray,
) -> Dict[str, object]:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
    )

    truth = np.asarray([record["oracle_label"] for record in records], dtype=int)
    matrix = confusion_matrix(
        truth,
        predicted,
        labels=list(range(len(DEFAULT_CLASS_NAMES))),
    )
    selected_reconciliation_accuracies: List[float] = []
    oracle_reconciliation_accuracies: List[float] = []
    dispatched_methods: List[str] = []
    for record, predicted_label in zip(records, predicted):
        selected_method = (
            DEFAULT_CLASS_NAMES[int(predicted_label)]
            if int(predicted_label) < len(DEFAULT_CLASS_NAMES)
            else None
        )
        oracle_method = record["oracle_method"]
        dispatched_methods.append(selected_method or ABSTAIN_CLASS_NAME)
        selected_reconciliation_accuracies.append(
            0.0
            if selected_method is None
            else float(record["method_metrics"][selected_method]["accuracy"])
        )
        oracle_reconciliation_accuracies.append(
            float(record["method_metrics"][oracle_method]["accuracy"])
        )
    confidence = predicted_probabilities[
        np.arange(len(predicted)), predicted.astype(int)
    ]
    return {
        "n_samples": len(records),
        "accuracy": float(accuracy_score(truth, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
        "macro_f1": float(
            f1_score(
                truth,
                predicted,
                labels=list(range(len(DEFAULT_CLASS_NAMES))),
                average="macro",
                zero_division=0,
            )
        ),
        "confusion_matrix": matrix.astype(int).tolist(),
        "label_counts": dict(Counter(int(value) for value in truth)),
        "prediction_counts": dict(Counter(int(value) for value in predicted)),
        "abstain_rate": float(np.mean(predicted == ABSTAIN_CLASS_INDEX)),
        "mean_confidence": float(np.mean(confidence)),
        "mean_selected_reconciliation_accuracy": float(
            np.mean(selected_reconciliation_accuracies)
        ),
        "mean_oracle_reconciliation_accuracy": float(
            np.mean(oracle_reconciliation_accuracies)
        ),
        "gpu_dispatch_rate": float(np.mean([
            method in {
                "minilm", "gemma_e2b", "bge", "cross_encoder",
                "qwen_1_5b", "smollm2_1_7b",
            }
            for method in dispatched_methods
        ])),
    }


def evaluate(qnn, records: Sequence[dict], weights: np.ndarray) -> Dict[str, object]:
    features, _ = records_to_arrays(records)
    probs = probabilities(qnn, features, weights)
    predicted = np.argmax(probs, axis=1)
    return classification_metrics(records, predicted, probs)


def run_train(args: argparse.Namespace) -> None:
    from scipy.optimize import minimize

    oracle_path = (REPO_ROOT / args.oracle).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = output_dir / f"candidate_start{args.start_index:02d}.json"
    if candidate_path.exists() and not args.overwrite:
        raise RuntimeError(f"Candidate already exists: {candidate_path}")

    records = load_oracle(oracle_path)
    train_records = [record for record in records if record["split"] == "train"]
    validation_records = [
        record for record in records if record["split"] == "validation"
    ]
    if not train_records or not validation_records:
        raise RuntimeError("Oracle must contain non-empty train and validation splits")

    seed = args.seed + args.start_index * 10_007
    train_records = stratified_cap(train_records, args.max_train_records, seed)
    X_train, y_train = records_to_arrays(train_records)
    sample_weights = class_balancing_weights(y_train)
    qnn, num_weights, device = create_qnn(
        backend_name=args.backend,
        shots=args.training_shots,
        seed=seed,
    )
    rng = np.random.default_rng(seed)
    initial = rng.normal(loc=0.0, scale=args.initial_scale, size=num_weights)
    history: List[Dict[str, object]] = []
    evaluation_counter = 0
    started = time.time()

    def objective(weights: np.ndarray) -> float:
        nonlocal evaluation_counter
        evaluation_counter += 1
        probs = probabilities(qnn, X_train, weights)
        correct = np.clip(probs[np.arange(len(y_train)), y_train], 1e-9, 1.0)
        loss = float(np.average(-np.log(correct), weights=sample_weights))
        history.append(
            {
                "evaluation": evaluation_counter,
                "loss": loss,
                "elapsed_seconds": time.time() - started,
            }
        )
        print(
            f"[start {args.start_index:02d}] evaluation={evaluation_counter:04d} "
            f"loss={loss:.6f}",
            flush=True,
        )
        return loss

    result = minimize(
        objective,
        initial,
        method="COBYLA",
        options={
            "maxiter": args.maxiter,
            "rhobeg": args.rhobeg,
            "tol": args.tolerance,
            "disp": False,
        },
    )
    weights = np.asarray(result.x, dtype=float)
    validation_metrics = evaluate(qnn, validation_records, weights)
    candidate = {
        "created_at": utc_now(),
        "start_index": args.start_index,
        "seed": seed,
        "circuit_id": CIRCUIT_ID,
        "class_names": list(DEFAULT_CLASS_NAMES),
        "feature_count": DEFAULT_FEATURE_COUNT,
        "reps": DEFAULT_REPS,
        "trained_params": weights.tolist(),
        "optimizer": {
            "name": "COBYLA",
            "maxiter": args.maxiter,
            "rhobeg": args.rhobeg,
            "tolerance": args.tolerance,
            "success": bool(result.success),
            "message": str(result.message),
            "function_evaluations": int(result.nfev),
            "final_loss": float(result.fun),
        },
        "training": {
            "oracle_path": str(oracle_path),
            "oracle_sha256": file_sha256(oracle_path),
            "records": len(train_records),
            "label_counts": dict(Counter(int(value) for value in y_train)),
            "class_balancing": "inverse-frequency weighted cross-entropy",
            "backend": args.backend,
            "shots": args.training_shots,
            "device": device,
            "duration_seconds": time.time() - started,
        },
        "validation_metrics": validation_metrics,
        "history": history,
        "host": socket.gethostname(),
        "git": git_metadata(),
    }
    candidate_path.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("=== Candidate complete ===")
    print(f"Candidate: {candidate_path}")
    print(json.dumps(validation_metrics, indent=2, sort_keys=True))


def candidate_rank(candidate: dict) -> Tuple[float, float, float, float]:
    metrics = candidate["validation_metrics"]
    return (
        float(metrics["macro_f1"]),
        float(metrics["balanced_accuracy"]),
        float(metrics["mean_selected_reconciliation_accuracy"]),
        -float(metrics["gpu_dispatch_rate"]),
    )


def write_latex_selection(path: Path, report: dict) -> None:
    validation = report["validation_metrics"]
    test = report["test_metrics"]
    content = (
        "\\begin{table}[t]\n"
        "\\centering\n"
        "\\small\n"
        "\\caption{Canonical VQC model-selection and held-out routing performance.}\n"
        "\\label{tab:vqc-model-selection}\n"
        "\\begin{tabular}{lrr}\n"
        "\\toprule\n"
        "Metric & Validation & Held-out test \\\\\n"
        "\\midrule\n"
        f"Routing accuracy (\\%) & {100 * validation['accuracy']:.2f} & "
        f"{100 * test['accuracy']:.2f} \\\\\n"
        f"Balanced accuracy (\\%) & {100 * validation['balanced_accuracy']:.2f} & "
        f"{100 * test['balanced_accuracy']:.2f} \\\\\n"
        f"Macro-F1 (\\%) & {100 * validation['macro_f1']:.2f} & "
        f"{100 * test['macro_f1']:.2f} \\\\\n"
        f"Selected reconciliation accuracy (\\%) & "
        f"{100 * validation['mean_selected_reconciliation_accuracy']:.2f} & "
        f"{100 * test['mean_selected_reconciliation_accuracy']:.2f} \\\\\n"
        f"GPU dispatch rate (\\%) & {100 * validation['gpu_dispatch_rate']:.2f} & "
        f"{100 * test['gpu_dispatch_rate']:.2f} \\\\\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
    )
    path.write_text(content, encoding="utf-8")


def run_select(args: argparse.Namespace) -> None:
    oracle_path = (REPO_ROOT / args.oracle).resolve()
    candidates_dir = (REPO_ROOT / args.candidates_dir).resolve()
    model_path = (REPO_ROOT / args.model_output).resolve()
    candidates = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(candidates_dir.glob("candidate_start*.json"))
    ]
    if len(candidates) < args.expected_starts:
        raise RuntimeError(
            f"Expected at least {args.expected_starts} completed starts, found "
            f"{len(candidates)} in {candidates_dir}"
        )
    oracle_hash = file_sha256(oracle_path)
    mismatched = [
        candidate["start_index"]
        for candidate in candidates
        if candidate["training"]["oracle_sha256"] != oracle_hash
    ]
    if mismatched:
        raise RuntimeError(f"Candidates use a different oracle: starts {mismatched}")

    winner = max(candidates, key=candidate_rank)
    records = load_oracle(oracle_path)
    test_records = [record for record in records if record["split"] == "test"]
    if not test_records:
        raise RuntimeError("Oracle has no held-out test records")
    qnn, _, device = create_qnn(
        backend_name=args.backend,
        shots=args.evaluation_shots,
        seed=args.seed,
    )
    weights = np.asarray(winner["trained_params"], dtype=float)
    test_metrics = evaluate(qnn, test_records, weights)
    validation_metrics = winner["validation_metrics"]

    if (
        float(test_metrics["macro_f1"]) < args.min_macro_f1
        or float(test_metrics["balanced_accuracy"]) < args.min_balanced_accuracy
    ):
        raise RuntimeError(
            "Selected model failed the held-out quality gate: "
            f"macro-F1={test_metrics['macro_f1']:.4f}, "
            f"balanced_accuracy={test_metrics['balanced_accuracy']:.4f}. "
            "Do not spend QPU time; improve labels/features or training."
        )

    selection_report = {
        "selected_at": utc_now(),
        "selection_rule": (
            "validation macro-F1, then balanced accuracy, then reconciliation "
            "accuracy, then lower GPU dispatch"
        ),
        "candidate_count": len(candidates),
        "selected_start_index": winner["start_index"],
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "test_evaluation": {
            "backend": args.backend,
            "shots": args.evaluation_shots,
            "device": device,
            "n_records": len(test_records),
        },
        "oracle_path": str(oracle_path),
        "oracle_sha256": oracle_hash,
        "quality_gate": {
            "min_macro_f1": args.min_macro_f1,
            "min_balanced_accuracy": args.min_balanced_accuracy,
            "passed": True,
        },
        "candidate_ranking": [
            {
                "start_index": candidate["start_index"],
                "rank_tuple": list(candidate_rank(candidate)),
            }
            for candidate in sorted(candidates, key=candidate_rank, reverse=True)
        ],
    }
    model = model_from_weights(
        weights,
        metadata={
            "training": winner["training"],
            "optimizer": winner["optimizer"],
            "selection": selection_report,
        },
    )
    model.save(model_path)
    report_path = model_path.with_suffix(".selection.json")
    report_path.write_text(
        json.dumps(selection_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_latex_selection(model_path.with_suffix(".selection.tex"), selection_report)
    print("=== Model selected ===")
    print(f"Start: {winner['start_index']}")
    print(f"Model: {model_path}")
    print(f"SHA256: {model.sha256}")
    print(json.dumps(test_metrics, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train", help="Train one independent start")
    train.add_argument(
        "--oracle",
        default="data/training/router_oracle_22500_v6.jsonl",
    )
    train.add_argument(
        "--output-dir",
        default="data/training/qpu_router_multistart_v6",
    )
    train.add_argument("--start-index", type=int, required=True)
    train.add_argument(
        "--backend",
        choices=["aer_gpu", "statevector_cpu"],
        default="aer_gpu",
    )
    train.add_argument("--training-shots", type=int, default=512)
    train.add_argument("--maxiter", type=int, default=200)
    train.add_argument("--rhobeg", type=float, default=0.5)
    train.add_argument("--tolerance", type=float, default=1e-3)
    train.add_argument("--initial-scale", type=float, default=0.25)
    train.add_argument("--seed", type=int, default=20260723)
    train.add_argument(
        "--max-train-records",
        type=int,
        default=0,
        help="Zero uses every training record; positive values cap stratified input",
    )
    train.add_argument("--overwrite", action="store_true")

    select = subparsers.add_parser(
        "select",
        help="Select by validation metrics and evaluate held-out test once",
    )
    select.add_argument(
        "--oracle",
        default="data/training/router_oracle_22500_v6.jsonl",
    )
    select.add_argument(
        "--candidates-dir",
        default="data/training/qpu_router_multistart_v6",
    )
    select.add_argument(
        "--model-output",
        default="configs/quantum_router_v6.json",
    )
    select.add_argument("--expected-starts", type=int, default=10)
    select.add_argument(
        "--backend",
        choices=["aer_gpu", "statevector_cpu"],
        default="aer_gpu",
    )
    select.add_argument("--evaluation-shots", type=int, default=2048)
    select.add_argument("--seed", type=int, default=20260723)
    select.add_argument("--min-macro-f1", type=float, default=0.70)
    select.add_argument("--min-balanced-accuracy", type=float, default=0.70)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "train":
        run_train(args)
    elif args.command == "select":
        run_select(args)


if __name__ == "__main__":
    main()
