import json
from typing import Dict, List, Tuple
from .levenshtein_rec import LevenshteinReconciler
from .regex_rec import RegexReconciler
from .bert_rec import BERTReconciler
from .gemma_e4b_rec import GemmaE4BReconciler
from .nemotron_rec import NemotronReconciler

class ReconciliationEngine:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.batch_size = batch_size
        self.reconcilers = {
            "levenshtein": LevenshteinReconciler(),
            "regex": RegexReconciler(),
            "bert": BERTReconciler(hardware_profile, batch_size),
            "gemma_e4b": GemmaE4BReconciler(hardware_profile, batch_size),
            "nemotron": NemotronReconciler(hardware_profile, batch_size),
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
            "reconciled_data": result.get("reconciled_data", original_data),
            "batch_size": self.batch_size
        }

    def reconcile_bert_batch(self, pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        bert = self.reconcilers.get("bert")
        if bert and hasattr(bert, "reconcile_batch"):
            return bert.reconcile_batch(pairs)
        return [
            self.reconcile({"data": orig}, {"data": drift}, "bert")
            for orig, drift in pairs
        ]

    def reconcile_gemma_batch(self, pairs: List[Tuple[Dict, Dict]], progress_cb=None) -> List[Dict]:
        gemma = self.reconcilers.get("gemma_e4b")
        if gemma and hasattr(gemma, "reconcile_batch"):
            return gemma.reconcile_batch(pairs, progress_cb=progress_cb)
        return [
            self.reconcile({"data": orig}, {"data": drift}, "gemma_e4b")
            for orig, drift in pairs
        ]

    def reconcile_nemotron_batch(self, pairs: List[Tuple[Dict, Dict]], progress_cb=None) -> List[Dict]:
        nemotron = self.reconcilers.get("nemotron")
        if nemotron and hasattr(nemotron, "reconcile_batch"):
            return nemotron.reconcile_batch(pairs, progress_cb=progress_cb)
        return [
            self.reconcile({"data": orig}, {"data": drift}, "nemotron")
            for orig, drift in pairs
        ]

    def route_and_reconcile(self, original: Dict, drifted: Dict, router: object, feature_extractor: object) -> Dict:
        import time
        start_time = time.perf_counter()
        
        # Extract features
        original_data = original.get("data", {})
        drifted_data = drifted.get("data", {})
        source = original.get("source", "unknown")
        
        features = feature_extractor.extract(original_data, drifted_data, source)
        
        # Quantum route
        reconciler_name, confidence = router.route_packet(features)
        routing_latency_ms = (time.perf_counter() - start_time) * 1000
        
        # Reconcile using selected reconciler
        rec_result = self.reconcile(original, drifted, reconciler_name)
        
        # Merge routing metrics
        rec_result["routing_decision"] = reconciler_name
        rec_result["routing_confidence"] = confidence
        rec_result["routing_latency_ms"] = routing_latency_ms
        return rec_result
