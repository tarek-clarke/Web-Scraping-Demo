import json
from typing import Dict, List, Tuple
from .levenshtein_rec import LevenshteinReconciler
from .regex_rec import RegexReconciler
from .bert_rec import BERTReconciler
from .gemma_e4b_rec import GemmaE2BReconciler
from .nemotron_rec import NemotronReconciler

class ReconciliationEngine:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.batch_size = batch_size
        self.reconcilers = {
            "levenshtein": LevenshteinReconciler(),
            "regex": RegexReconciler(),
            "bert": BERTReconciler(hardware_profile, batch_size),
            "gemma_e2b": GemmaE2BReconciler(hardware_profile, batch_size),
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

    def reconcile_levenshtein_batch(self, pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        lev = self.reconcilers.get("levenshtein")
        if lev and hasattr(lev, "reconcile_batch"):
            return lev.reconcile_batch(pairs)
        return [
            self.reconcile({"data": orig}, {"data": drift}, "levenshtein")
            for orig, drift in pairs
        ]

    def reconcile_gemma_batch(self, pairs: List[Tuple[Dict, Dict]], progress_cb=None) -> List[Dict]:
        gemma = self.reconcilers.get("gemma_e2b")
        if gemma and hasattr(gemma, "reconcile_batch"):
            return gemma.reconcile_batch(pairs, progress_cb=progress_cb)
        return [
            self.reconcile({"data": orig}, {"data": drift}, "gemma_e2b")
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
        
        # Policy: Drop gemma_e2b from routing UNLESS routing confidence is very low (< 0.40),
        # which indicates high ambiguity and justifies using the slower LLM reconciler.
        if reconciler_name == "gemma_e2b" and confidence >= 0.40:
            reconciler_name = "bert"
            
        # Reconcile using selected reconciler
        rec_result = self.reconcile(original, drifted, reconciler_name)
        
        # Determine optimal reconciler (lowest-latency satisfying 95% accuracy SLA)
        optimal_reconciler = "bert"
        try:
            lev_res = self.reconcilers["levenshtein"].reconcile(original_data, drifted_data)
            if lev_res.get("accuracy", 0.0) >= 0.95:
                optimal_reconciler = "levenshtein"
            else:
                reg_res = self.reconcilers["regex"].reconcile(original_data, drifted_data)
                if reg_res.get("accuracy", 0.0) >= 0.95:
                    optimal_reconciler = "regex"
        except Exception:
            pass

        # Merge routing metrics
        rec_result["routing_decision"] = reconciler_name
        rec_result["routing_confidence"] = confidence
        rec_result["routing_latency_ms"] = routing_latency_ms
        rec_result["optimal_reconciler"] = optimal_reconciler
        rec_result["routing_decision_match"] = (reconciler_name == optimal_reconciler)
        
        # Propagate QPU telemetry
        qpu_telemetry = getattr(router, "last_telemetry", {})
        rec_result["qpu_execution_time_ms"] = qpu_telemetry.get("qpu_execution_time_ms", 0.0)
        rec_result["classical_simulation_baseline_ms"] = qpu_telemetry.get("classical_simulation_baseline_ms", 0.0)
        rec_result["quantum_loop_iterations"] = qpu_telemetry.get("quantum_loop_iterations", 1)
        rec_result["gate_fidelity_average"] = qpu_telemetry.get("gate_fidelity_average", 0.99)
        rec_result["qubit_coherence_status_score"] = qpu_telemetry.get("qubit_coherence_status_score", 0.98)
        
        return rec_result
