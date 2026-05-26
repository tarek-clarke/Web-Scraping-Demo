import random
import json
from models.gemma_offline import GemmaModel

class GemmaChaos:
    def __init__(self, probability: float, gemma_model: GemmaModel = None):
        self.probability = probability
        self.gemma = gemma_model or GemmaModel()

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

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated, drift_type = self.apply_chaos(data, drift_logger, run_number, api_source)
        return mutated, drift_type

    def _paraphrase_value(self, val: str) -> str:
        if not isinstance(val, str):
            return val
        for k, v in self.paraphrases.items():
            if k.lower() in val.lower():
                return val.lower().replace(k.lower(), v)
        prompt = f"Paraphrase this short API string value to be verbose and semantically drifted but keep original meaning: \"{val}\". Return ONLY the paraphrased string."
        return self.gemma.query(prompt, temperature=0.7).strip().strip('"')

    def _adversarial_rename_field(self, key: str) -> str:
        for k, v in self.adversarial_renames.items():
            if k in key:
                return v
        prompt = f"Create an overly verbose, academic, or adversarial synonym for the API schema field name \"{key}\" (e.g., price -> monetary_exchange_value). Return ONLY the new field name in snake_case."
        return self.gemma.query(prompt, temperature=0.7).strip().strip('"').replace(" ", "_")

    def _apply_semantic_drift(self, key: str, val):
        if "temp" in key or "temperature" in key:
            return f"{key}_heat_index", val + 2.0
        if "active" in key:
            return "verification_pending", False
        if "price" in key:
            return "original_cost_before_inflation", val * 1.15
        return f"{key}_semantically_drifted", val

    def _structural_drift(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """Use Gemma to generate a structurally drifted version of the data."""
        prompt = f"""
You are a data mutation engine. Given the following JSON object, produce a structurally different JSON object.
You may split fields, merge fields, rename keys, or restructure nesting.
Do NOT change the meaning of the data. Return ONLY the modified JSON object.

Original JSON:
{json.dumps(data, indent=2)}

Modified JSON:
"""
        try:
            raw = self.gemma.query(prompt, temperature=0.7, max_tokens=500)
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                raw_clean = raw_clean.split("\n", 1)[1]
                if "```" in raw_clean:
                    raw_clean = raw_clean.split("```")[0]
            modified = json.loads(raw_clean)
            if isinstance(modified, dict) and modified != data:
                return modified, "gemma_structural"
        except Exception:
            pass
        # fallback: apply deterministic split/merge
        return self._split_or_merge_fallback(data, drift_logger, run_number, api_source)

    def _split_or_merge_fallback(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        if random.random() < 0.5:
            return self._split_field(data, drift_logger, run_number, api_source)
        else:
            return self._merge_fields(data, drift_logger, run_number, api_source)

    def _split_field(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        keys = list(data.keys())
        if not keys:
            return data, None
        target_key = random.choice(keys)
        target_val = data[target_key]
        # simplest split: if string with space
        if isinstance(target_val, str) and " " in target_val:
            parts = target_val.split(" ", 1)
            new_data = dict(data)
            new_data[f"{target_key}_first"] = parts[0]
            new_data[f"{target_key}_second"] = parts[1]
            del new_data[target_key]
            drift_type = "gemma_split"
        elif isinstance(target_val, (int, float)) and not isinstance(target_val, bool):
            int_part = int(target_val)
            frac_part = int((target_val - int_part) * 1000000)
            new_data = dict(data)
            new_data[f"{target_key}_integer"] = int_part
            new_data[f"{target_key}_fraction"] = frac_part
            del new_data[target_key]
            drift_type = "gemma_split"
        else:
            # Duplicate
            new_data = dict(data)
            new_data[f"{target_key}_copy"] = target_val
            drift_type = "gemma_split_duplicate"
        if drift_logger:
            drift_logger.log_event(
                api_source=api_source,
                run_number=run_number,
                chaos_strategy="gemma",
                chaos_level=self.probability,
                drift_type=drift_type,
                original_field=target_key,
                mutated_field=list(new_data.keys()),
                metadata={"fallback": True}
            )
        return new_data, drift_type

    def _merge_fields(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        keys = list(data.keys())
        if len(keys) < 2:
            return data, None
        idx = random.randint(0, len(keys) - 2)
        key1, key2 = keys[idx], keys[idx+1]
        val1, val2 = data[key1], data[key2]
        if isinstance(val1, str) and isinstance(val2, str):
            merged_val = val1 + " " + val2
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            merged_val = val1 + val2
        else:
            merged_val = f"{val1},{val2}"
        merged_key = f"{key1}_{key2}"
        new_data = dict(data)
        new_data[merged_key] = merged_val
        del new_data[key1]
        del new_data[key2]
        drift_type = "gemma_merge"
        if drift_logger:
            drift_logger.log_event(
                api_source=api_source,
                run_number=run_number,
                chaos_strategy="gemma",
                chaos_level=self.probability,
                drift_type=drift_type,
                original_field=f"{key1},{key2}",
                mutated_field=merged_key,
                metadata={"fallback": True}
            )
        return new_data, drift_type

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """
        Applies Gemma-level advanced semantic drift chaos based on target probability.
        Logs every event via drift_logger.
        Returns (mutated_data, drift_type).
        """
        # Always apply structural drift with gemma
        mutated_data, drift_type = self._structural_drift(data, drift_logger, run_number, api_source)

        # Then apply key/value mutations with given probability
        final_data = {}
        for key, val in mutated_data.items():
            new_key = key
            new_val = val

            if isinstance(val, dict):
                final_data[key] = val
                continue

            if random.random() < self.probability:
                drift_type_key = random.choice(["adversarial_rename", "semantic_drift"])
                if drift_type_key == "adversarial_rename":
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
                else:
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

        return final_data, drift_type
