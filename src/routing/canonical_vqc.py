"""Canonical, hardware-efficient VQC used by training and every backend.

The previous workflow trained a Qiskit ``VQC`` that measured/interpreted all
12 qubits, then performed hardware inference by measuring only two output
qubits from a differently placed feature map.  Its weights therefore did not
describe the circuit that was executed on the QPU.

This module is the single source of truth for:

* the 10 feature parameters;
* the shallow 13-qubit unitary;
* the three measured output qubits and complete eight-state class encoding;
* model artifact validation; and
* provider-independent decoding.

Training operates on the unitary circuit.  Hardware inference calls
``build_measured_circuit`` on that exact unitary and only adds terminal
measurements.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


MODEL_SCHEMA_VERSION = 9
CIRCUIT_ID = "rap-tree-vqc-13q-v9-eight-route"
DEFAULT_CLASS_NAMES = (
    "levenshtein",
    "regex",
    "schema_registry",
    "minilm",
    "qwen_1_5b",
    "bge",
    "cross_encoder",
    "cohere_embed_v4",
)
DEFAULT_FEATURE_COUNT = 10
DEFAULT_REPS = 2
IBM_MAX_EXECUTIONS = 10_000_000
# Abstention remains available as a confidence policy applied after decoding;
# it no longer consumes either of the two previously unused three-bit states.
ABSTAIN_CLASS_NAME = "abstain"
ABSTAIN_CLASS_INDEX = len(DEFAULT_CLASS_NAMES)
ROUTING_OUTPUT_SHAPE = len(DEFAULT_CLASS_NAMES)


def output_qubit_count(num_classes: int) -> int:
    if num_classes < 2:
        raise ValueError("At least two routing classes are required")
    return int(math.ceil(math.log2(num_classes)))


def logical_qubit_count(feature_count: int, num_classes: int) -> int:
    return feature_count + output_qubit_count(num_classes)


def _tree_edges(feature_count: int, output_qubits: Sequence[int]) -> List[Tuple[int, int]]:
    """Return the fixed degree-3 interaction graph used by the 10+3 model.

    Its maximum logical degree is three, which maps naturally to IBM's
    heavy-hex fabric while remaining shallow on VLQ's star-connected system.
    """
    if feature_count != 10 or len(output_qubits) != 3:
        raise ValueError(
            f"{CIRCUIT_ID} requires exactly 10 feature and 3 output qubits"
        )
    left, middle, right = output_qubits
    return [
        # Each measured output has three direct feature inputs.  Feature 9
        # joins the first feature subtree, so all ten dimensions participate
        # while the maximum logical degree remains three.
        (0, left),
        (1, left),
        (2, left),
        (3, middle),
        (4, middle),
        (5, middle),
        (6, right),
        (7, right),
        (8, right),
        (9, 0),
    ]


def build_unitary_circuit(
    *,
    feature_count: int = DEFAULT_FEATURE_COUNT,
    num_classes: int = len(DEFAULT_CLASS_NAMES),
    reps: int = DEFAULT_REPS,
):
    """Build the canonical parameterized unitary and return its parameters.

    Returns
    -------
    tuple
        ``(circuit, feature_parameters, weight_parameters, output_qubits)``.
    """
    if reps < 1:
        raise ValueError("reps must be at least one")
    num_outputs = output_qubit_count(num_classes)
    num_qubits = feature_count + num_outputs
    if num_qubits != 13:
        raise ValueError(
            f"{CIRCUIT_ID} is the eight-route 13-qubit protocol; requested "
            f"{feature_count} features and {num_classes} classes ({num_qubits} qubits)"
        )

    try:
        from qiskit import QuantumCircuit
        from qiskit.circuit import ParameterVector
    except ImportError as exc:  # pragma: no cover - exercised in minimal installs
        raise ImportError("Qiskit is required to construct the canonical VQC") from exc

    feature_parameters = ParameterVector("x", feature_count)
    weight_parameters = ParameterVector("theta", reps * num_qubits)
    output_qubits = tuple(range(feature_count, num_qubits))
    edges = _tree_edges(feature_count, output_qubits)

    circuit = QuantumCircuit(num_qubits, name=CIRCUIT_ID)
    weight_index = 0
    for rep in range(reps):
        # Data re-uploading lets a shallow circuit remain expressive without
        # the all-to-all two-qubit expansion of ZZFeatureMap.
        for qubit, parameter in enumerate(feature_parameters):
            circuit.ry(parameter, qubit)
        for qubit in range(num_qubits):
            circuit.ry(weight_parameters[weight_index], qubit)
            weight_index += 1

        # Reverse alternating layers.  The undirected interaction graph remains
        # identical, while information can propagate in both directions.
        layer_edges = edges if rep % 2 == 0 else [(dst, src) for src, dst in reversed(edges)]
        for control, target in layer_edges:
            circuit.cx(control, target)

    circuit.metadata = {
        "circuit_id": CIRCUIT_ID,
        "model_schema_version": MODEL_SCHEMA_VERSION,
        "feature_count": feature_count,
        "num_classes": num_classes,
        "reps": reps,
        "output_qubits": list(output_qubits),
    }
    return circuit, list(feature_parameters), list(weight_parameters), output_qubits


def build_measured_circuit(
    *,
    weights: Sequence[float],
    feature_count: int = DEFAULT_FEATURE_COUNT,
    num_classes: int = len(DEFAULT_CLASS_NAMES),
    reps: int = DEFAULT_REPS,
):
    """Return the canonical circuit with frozen weights and three output bits."""
    circuit, feature_parameters, weight_parameters, output_qubits = (
        build_unitary_circuit(
            feature_count=feature_count,
            num_classes=num_classes,
            reps=reps,
        )
    )
    weight_array = np.asarray(weights, dtype=float)
    if weight_array.shape != (len(weight_parameters),):
        raise ValueError(
            f"Model has {weight_array.size} weights; {CIRCUIT_ID} requires "
            f"{len(weight_parameters)}"
        )
    circuit = circuit.assign_parameters(
        dict(zip(weight_parameters, weight_array)),
        inplace=False,
    )

    from qiskit import ClassicalRegister

    output_register = ClassicalRegister(len(output_qubits), "route")
    circuit.add_register(output_register)
    circuit.measure(list(output_qubits), list(output_register))
    return circuit, feature_parameters, output_qubits


def qnn_interpret(output_qubits: Sequence[int]):
    """Map all three-bit measurement states to the eight route classes."""
    qubits = tuple(int(q) for q in output_qubits)

    def interpret(bitstring_as_int: int) -> int:
        class_index = 0
        for classical_position, qubit in enumerate(qubits):
            class_index |= ((int(bitstring_as_int) >> qubit) & 1) << classical_position
        return class_index

    return interpret


def bind_features(circuit, feature_parameters, features: Sequence[float]):
    values = np.asarray(features, dtype=float)
    if values.shape != (len(feature_parameters),):
        raise ValueError(
            f"Expected {len(feature_parameters)} features, received shape {values.shape}"
        )
    return circuit.assign_parameters(
        dict(zip(feature_parameters, values)),
        inplace=False,
    )


def parameter_mapping(feature_parameters, feature_matrix: np.ndarray) -> Mapping:
    """Return a SamplerV2 mapping that is independent of circuit parameter order."""
    matrix = np.asarray(feature_matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(feature_parameters):
        raise ValueError(
            f"Feature matrix must have shape (N, {len(feature_parameters)}); "
            f"received {matrix.shape}"
        )
    return {tuple(feature_parameters): matrix}


def counts_to_prediction(
    counts: Mapping[str, int],
    class_names: Sequence[str] = DEFAULT_CLASS_NAMES,
    *,
    confidence_threshold: float = 0.0,
) -> Dict[str, object]:
    """Decode output counts into a class, confidence, and dense probabilities.

    Every three-bit state maps to a real reconciler. Optional abstention is a
    post-measurement confidence policy and therefore does not waste a state.
    """
    total = int(sum(int(value) for value in counts.values()))
    if total <= 0:
        raise ValueError("Cannot decode empty QPU counts")
    probabilities = np.zeros(len(class_names), dtype=float)
    invalid_shots = 0
    for raw_bits, count in counts.items():
        bits = str(raw_bits).replace(" ", "")
        class_index = int(bits, 2)
        if class_index < len(class_names):
            probabilities[class_index] += int(count) / total
        else:
            invalid_shots += int(count)
    invalid_state_rate = invalid_shots / total
    class_index = int(np.argmax(probabilities))
    confidence = float(probabilities[class_index])
    abstain = confidence < float(confidence_threshold)
    return {
        "class_index": ABSTAIN_CLASS_INDEX if abstain else class_index,
        "class_name": ABSTAIN_CLASS_NAME if abstain else class_names[class_index],
        "confidence": confidence,
        "probabilities": probabilities.tolist(),
        "shots": total,
        "abstain": abstain,
        "invalid_shots": invalid_shots,
        "invalid_state_rate": invalid_state_rate,
    }


def split_bitstrings_into_replicates(
    bitstrings: Sequence[str],
    *,
    repetitions: int,
    shots_per_repetition: int,
) -> List[Dict[str, int]]:
    """Split one Sampler shot stream into within-job technical replicates."""
    expected = repetitions * shots_per_repetition
    if len(bitstrings) != expected:
        raise ValueError(
            f"Expected {expected} bitstrings ({repetitions} × "
            f"{shots_per_repetition}), received {len(bitstrings)}"
        )
    return [
        dict(
            Counter(
                bitstrings[
                    rep * shots_per_repetition : (rep + 1) * shots_per_repetition
                ]
            )
        )
        for rep in range(repetitions)
    ]


def execution_count(
    num_parameter_sets: int,
    repetitions: int,
    shots_per_repetition: int,
) -> int:
    for name, value in (
        ("num_parameter_sets", num_parameter_sets),
        ("repetitions", repetitions),
        ("shots_per_repetition", shots_per_repetition),
    ):
        if int(value) < 1:
            raise ValueError(f"{name} must be positive")
    return int(num_parameter_sets) * int(repetitions) * int(shots_per_repetition)


def validate_ibm_execution_limit(
    num_parameter_sets: int,
    repetitions: int,
    shots_per_repetition: int,
    *,
    maximum: int = IBM_MAX_EXECUTIONS,
) -> int:
    total = execution_count(
        num_parameter_sets,
        repetitions,
        shots_per_repetition,
    )
    if total > maximum:
        raise ValueError(
            f"IBM Sampler job would require {total:,} executions, exceeding "
            f"the {maximum:,} per-job limit. Reduce shots or evaluation cases; "
            "the workflow will not split this paper run into hidden extra jobs."
        )
    return total


@dataclass(frozen=True)
class RouterModel:
    """Validated frozen router artifact."""

    trained_params: np.ndarray
    class_names: Tuple[str, ...]
    feature_count: int
    reps: int
    metadata: Dict[str, object]

    @property
    def num_classes(self) -> int:
        return len(self.class_names)

    @property
    def logical_qubits(self) -> int:
        return logical_qubit_count(self.feature_count, self.num_classes)

    @property
    def sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> Dict[str, object]:
        return {
            "model_schema_version": MODEL_SCHEMA_VERSION,
            "circuit_id": CIRCUIT_ID,
            "trained_params": self.trained_params.astype(float).tolist(),
            "class_names": list(self.class_names),
            "num_classes": self.num_classes,
            "feature_count": self.feature_count,
            "reps": self.reps,
            "logical_qubits": self.logical_qubits,
            "metadata": self.metadata,
        }

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "RouterModel":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        schema_version = data.get("model_schema_version", MODEL_SCHEMA_VERSION)
        circuit_id = data.get("circuit_id", CIRCUIT_ID)
        if int(schema_version) != MODEL_SCHEMA_VERSION or circuit_id != CIRCUIT_ID:
            raise ValueError(
                f"{source} is not a {CIRCUIT_ID} model artifact. "
                "Archived router models must not be evaluated under the current protocol."
            )
        if "trained_params" not in data:
            raise ValueError(f"{source} missing trained_params")
        class_names = tuple(data.get("class_names") or DEFAULT_CLASS_NAMES)
        if class_names != DEFAULT_CLASS_NAMES:
            raise ValueError(
                f"{source} class order {class_names!r} does not match the canonical "
                f"eight-route protocol {DEFAULT_CLASS_NAMES!r}"
            )
        feature_count = int(data.get("feature_count", DEFAULT_FEATURE_COUNT))
        weights = np.asarray(data.get("trained_params"), dtype=float)
        qubits = logical_qubit_count(feature_count, len(class_names))
        reps = int(data.get("reps") or (weights.size // qubits if qubits > 0 else DEFAULT_REPS))
        expected = reps * qubits
        if weights.shape != (expected,):
            raise ValueError(
                f"{source} contains {weights.size} weights; expected {expected}"
            )
        return cls(
            trained_params=weights,
            class_names=class_names,
            feature_count=feature_count,
            reps=reps,
            metadata=dict(data.get("metadata") or {}),
        )


def model_from_weights(
    weights: Sequence[float],
    *,
    class_names: Sequence[str] = DEFAULT_CLASS_NAMES,
    feature_count: int = DEFAULT_FEATURE_COUNT,
    reps: int = DEFAULT_REPS,
    metadata: Dict[str, object] | None = None,
) -> RouterModel:
    return RouterModel(
        trained_params=np.asarray(weights, dtype=float),
        class_names=tuple(class_names),
        feature_count=int(feature_count),
        reps=int(reps),
        metadata=dict(metadata or {}),
    )
