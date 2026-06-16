import unittest
import numpy as np
import math
from src.routing.feature_extractor import FeatureExtractor

class TestFeatureExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = FeatureExtractor()
        
    def test_extract_basic(self):
        orig = {"a": 1, "b": "str", "c": {"d": 2}}
        drift = {"a": 1, "b_renamed": "str", "c": {"d": 2}, "e": 3}
        
        features = self.extractor.extract(orig, drift, "openf1")
        
        self.assertEqual(features.shape, (10,))
        self.assertTrue(np.all(features >= 0))
        self.assertTrue(np.all(features <= math.pi))
        
        # openf1 is 0.25 -> scaled by pi
        self.assertAlmostEqual(features[9], 0.25 * math.pi)

if __name__ == "__main__":
    unittest.main()
