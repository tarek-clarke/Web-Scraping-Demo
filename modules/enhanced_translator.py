#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
Enhanced Semantic Translator
============================
Core research component of the Resilient RAP framework.
Provides BERT-based semantic reconciliation for sensor name drift.
Includes Explainable AI (XAI) for mapping transparency.
"""

import time
import torch
from typing import List, Dict, Tuple, Optional
from sentence_transformers import SentenceTransformer, util
from modules.hitl_feedback import HITLFeedbackManager

class EnhancedSemanticTranslator:
    def __init__(self, canonical_schema: List[str], model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the translator with a canonical schema and a BERT model.
        """
        self.device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.canonical_schema = canonical_schema
        self.canonical_embeddings = self.model.encode(canonical_schema, convert_to_tensor=True)
        
        # Performance & Confidence Tracking
        self.history: List[Dict] = []
        self.confidence_threshold = 0.65
        self.hitl = HITLFeedbackManager()

    def translate(self, drifted_field: str) -> Dict:
        """
        Reconcile a drifted field name using the 3-Tier Resilient Architecture:
        Tier 1: Verified Translation Cache (Known mapping from HITL)
        Tier 2: Semantic Inference (BERT vector space)
        Tier 3: Expert Revision (Human-in-the-Loop Quarantine)
        """
        start_time = time.perf_counter()
        
        # ── Tier 1: Verified Translation Cache (O(1) Knowledge Base) ──
        # This matches the user's "Regex Database" concept: instant O(1) lookup.
        cache_match = self.hitl.get_correction(drifted_field)
        if cache_match and cache_match in self.canonical_schema:
            latency_ms = (time.perf_counter() - start_time) * 1000
            result = {
                "original": drifted_field,
                "mapped": cache_match,
                "confidence": 1.0,
                "latency_ms": round(latency_ms, 4),
                "reconciliation_type": "TIER_1_VERIFIED_CACHE",
                "explanation": f"O(1) Cache Hit: '{drifted_field}' -> '{cache_match}' (Previously human-validated)."
            }
            self.history.append(result)
            return result

        # ── Tier 2: Semantic Inference (O(n) Autonomous BERT) ────────
        # Handles unseen drift (synonyms, abbreviations) without manual rules.
        drift_embedding = self.model.encode(drifted_field, convert_to_tensor=True)
        cos_scores = util.cos_sim(drift_embedding, self.canonical_embeddings)[0]
        best_idx = torch.argmax(cos_scores).item()
        confidence = float(cos_scores[best_idx].item())
        mapped_field = self.canonical_schema[best_idx]
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        # Determine if we fallback to Tier 3 (Human Quarantine)
        is_confident = confidence >= self.confidence_threshold
        
        result = {
            "original": drifted_field,
            "mapped": mapped_field if is_confident else "unknown",
            "confidence": round(confidence, 4),
            "latency_ms": round(latency_ms, 4),
            "reconciliation_type": "TIER_2_BERT_SEMANTIC" if is_confident else "TIER_3_HITL_QUARANTINE",
            "explanation": self.explain(drifted_field, mapped_field, confidence)
        }
        
        self.history.append(result)
        return result

    def explain(self, drifted: str, mapped: str, score: float) -> str:
        """
        XAI Component: Provides a technical rationale for the mapping.
        """
        if score < self.confidence_threshold:
            return f"Low semantic similarity ({score:.4f}) detected. Field quarantined for HITL review."
        
        return (f"Mapped '{drifted}' to '{mapped}' with {score:.1%} semantic alignment. "
                "The BERT vector space suggests high contextual overlap between these identifiers.")

    @property
    def resilience_delta(self) -> float:
        """
        Measures the percentage of unknown fields successfully repaired.
        """
        if not self.history:
            return 1.0
        repaired = sum(1 for r in self.history if r["mapped"] != "unknown")
        return repaired / len(self.history)

if __name__ == "__main__":
    # Quick Smoke Test
    schema = ["speed", "rpm", "throttle", "brake_temp", "engine_temp"]
    translator = EnhancedSemanticTranslator(schema)
    
    test_fields = ["velocity_kph", "engine_thermal_c", "gas_pedal_pct"]
    for field in test_fields:
        res = translator.translate(field)
        print(f"[{res['confidence']}] {res['original']} -> {res['mapped']}")
        print(f"Reason: {res['explanation']}\n")
