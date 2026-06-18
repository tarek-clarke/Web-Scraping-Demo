"""
quantum_router.py — Quantum-accelerated packet router for resilient-rap-framework.

Selects the optimal reconciler (levenshtein, regex, bert, or gemma_e4b)
for each drifted data packet using Variational Quantum Classifier (VQC)
circuits or, optionally, QAOA-based batch optimization.

All Qiskit imports are lazily guarded behind ``try/except ImportError``
so the module can be imported and the classical fallback used even when
Qiskit is not installed.
"""

import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np


class QuantumRouter:
    """
    Quantum-accelerated router that selects the optimal reconciler
    (levenshtein, regex, or bert) for each drifted packet.

    Uses VQC (per-packet classification) or QAOA (batch optimization).
    Gemma is supported but disabled by default (too slow per MI250X benchmarks).

    Parameters
    ----------
    backend : str
        Name of the quantum backend. ``"aer_simulator"`` (default) uses
        the local Aer noise-free simulator; ``"ibm_quantum"`` picks the
        least-busy IBM device.
    mode : str
        ``"vqc"`` for per-packet classification, ``"qaoa"`` for batch
        optimisation (QAOA support is planned).
    enable_gemma : bool
        When *True* the fourth reconciler class (``gemma_e4b``) is
        enabled.  Disabled by default because MI250X benchmarks showed
        unacceptable latency.
    shots : int
        Number of measurement shots per circuit execution.
    feature_count : int
        Dimensionality of each packet's feature vector.
    model_params_path : str | None
        Optional path to a JSON file with pre-trained VQC parameters.
    """

    RECONCILER_CLASSES: Dict[int, str] = {
        0: "levenshtein",
        1: "regex",
        2: "bert",
        3: "gemma_e4b",  # Disabled by default
    }

    _shared_backend: Optional[object] = None
    _backend_lock: Optional[object] = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        backend: str = "aer_simulator",
        mode: str = "vqc",
        enable_gemma: bool = False,
        shots: int = 1024,
        feature_count: int = 10,
        model_params_path: Optional[str] = None,
    ) -> None:
        self.backend_name: str = backend
        self.mode: str = mode
        self.enable_gemma: bool = enable_gemma
        self.shots: int = shots
        self.feature_count: int = feature_count
        self.num_classes: int = 4 if enable_gemma else 3
        self.num_output_qubits: int = 2  # 2 qubits encode up to 4 classes
        self.trained_params: Optional[np.ndarray] = None
        self._backend: Optional[object] = None
        self._circuit: Optional[object] = None

        import threading
        if QuantumRouter._backend_lock is None:
            QuantumRouter._backend_lock = threading.Lock()

        if model_params_path and os.path.exists(model_params_path):
            self._load_params(model_params_path)

    # ------------------------------------------------------------------
    # Backend helpers
    # ------------------------------------------------------------------

    def _init_backend(self) -> None:
        """Lazy-initialise the quantum backend.

        Falls back to ``AerSimulator`` when the requested backend name is
        not recognised, and prints a warning to *stdout* when Qiskit is
        missing entirely.
        """
        import threading
        if QuantumRouter._backend_lock is None:
            QuantumRouter._backend_lock = threading.Lock()

        with QuantumRouter._backend_lock:
            if QuantumRouter._shared_backend is not None:
                self._backend = QuantumRouter._shared_backend
                return

            try:
                if self.backend_name == "aer_simulator":
                    from qiskit_aer import AerSimulator  # type: ignore[import-untyped]

                    self._backend = AerSimulator()
                elif self.backend_name == "ibm_quantum":
                    from qiskit_ibm_runtime import QiskitRuntimeService  # type: ignore[import-untyped]

                    token = os.getenv("QISKIT_IBM_TOKEN") or os.getenv("IBM_QUANTUM_TOKEN")
                    channel = os.getenv("QISKIT_IBM_CHANNEL") or "ibm_quantum"
                    instance = os.getenv("QISKIT_IBM_INSTANCE")

                    service = QiskitRuntimeService(token=token, channel=channel, instance=instance)
                    self._backend = service.least_busy(
                        simulator=False,
                        operational=True,
                        min_num_qubits=self.feature_count + self.num_output_qubits
                    )
                else:
                    from qiskit_aer import AerSimulator  # type: ignore[import-untyped]

                    self._backend = AerSimulator()
                    print(
                        f"[QuantumRouter] Backend '{self.backend_name}' not recognised, "
                        "falling back to AerSimulator"
                    )
                
                QuantumRouter._shared_backend = self._backend
            except ImportError:
                print(
                    "[QuantumRouter] Qiskit not installed. "
                    "Install with: pip install -r requirements-quantum.txt"
                )
                self._backend = None

    # ------------------------------------------------------------------
    # Circuit construction
    # ------------------------------------------------------------------

    def _build_vqc_circuit(self, features: np.ndarray) -> object:
        """Build a VQC circuit with ``ZZFeatureMap`` + ``RealAmplitudes`` ansatz.

        The first ``feature_count`` qubits are used for angle-encoded
        features.  Two additional *output* qubits are measured to yield
        a 2-bit class index (supporting up to 4 reconciler classes).

        Parameters
        ----------
        features : np.ndarray
            1-D array of length ``self.feature_count``.

        Returns
        -------
        QuantumCircuit
            Parameterised circuit ready for parameter binding.
        """
        try:
            from qiskit.circuit import QuantumCircuit  # type: ignore[import-untyped]
            from qiskit.circuit.library import (  # type: ignore[import-untyped]
                RealAmplitudes,
                ZZFeatureMap,
            )
        except ImportError as exc:
            raise ImportError(
                "[QuantumRouter] qiskit is required for circuit construction. "
                "Install with: pip install -r requirements-quantum.txt"
            ) from exc

        num_qubits: int = self.feature_count + self.num_output_qubits
        qc = QuantumCircuit(num_qubits, self.num_output_qubits)

        # Feature encoding: angle encoding on feature qubits
        feature_map = ZZFeatureMap(feature_dimension=self.feature_count, reps=2)
        qc.compose(feature_map, qubits=list(range(self.feature_count)), inplace=True)

        # Trainable ansatz on *all* qubits (entangles feature + output)
        ansatz = RealAmplitudes(num_qubits=num_qubits, reps=2)
        qc.compose(ansatz, inplace=True)

        # Measure only output qubits
        qc.measure(
            list(range(self.feature_count, num_qubits)),
            list(range(self.num_output_qubits)),
        )

        return qc

    def _bind_features(self, circuit: object, features: np.ndarray) -> object:
        """Bind feature values and trained weights to circuit parameters.

        Feature parameters are identified by names starting with ``'x'``
        (the convention used by Qiskit's ``ZZFeatureMap``).  All
        remaining parameters are treated as trainable weights.

        Parameters
        ----------
        circuit : QuantumCircuit
            A parameterised circuit produced by :pymeth:`_build_vqc_circuit`.
        features : np.ndarray
            1-D array of feature values to bind.

        Returns
        -------
        QuantumCircuit
            A fully-bound circuit with no free parameters.
        """
        feature_params = [p for p in circuit.parameters if p.name.startswith("x")]
        param_dict = {
            p: v
            for p, v in zip(
                sorted(feature_params, key=lambda p: p.name), features
            )
        }

        trainable_params = [
            p for p in circuit.parameters if not p.name.startswith("x")
        ]
        
        if self.trained_params is not None:
            weights = self.trained_params
        else:
            # Fall back to zero weights if model has not been trained yet
            weights = np.zeros(len(trainable_params))

        for p, v in zip(
            sorted(trainable_params, key=lambda p: p.name),
            weights,
        ):
            param_dict[p] = v

        bound_circuit = circuit.assign_parameters(param_dict)
        if bound_circuit.parameters:
            print(f"[DEBUG] Unbound parameters remaining: {[p.name for p in bound_circuit.parameters]}")
            print(f"[DEBUG] features size: {len(features)}, expected: {self.feature_count}")
            print(f"[DEBUG] feature_params count: {len(feature_params)}, trainable_params count: {len(trainable_params)}")
            print(f"[DEBUG] weights size: {len(weights)}")
            print(f"[DEBUG] param_dict size: {len(param_dict)}, unique keys: {len(set(param_dict.keys()))}")

        return bound_circuit

    # ------------------------------------------------------------------
    # Routing (single packet)
    # ------------------------------------------------------------------

    def route_packet(self, features: np.ndarray) -> Tuple[str, float]:
        """Route a single packet based on its extracted features.

        If the quantum backend is unavailable (Qiskit not installed or
        initialisation failed) the router transparently falls back to
        a simple classical heuristic.

        Parameters
        ----------
        features : np.ndarray
            1-D array of shape ``(feature_count,)``.

        Returns
        -------
        tuple[str, float]
            ``(reconciler_name, confidence)`` — the selected reconciler
            and a confidence score in ``[0, 1]``.
        """
        if self._backend is None:
            self._init_backend()

        if self._backend is None:
            # Fallback to classical heuristic if quantum not available
            return self._classical_fallback(features)

        circuit = self._build_vqc_circuit(features)
        bound_circuit = self._bind_features(circuit, features)

        try:
            from qiskit import transpile  # type: ignore[import-untyped]
        except ImportError:
            return self._classical_fallback(features)

        transpiled = transpile(bound_circuit, self._backend)

        # Use SamplerV2 primitives for IBM Runtime backends (backend.run()
        # has been removed); fall back to legacy .run() for AerSimulator.
        counts: Dict[str, int] = {}
        try:
            from qiskit_ibm_runtime import IBMBackend  # type: ignore[import-untyped]
            is_ibm = isinstance(self._backend, IBMBackend)
        except ImportError:
            is_ibm = False

        if is_ibm:
            from qiskit_ibm_runtime import SamplerV2 as Sampler  # type: ignore[import-untyped]
            sampler = Sampler(self._backend)
            sampler.options.default_shots = self.shots
            job = sampler.run([transpiled])
            result = job.result()
            pub_result = result[0]
            # Default classical register name is 'c' for QuantumCircuit(n, m)
            counts = pub_result.data.c.get_counts()
        else:
            job = self._backend.run(transpiled, shots=self.shots)
            counts = job.result().get_counts()

        # Decode measurement: most frequent bitstring -> class index
        best_bitstring: str = max(counts, key=counts.get)  # type: ignore[arg-type]
        class_idx: int = int(best_bitstring, 2)
        confidence: float = counts[best_bitstring] / self.shots

        # Clamp to valid classes
        if class_idx >= self.num_classes:
            class_idx = 2  # Default to BERT for out-of-range

        reconciler: str = self.RECONCILER_CLASSES[class_idx]
        return reconciler, confidence

    # ------------------------------------------------------------------
    # Routing (batch)
    # ------------------------------------------------------------------

    def route_batch(
        self, feature_batch: np.ndarray
    ) -> List[Tuple[str, float]]:
        """Route a batch of packets.

        Parameters
        ----------
        feature_batch : np.ndarray
            2-D array of shape ``(N, feature_count)`` where each row is
            a packet's feature vector.

        Returns
        -------
        list[tuple[str, float]]
            One ``(reconciler_name, confidence)`` pair per packet.
        """
        results: List[Tuple[str, float]] = []
        for features in feature_batch:
            results.append(self.route_packet(features))
        return results

    # ------------------------------------------------------------------
    # Classical fallback
    # ------------------------------------------------------------------

    def _classical_fallback(self, features: np.ndarray) -> Tuple[str, float]:
        """Simple heuristic fallback when the quantum backend is unavailable.

        Uses feature thresholds derived from MI250X benchmark insights.
        Features are expected to be normalised to ``[0, π]`` (angle
        encoding convention).

        Decision logic
        ~~~~~~~~~~~~~~
        * Low edit distance + no structural / type changes → **levenshtein**
        * Few removed fields + no structural changes → **regex**
        * Everything else → **bert** (highest-capability reconciler)
        """
        # Denormalise key features from [0, π] back to [0, 1]
        key_edit_dist: float = features[6] / math.pi    # index 6: key_edit_distance_mean
        has_type_changes: float = features[7] / math.pi  # index 7
        has_structural: float = features[8] / math.pi    # index 8
        fields_removed: float = features[5] / math.pi    # index 5

        if (
            key_edit_dist < 0.3
            and has_structural < 0.5
            and has_type_changes < 0.5
        ):
            return "levenshtein", 0.8
        elif fields_removed < 0.1 and has_structural < 0.5:
            return "regex", 0.7
        else:
            return "bert", 0.9

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        maxiter: int = 200,
        callback: Optional[object] = None,
    ) -> Dict[str, object]:
        """Train the VQC on labelled data.

        Parameters
        ----------
        X_train : np.ndarray
            Feature matrix of shape ``(N, feature_count)``.
        y_train : np.ndarray
            Integer label vector of shape ``(N,)`` with values in
            ``{0, 1, 2}`` (or ``{0, 1, 2, 3}`` if Gemma is enabled).
        maxiter : int
            Maximum number of COBYLA optimiser iterations.
        callback : callable | None
            Optional ``callback(iteration, params, cost)`` invoked each
            optimiser step.

        Returns
        -------
        dict
            Training metrics including accuracy, sample count, and
            optimiser configuration.

        Raises
        ------
        ImportError
            If required Qiskit packages are not installed.
        """
        if self._backend is None:
            self._init_backend()

        try:
            from qiskit.circuit.library import (  # type: ignore[import-untyped]
                RealAmplitudes,
                ZZFeatureMap,
            )
            from qiskit_aer import AerSimulator  # type: ignore[import-untyped]
            from qiskit_algorithms.optimizers import COBYLA  # type: ignore[import-untyped]
            from qiskit_machine_learning.algorithms import VQC  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "[QuantumRouter] Training requires qiskit, qiskit-aer, "
                "qiskit-algorithms, and qiskit-machine-learning. "
                "Install with: pip install -r requirements-quantum.txt"
            ) from exc

        # Train on 12 qubits to match the evaluation circuit shape
        total_qubits = self.feature_count + self.num_output_qubits
        feature_map = ZZFeatureMap(feature_dimension=total_qubits, reps=2)
        ansatz = RealAmplitudes(num_qubits=total_qubits, reps=2)
        optimizer = COBYLA(maxiter=maxiter)

        backend = self._backend or AerSimulator()

        vqc = VQC(
            feature_map=feature_map,
            ansatz=ansatz,
            optimizer=optimizer,
            num_qubits=total_qubits,
        )

        # One-hot encode labels
        num_classes: int = self.num_classes
        y_onehot: np.ndarray = np.zeros((len(y_train), num_classes))
        for i, label in enumerate(y_train):
            y_onehot[i, int(label)] = 1

        # Pad feature space with zeros to match VQC's 12-qubit feature map requirement
        X_train_padded = np.pad(X_train, ((0, 0), (0, self.num_output_qubits)), mode='constant')

        result = vqc.fit(X_train_padded, y_onehot)

        # Store trained parameters
        self.trained_params = vqc.weights

        # Evaluate training accuracy
        y_pred: np.ndarray = vqc.predict(X_train_padded)
        train_accuracy: float = float(
            np.mean(np.argmax(y_pred, axis=1) == y_train)
        )

        return {
            "train_accuracy": train_accuracy,
            "n_samples": len(X_train),
            "n_classes": num_classes,
            "maxiter": maxiter,
            "optimizer": "COBYLA",
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_params(self, path: str) -> None:
        """Save trained parameters and router config to a JSON file.

        Parameters
        ----------
        path : str
            Destination file path (will be created / overwritten).
        """
        data: Dict[str, object] = {
            "trained_params": (
                self.trained_params.tolist()
                if self.trained_params is not None
                else None
            ),
            "num_classes": self.num_classes,
            "feature_count": self.feature_count,
            "mode": self.mode,
            "enable_gemma": self.enable_gemma,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_params(self, path: str) -> None:
        """Load trained parameters from a JSON file.

        Parameters
        ----------
        path : str
            Path to a JSON file previously written by :pymeth:`save_params`.
        """
        with open(path, "r") as f:
            data: Dict = json.load(f)
        if data.get("trained_params"):
            self.trained_params = np.array(data["trained_params"])
        self.num_classes = data.get("num_classes", 3)
        self.feature_count = data.get("feature_count", 10)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_routing_stats(self) -> Dict[str, object]:
        """Return a summary of the router's current configuration.

        Returns
        -------
        dict
            Keys include ``backend``, ``mode``, ``num_classes``,
            ``feature_count``, ``shots``, ``enable_gemma``,
            ``is_trained``, and ``total_qubits``.
        """
        return {
            "backend": self.backend_name,
            "mode": self.mode,
            "num_classes": self.num_classes,
            "feature_count": self.feature_count,
            "shots": self.shots,
            "enable_gemma": self.enable_gemma,
            "is_trained": self.trained_params is not None,
            "total_qubits": self.feature_count + self.num_output_qubits,
        }
