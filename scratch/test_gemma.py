import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from semantic_benchmark.model_loaders import StrictGemmaModel
from semantic_benchmark.reconcilers import GemmaReconciler

def main():
    print("Loading Gemma model...")
    gemma_model = StrictGemmaModel(require_local=True)
    gemma = GemmaReconciler(gemma_model)
    
    canonical_keys = ["price", "cost", "amount", "monetary", "usd", "val"]
    query_key = "prc"
    
    print("\nTesting Gemma Reconciler directly...")
    res = gemma.reconcile(canonical_keys, query_key)
    print("Reconcile Result:")
    print(res)
    
    print("\nTesting Gemma Model raw generate directly...")
    prompt = (
        f"Given a list of canonical API schema fields: {canonical_keys}\n"
        f"And a query key from a drifted/mutated schema: \"{query_key}\"\n\n"
        "Select the canonical field that is the best semantic match for this query key.\n"
        "Return your response strictly in the following JSON format:\n"
        '{"match": "canonical_field_name", "confidence": 0.0}'
    )
    raw_response = gemma_model.generate(prompt, max_new_tokens=128, temperature=0.0)
    print("Raw Response:")
    print(repr(raw_response))

if __name__ == "__main__":
    main()
