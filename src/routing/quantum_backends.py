"""
quantum_backends.py – Abstract backend interface for quantum circuit execution.

Provides pluggable backends for the quantum routing module:
  - QiskitAerBackend  : local Aer simulator (default)
  - IBMQuantumBackend : IBM Quantum hardware via qiskit-ibm-runtime
  - LumiQBackend      : LUMI-Q / VTT Q50 (53-qubit) via FiQCI

Use the ``get_backend`` factory to instantiate by name.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class QuantumBackend(ABC):
    """Abstract quantum backend interface."""

    @abstractmethod
    def execute_circuit(self, circuit, shots: int = 1024) -> Dict:
        """Execute a quantum circuit and return measurement counts."""
        pass

    @abstractmethod
    def get_backend_info(self) -> Dict:
        """Return backend configuration info."""
        pass


class QiskitAerBackend(QuantumBackend):
    """Local Qiskit Aer simulator backend."""

    def __init__(self) -> None:
        self._simulator = None

    def _init(self) -> None:
        try:
            from qiskit_aer import AerSimulator
            self._simulator = AerSimulator()
        except ImportError:
            raise ImportError(
                "qiskit-aer not installed. Run: pip install -r requirements-quantum.txt"
            )

    def execute_circuit(self, circuit, shots: int = 1024) -> Dict:
        if self._simulator is None:
            self._init()
        from qiskit import transpile
        transpiled = transpile(circuit, self._simulator)
        job = self._simulator.run(transpiled, shots=shots)
        return job.result().get_counts()

    def get_backend_info(self) -> Dict:
        return {"type": "simulator", "name": "aer_simulator", "provider": "qiskit"}


class IBMQuantumBackend(QuantumBackend):
    """IBM Quantum hardware backend."""

    def __init__(self, instance: str = "ibm-q/open/main", min_qubits: int = 12) -> None:
        self.instance = instance
        self.min_qubits = min_qubits
        self._backend = None

    def _init(self) -> None:
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            service = QiskitRuntimeService(instance=self.instance)
            self._backend = service.least_busy(min_num_qubits=self.min_qubits)
        except ImportError:
            raise ImportError("qiskit-ibm-runtime not installed.")

    def execute_circuit(self, circuit, shots: int = 1024) -> Dict:
        if self._backend is None:
            self._init()
        from qiskit import transpile
        transpiled = transpile(circuit, self._backend)
        job = self._backend.run(transpiled, shots=shots)
        return job.result().get_counts()

    def get_backend_info(self) -> Dict:
        name = self._backend.name if self._backend else "not_initialized"
        return {
            "type": "hardware",
            "name": name,
            "provider": "ibm_quantum",
            "instance": self.instance,
        }


class LumiQBackend(QuantumBackend):
    """LUMI-Q backend placeholder for VTT Q50 (53 qubits) via FiQCI."""

    def __init__(self, endpoint: Optional[str] = None) -> None:
        self.endpoint = endpoint
        self._backend = None

    def execute_circuit(self, circuit, shots: int = 1024) -> Dict:
        if self.endpoint is None:
            # Fall back to Aer simulator when LUMI-Q access not configured
            print("[LumiQBackend] No endpoint configured, falling back to AerSimulator")
            fallback = QiskitAerBackend()
            return fallback.execute_circuit(circuit, shots)
        # Future: implement IQM/FiQCI client connection
        raise NotImplementedError(
            "LUMI-Q backend requires FiQCI access. Set endpoint in config."
        )

    def get_backend_info(self) -> Dict:
        return {
            "type": "quantum_hpc",
            "name": "lumi_q",
            "provider": "FiQCI/VTT",
            "qubits": 53,
            "endpoint": self.endpoint,
        }


def get_backend(name: str, **kwargs) -> QuantumBackend:
    """Factory function to get a quantum backend by name.

    Parameters
    ----------
    name : str
        One of ``"aer_simulator"``, ``"ibm_quantum"``, or ``"lumi_q"``.
    **kwargs
        Forwarded to the backend constructor.

    Returns
    -------
    QuantumBackend
        An initialised backend instance.
    """
    backends = {
        "aer_simulator": QiskitAerBackend,
        "ibm_quantum": IBMQuantumBackend,
        "lumi_q": LumiQBackend,
    }
    if name not in backends:
        print(f"[WARNING] Unknown backend '{name}', falling back to aer_simulator")
        return QiskitAerBackend()
    return backends[name](**kwargs)
