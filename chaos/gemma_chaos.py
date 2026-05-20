import random
from models.gemma_offline import GemmaModel

class GemmaChaos:
    def __init__(self, probability: float, gemma_model: GemmaModel = None):
        self.probability = probability
        self.gemma = gemma_model or GemmaModel()
        
        # Heuristics lookup for instant local high-fidelity Gemma emulation
        self.adversarial_renames = {
            "price": "monetary_compensation_equivalent_usd",
            "temperature": "ambient_atmospheric_thermal_reading_celsius",
            "speed": "velocity_magnitude_vectors",
            "active": "pending_manual_verification_status",
            "name": "nominal_appellation_identifier",
            "timestamp": "temporal_coordinate_epoch_milliseconds",
            "wind_speed": "atmospheric_velocity_displacement",
            "capsule_serial": "spacecraft_module_alpha_numeric_tag",
            "driver_name": "motorsport_competitor_appellation"
        }
        
        self.paraphrases = {
            "Clear sky": "Fully unclouded celestial conditions",
            "Rainy": "High levels of liquid precipitation observed",
            "Active": "Operating in active nominal status",
            "SpaceX": "Space Exploration Technologies Corp",
            "Verstappen": "Max Verstappen (Red Bull Racing)"
        }

    def _paraphrase_value(self, val: str) -> str:
        if not isinstance(val, str):
            return val
        
        # Check local dictionary
        for k, v in self.paraphrases.items():
            if k.lower() in val.lower():
                return val.lower().replace(k.lower(), v)
                
        # Query local Gemma
        prompt = f"Paraphrase this short API string value to be verbose and semantically drifted but keep original meaning: \"{val}\". Return ONLY the paraphrased string."
        return self.gemma.query(prompt, temperature=0.7).strip().strip('"')

    def _adversarial_rename_field(self, key: str) -> str:
        # Check local dictionary
        for k, v in self.adversarial_renames.items():
            if k in key:
                return v
                
        # Query local Gemma
        prompt = f"Create an overly verbose, academic, or adversarial synonym for the API schema field name \"{key}\" (e.g., price -> monetary_exchange_value). Return ONLY the new field name in snake_case."
        return self.gemma.query(prompt, temperature=0.7).strip().strip('"').replace(" ", "_")

    def _apply_semantic_drift(self, key: str, val):
        # Slightly alter semantic meaning
        # e.g., active -> pending_verification, or temp -> heat_index
        if "temp" in key or "temperature" in key:
            return f"{key}_heat_index", val + 2.0
        if "active" in key:
            return "verification_pending", False
        if "price" in key:
            return "original_cost_before_inflation", val * 1.15
        return f"{key}_semantically_drifted", val

    def _apply_merge_split(self, data: dict) -> dict:
        # Pick two fields or restructure one
        # Let's say we split coordinate / location
        mutated = dict(data)
        keys = list(data.keys())
        
        # Restructure a lat/long or similar if present
        if "latitude" in data and "longitude" in data:
            lat = mutated.pop("latitude")
            lng = mutated.pop("longitude")
            mutated["coordinates"] = {"lat": lat, "lng": lng}
            return mutated
            
        # Group general details if possible
        if len(keys) >= 3:
            # nest first 2 keys into a "metadata_payload"
            k1, k2 = keys[0], keys[1]
            v1 = mutated.pop(k1)
            v2 = mutated.pop(k2)
            mutated["metadata_payload"] = {k1: v1, k2: v2}
            
        return mutated

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        """
        Applies Gemma-level advanced semantic drift chaos based on target probability.
        Logs every event via drift_logger.
        """
        mutated_data = {}
        merge_split_applied = False
        
        # Check if we should apply split/merge proposal
        if random.random() < self.probability:
            mutated_data = self._apply_merge_split(data)
            merge_split_applied = True
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="gemma",
                    chaos_level=self.probability,
                    drift_type="schema_merge_split_proposal",
                    original_field="schema_root",
                    mutated_field="schema_root_nested",
                    metadata={"keys_modified": list(data.keys())}
                )

        target_data = mutated_data if merge_split_applied else data
        final_data = {}

        for key, val in target_data.items():
            new_key = key
            new_val = val
            
            # Skip nesting fields from merge_split if they were already nested
            if isinstance(val, dict):
                final_data[key] = val
                continue

            # Roll dice for key mutations
            if random.random() < self.probability:
                drift_type = random.choice(["adversarial_rename", "semantic_drift"])
                
                if drift_type == "adversarial_rename":
                    new_key = self._adversarial_rename_field(key)
                    if drift_logger and new_key != key:
                        drift_logger.log_event(
                            api_source=api_source,
                            run_number=run_number,
                            chaos_strategy="gemma",
                            chaos_level=self.probability,
                            drift_type="adversarial_rename",
                            original_field=key,
                            mutated_field=new_key,
                            metadata={"method": "gemma_synthesis"}
                        )
                else: # semantic_drift
                    new_key, new_val = self._apply_semantic_drift(key, val)
                    if drift_logger:
                        drift_logger.log_event(
                            api_source=api_source,
                            run_number=run_number,
                            chaos_strategy="gemma",
                            chaos_level=self.probability,
                            drift_type="semantic_drift",
                            original_field=key,
                            mutated_field=new_key,
                            metadata={"mutated_value": new_val}
                        )

            # Roll dice for value mutations (paraphrases)
            if new_val == val and isinstance(val, str) and random.random() < self.probability:
                new_val = self._paraphrase_value(val)
                if drift_logger:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="gemma",
                        chaos_level=self.probability,
                        drift_type="value_paraphrase",
                        original_field=f"{new_key}_value",
                        mutated_field=f"{new_key}_value",
                        metadata={"original": val, "mutated": new_val}
                    )
            
            final_data[new_key] = new_val

        return final_data
