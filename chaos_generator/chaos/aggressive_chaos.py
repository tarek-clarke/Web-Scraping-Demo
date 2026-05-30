import random
import json
from uuid import uuid4
from models.gemma_model import GemmaModel

class AggressiveChaos:
    """Adversarial schema mutation strategy using Gemma to generate highly complex,
    semantically obfuscated, and structurally challenging schema drifts.
    """
    def __init__(self, probability: float, gemma_model: GemmaModel = None):
        self.probability = probability
        self.gemma = gemma_model or GemmaModel()

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                 run_id=None, event_id=None):
        if self.probability <= 0.0 or random.random() > self.probability:
            return data, "none", event_id

        # Use Gemma to create highly aggressive, obfuscated structural and semantic mutations
        prompt = f"""
You are an adversarial data engineering agent. Your objective is to take this JSON object and transform it in a highly complex, semantically obfuscated, and aggressive way to challenge database schema reconciliation engines.
You MUST apply:
1. Deep nested structures (wrapping key fields in complex nested dictionaries or lists).
2. Aggressive, highly academic or extremely verbose synonyms for the key names (e.g., "name" -> "nominal_designation_appellation_token", "price" -> "monetary_compensation_equivalent_usd").
3. Intentionally confusing type-mismatches (e.g. converting floats to string expressions, or active state booleans into pending status strings).

Ensure you do NOT lose the core information of the data, but make it as difficult as possible to reconstruct semantically.
Return your result STRICTLY in raw JSON format inside a single code block.

Original JSON:
{json.dumps(data, indent=2)}

Obfuscated JSON:
"""
        try:
            raw = self.gemma.query(prompt, temperature=0.8, max_tokens=500)
            raw_clean = raw.strip()
            if "{" in raw_clean and "}" in raw_clean:
                raw_clean = raw_clean[raw_clean.index("{") : raw_clean.rindex("}") + 1]
            modified = json.loads(raw_clean)
            if isinstance(modified, dict) and modified != data:
                drift_type = "aggressive_obfuscation"
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="aggressive",
                        chaos_level=self.probability,
                        drift_type=drift_type,
                        original_field="multiple",
                        mutated_field="obfuscated_json",
                        metadata={"operation": "adversarial_gemma_chaos"},
                        run_id=run_id,
                        event_id=event_id
                    )
                return modified, drift_type, event_id
        except Exception:
            pass

        # Fallback to a highly aggressive deterministic shuffle if Gemma fails
        mutated = dict(data)
        for key in list(mutated.keys()):
            val = mutated.pop(key)
            new_key = f"academic_nominal_{key}_displacement_token"
            mutated[new_key] = {"nested_vector_payload": {"raw_value": val, "metadata_verification": "pending"}}
        
        return mutated, "aggressive_deterministic_fallback", event_id
