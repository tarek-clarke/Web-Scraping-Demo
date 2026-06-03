import json
from typing import Dict, List, Tuple
from .levenshtein_rec import LevenshteinReconciler
from .regex_rec import RegexReconciler
from .bert_rec import BERTReconciler
from .gemma_e4b_rec import GemmaE4BReconciler
from .gemma_31b_rec import Gemma31BReconciler

class ReconciliationEngine:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.batch_size = batch_size
        self.reconcilers = {
            "levenshtein": LevenshteinReconciler(),
            "regex": RegexReconciler(),
            "bert": BERTReconciler(hardware_profile, batch_size),
            "gemma_e4b": GemmaE4BReconciler(hardware_profile, batch_size),
            "gemma_31b": Gemma31BReconciler(hardware_profile, batch_size)
        }

    def reconcile(self, original: Dict, drifted: Dict, method: str) -> Dict:
        if method not in self.reconcilers:
            raise ValueError(f"Unknown method: {method}")
        
        reconciler = self.reconcilers[method]
        
        original_data = original.get("data", {})
        drifted_data = drifted.get("data", {})
        
        result = reconciler.reconcile(original_data, drifted_data)
        
        return {
            "method": method,
            "accuracy": result["accuracy"],
            "latency_ms": result["latency_ms"],
            "mapped_fields": result["mapped_fields"],
            "unmapped_fields": result["unmapped_fields"],
            "batch_size": self.batch_size
        }
