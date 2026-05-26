import json
import time
from semantic.levenshtein import LevenshteinReconciler
from semantic.regex_recon import RegexReconciler
from semantic.bert_recon import BERTReconciler
from semantic.gemma_recon import GemmaReconciler
from models.bert_model import BERTModel
from models.gemma_offline import GemmaModel

class SchemaComparer:
    def __init__(self, bert_model: BERTModel = None, gemma_model: GemmaModel = None):
        self.levenshtein = LevenshteinReconciler()
        self.regex = RegexReconciler()
        self.bert = BERTReconciler(bert_model)
        self.gemma = GemmaReconciler(gemma_model)

    def classify_drift(self, original: dict, mutated: dict) -> dict:
        """Classify all drift types between original and mutated packets."""
        original_keys = set(original.keys())
        mutated_keys = set(mutated.keys())

        missing_keys = original_keys - mutated_keys
        extra_keys = mutated_keys - original_keys

        types_mismatch = 0
        value_contradiction = 0
        split_fields = 0
        merge_fields = 0
        nested_corruption = 0

        # type mismatch and value contradiction for common keys
        common_keys = original_keys & mutated_keys
        for key in common_keys:
            ov = original[key]
            mv = mutated[key]
            if type(ov) != type(mv):
                types_mismatch += 1
            else:
                if isinstance(ov, dict) and isinstance(mv, dict):
                    # nested corruption if dicts differ
                    if ov != mv:
                        nested_corruption += 1
                elif isinstance(ov, (str, int, float, bool)):
                    if ov != mv:
                        value_contradiction += 1

        # detect split: a missing key that is a prefix of at least two extra keys
        for mk in list(missing_keys):
            matching_extras = [ek for ek in extra_keys if ek.startswith(mk)]
            if len(matching_extras) >= 2:
                split_fields += 1
                extra_keys = extra_keys - set(matching_extras)

        # detect merge: an extra key that is a combination of at least two missing keys
        for ek in list(extra_keys):
            parts = ek.split('_')
            if len(parts) >= 2 and all(p in missing_keys for p in parts):
                merge_fields += 1
                missing_keys = missing_keys - set(parts)
                extra_keys = extra_keys - {ek}

        # renamed keys: each remaining missing key that has a similar extra key (Levenshtein <= 2)
        renamed_keys = 0
        remaining_missing = list(missing_keys)
        remaining_extra = list(extra_keys)
        for mk in remaining_missing[:]:
            best_dist = 999
            best_ek = None
            for ek in remaining_extra:
                dist = LevenshteinReconciler.distance(mk, ek)
                if dist < best_dist:
                    best_dist = dist
                    best_ek = ek
            if best_dist <= 2:
                renamed_keys += 1
                remaining_missing.remove(mk)
                remaining_extra.remove(best_ek)

        missing_keys_count = len(remaining_missing)
        extra_keys_count = len(remaining_extra)

        return {
            "missing_keys": missing_keys_count,
            "extra_keys": extra_keys_count,
            "renamed_keys": renamed_keys,
            "type_mismatch": types_mismatch,
            "value_contradiction": value_contradiction,
            "split_fields": split_fields,
            "merged_fields": merge_fields,
            "nested_corruption": nested_corruption
        }

    def detect_drift(self, original: dict, mutated: dict):
        drift_types = self.classify_drift(original, mutated)
        drift_detected = any(v > 0 for v in drift_types.values())
        drift_type_count = sum(drift_types.values())
        return drift_detected, drift_types, drift_type_count

    def process(self, mutated: dict, original: dict) -> dict:
        """Full pipeline: detect drift, reconcile, compute repair metrics."""
        drift_detected, drift_types, drift_type_count = self.detect_drift(original, mutated)

        # Reconcile using all algorithms (query_key = str(mutated))
        query_key = json.dumps(mutated)  # use full JSON as query
        # For reconciliation we need a list of canonical keys from original
        canonical_keys = list(original.keys())

        # Compare algorithms
        alg_results = self.compare_algorithms(canonical_keys, query_key)

        # Determine best match
        best_confidence = 0.0
        best_match = None
        for alg_name, res in alg_results.items():
            if res['confidence'] > best_confidence:
                best_confidence = res['confidence']
                best_match = res['match']
        fallback_used = best_confidence < 0.5
        reconciled_ok = not fallback_used and best_match is not None

        # repair_rate = fraction of drift types that were "repaired"
        # For simplicity, if drift detected and reconciled, repair_rate = 1.0 else 0.0
        if drift_detected and reconciled_ok:
            repair_rate = 1.0
        else:
            repair_rate = 0.0

        # recovery_score = semantic similarity between repaired and original
        # Use bert cosine similarity between whole packets as strings
        start = time.perf_counter()
        original_str = json.dumps(original)
        mutated_str = json.dumps(mutated)
        similarity = self.bert.bert.cosine_similarity(original_str, mutated_str)
        recovery_score = float(similarity)

        return {
            "drift_detected": drift_detected,
            "drift_types": drift_types,
            "drift_type_count": drift_type_count,
            "reconciliation_winner": best_match,
            "fallback_used": fallback_used,
            "reconciled_ok": reconciled_ok,
            "repair_rate": repair_rate,
            "recovery_score": recovery_score,
            "best_confidence": best_confidence,
            "algorithm_results": alg_results
        }

    def compare_algorithms(self, canonical_keys: list, query_key: str) -> dict:
        return {
            "levenshtein": self.levenshtein.reconcile(canonical_keys, query_key),
            "regex": self.regex.reconcile(canonical_keys, query_key),
            "bert": self.bert.reconcile(canonical_keys, query_key),
            "gemma": self.gemma.reconcile(canonical_keys, query_key)
        }
