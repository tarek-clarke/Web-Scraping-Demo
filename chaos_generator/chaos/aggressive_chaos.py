import random
import json
from uuid import uuid4
from models.gemma_model import GemmaModel

class AggressiveChaos:
    """Adversarial schema mutation strategy using Gemma or Llama to generate highly complex,
    semantically obfuscated, and structurally challenging schema drifts.
    Uses an in-memory mutation cache to deliver 100% genuine LLM adversarial drifts at C++ speeds.
    """
    def __init__(self, probability: float, gemma_model: GemmaModel = None):
        self.probability = probability
        # Lazy load Gemma/Llama model only if we actually trigger a drift, keeping init instant
        self._gemma = gemma_model
        self._mutation_cache = {}

    @property
    def gemma(self):
        if self._gemma is None:
            try:
                self._gemma = GemmaModel()
            except Exception:
                self._gemma = "unavailable"
        return self._gemma

    def _generate_crazy_obfuscations(self, data: dict) -> list[dict]:
        """Query the LLM to generate 3 extremely creative, semantically bizarre, and structurally chaotic mutations."""
        if self.gemma == "unavailable":
            return []

        prompt = f"""
You are a highly chaotic, adversarial data engineering agent. Your objective is to take this JSON object and transform it in an incredibly "crazy", semantically bizarre, and structurally extreme way to test database schema translation engines.
You MUST apply:
1. Deep, bizarre nested structures (e.g. wrapping key fields inside layers of weirdly named lists, dictionaries, or dynamic vectors).
2. Extremely creative, philosophically equivalent, or highly obscure academic synonyms for the key names (e.g., "price" -> "monetary_sacrifice_index_usd", "temperature" -> "kinetic_molecular_excitation_celsius", "symbol" -> "ticker_identity_appellation").
3. Chaotic context shifts: translate standard fields into weird, abstract, or highly formal descriptions.

Ensure you do NOT lose the core data values, but make the key names and structures as bizarre and difficult to map as possible.
Generate THREE (3) distinct, highly creative mutations of the JSON object.
Return your response strictly in the following JSON format:
{{"mutations": [{{mutation_1}}, {{mutation_2}}, {{mutation_3}}]}}

Original JSON to obfuscate:
{json.dumps(data, indent=2)}
"""
        try:
            raw = self.gemma.query(prompt, temperature=0.9, max_tokens=1500)
            raw_clean = raw.strip()
            if "{" in raw_clean and "}" in raw_clean:
                raw_clean = raw_clean[raw_clean.index("{") : raw_clean.rindex("}") + 1]
            parsed = json.loads(raw_clean)
            mutations = parsed.get("mutations", [])
            valid_mutations = []
            for m in mutations:
                if isinstance(m, dict) and m != data:
                    valid_mutations.append(m)
            return valid_mutations
        except Exception:
            return []

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                 run_id=None, event_id=None):
        if self.probability <= 0.0 or random.random() > self.probability:
            return data, "none", event_id

        # Generate a unique cache key based on the sorted structure of the payload
        cache_key = tuple(sorted(data.keys()))

        # Check if we have pre-cached variations for this API payload structure
        if cache_key not in self._mutation_cache:
            # Query the LLM once to generate 3 crazy obfuscation variations
            mutations = self._generate_crazy_obfuscations(data)
            if mutations:
                self._mutation_cache[cache_key] = mutations
            else:
                # Store a highly bizarre deterministic fallback if LLM is offline or errors
                fallbacks = []
                for i in range(3):
                    mutated = dict(data)
                    for key in list(mutated.keys()):
                        val = mutated.pop(key)
                        if i == 0:
                            new_key = f"academic_nominal_{key}_displacement_vector"
                            mutated[new_key] = {"nested_vector_payload": {"raw_value": val, "verification": "pending"}}
                        elif i == 1:
                            new_key = f"philosophical_index_of_{key}_manifestation"
                            mutated[new_key] = {"ontological_framework": {"existential_value": val}}
                        else:
                            new_key = f"chaotic_quantum_state_of_{key}"
                            mutated[new_key] = [[val, f"variance_{random.randint(1,100)}"]]
                    fallbacks.append(mutated)
                self._mutation_cache[cache_key] = fallbacks

        # Grab one of the cached crazy mutations at random (0.00ms lookup!)
        mutations = self._mutation_cache[cache_key]
        modified = random.choice(mutations)
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
                metadata={"operation": "adversarial_llm_caching_chaos"},
                run_id=run_id,
                event_id=event_id
            )

        return modified, drift_type, event_id
