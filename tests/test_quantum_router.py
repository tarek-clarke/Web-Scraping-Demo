import unittest
import numpy as np
from src.routing.quantum_router import QuantumRouter

class TestQuantumRouter(unittest.TestCase):
    def setUp(self):
        # Use aer_simulator for tests to avoid hardware dependencies
        self.router = QuantumRouter(backend="aer_simulator")

    def test_classical_fallback(self):
        # Test the classical fallback logic
        features = np.zeros(10)
        # Low edit distance, no structural -> levenshtein
        rec, conf = self.router._classical_fallback(features)
        self.assertEqual(rec, "levenshtein")

if __name__ == "__main__":
    unittest.main()
