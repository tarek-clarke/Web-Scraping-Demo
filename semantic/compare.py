from semantic.levenshtein import LevenshteinReconciler
from semantic.regex_recon import RegexReconciler
from semantic.bert_recon import BERTReconciler
from semantic.gemma_recon import GemmaReconciler
from models.bert_model import BERTModel
from models.gemma_model import GemmaModel

class SchemaComparer:
    def __init__(self, bert_model: BERTModel = None, gemma_model: GemmaModel = None):
        self.levenshtein = LevenshteinReconciler()
        self.regex = RegexReconciler()
        self.bert = BERTReconciler(bert_model)
        self.gemma = GemmaReconciler(gemma_model)

    def compare_algorithms(self, canonical_keys: list, query_key: str) -> dict:
        """
        Orchestrates and compares matching outcomes across all four algorithms.
        """
        return {
            "levenshtein": self.levenshtein.reconcile(canonical_keys, query_key),
            "regex": self.regex.reconcile(canonical_keys, query_key),
            "bert": self.bert.reconcile(canonical_keys, query_key),
            "gemma": self.gemma.reconcile(canonical_keys, query_key)
        }
