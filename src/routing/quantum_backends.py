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
    """IBM Quantum/Cloud hardware backend."""

    def __init__(self, instance: str = "ibm-q/open/main", min_qubits: int = 12) -> None:
        self.instance = instance
        self.min_qubits = min_qubits
        self._backend = None

    def _init(self) -> None:
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            service = None

            # 1. Try loading as ibm_cloud first if the instance is a CRN
            if self.instance and self.instance.startswith("crn:"):
                try:
                    service = QiskitRuntimeService(channel="ibm_cloud", instance=self.instance)
                except Exception as e:
                    print(f"[IBMQuantumBackend] Failed to load via ibm_cloud with instance CRN: {e}")

            # 2. Try loading default saved accounts (from environment/file)
            if service is None:
                try:
                    service = QiskitRuntimeService()
                except Exception:
                    pass

            # 3. Try loading ibm_cloud channel generally
            if service is None:
                try:
                    service = QiskitRuntimeService(channel="ibm_cloud")
                except Exception:
                    pass

            # 4. Try loading ibm_quantum_platform channel generally
            if service is None:
                try:
                    service = QiskitRuntimeService(channel="ibm_quantum_platform", instance=self.instance)
                except Exception:
                    pass

            if service is None:
                raise ValueError("Could not initialize QiskitRuntimeService on any channel. Please check your credentials.")

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
    """LUMI-Q hardware backend (VTT 24-qubit or VTT Q50) via FiQCI."""

    def __init__(self, endpoint: Optional[str] = None) -> None:
        import os
        # Fall back to env var HELMI_CORTEX_URL if no endpoint is passed explicitly
        self.endpoint = endpoint or os.getenv("HELMI_CORTEX_URL")
        self._backend = None

    def _init(self) -> None:
        if not self.endpoint:
            raise ValueError(
                "LUMI-Q Cortex URL is not configured. Please export HELMI_CORTEX_URL or pass --endpoint."
            )
        try:
            # Support both package layouts of qiskit-iqm
            try:
                from iqm.qiskit_iqm import IQMProvider
            except ImportError:
                from qiskit_iqm import IQMProvider

            provider = IQMProvider(self.endpoint)
            self._backend = provider.get_backend()
        except ImportError:
            raise ImportError(
                "qiskit-iqm is not installed. Please run: pip install qiskit-iqm"
            )

    def execute_circuit(self, circuit, shots: int = 1024) -> Dict:
        if self._backend is None:
            try:
                self._init()
            except Exception as e:
                print(f"[LumiQBackend] Failed to connect to physical QPU ({e}). Falling back to AerSimulator.")
                from qiskit_aer import AerSimulator
                sim = AerSimulator()
                from qiskit import transpile
                transpiled = transpile(circuit, sim)
                job = sim.run(transpiled, shots=shots)
                return job.result().get_counts()

        from qiskit import transpile
        transpiled = transpile(circuit, self._backend)
        job = self._backend.run(transpiled, shots=shots)
        return job.result().get_counts()

    def get_backend_info(self) -> Dict:
        name = self._backend.name if self._backend else "lumi_q"
        return {
            "type": "quantum_hpc",
            "name": name,
            "provider": "FiQCI/VTT",
            "qubits": 24,
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
