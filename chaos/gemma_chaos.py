import random
import json
from uuid import uuid4
from models.gemma_model import GemmaModel

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

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                 run_id=None, event_id=None):
        mutated, drift_type, event_id_out = self.apply_chaos(data, drift_logger, run_number, api_source,
                                                              run_id=run_id, event_id=event_id)
        return mutated, drift_type, event_id_out

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
You may split fields, merge fields, rename keys (e.g., address -> addr, open_price -> openPx),
or restructure nesting (wrap a field in an object or flatten an object).
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
                # classify drift type based on diff
                orig_keys = set(data.keys())
                mod_keys = set(modified.keys())
                if len(orig_keys & mod_keys) < min(len(orig_keys), len(mod_keys)):
                    return modified, "gemma_structural_renamed"
                for k in orig_keys & mod_keys:
                    if type(data[k]) != type(modified[k]):
                        return modified, "gemma_structural_nested"
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

    def _nested_corruption(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """Nest a flat field into an object, or flatten a nested object."""
        mutated = dict(data)
        keys = list(mutated.keys())
        if not keys:
            return mutated, None
        target_key = random.choice(keys)
        target_val = mutated[target_key]
        if isinstance(target_val, (str, int, float)) and not isinstance(target_val, bool):
            mutated[target_key] = {"raw": target_val}
            drift_type = "gemma_nested_corruption"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="gemma",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field=target_key,
                    mutated_field=f"{target_key}.raw",
                    metadata={"operation": "nest"}
                )
        elif isinstance(target_val, dict):
            for sub_key, sub_val in target_val.items():
                flat_key = f"{target_key}_{sub_key}"
                mutated[flat_key] = sub_val
            del mutated[target_key]
            drift_type = "gemma_nested_corruption"
            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="gemma",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field=f"{target_key}.*",
                    mutated_field=f"flattened_{target_key}",
                    metadata={"operation": "flatten"}
                )
        else:
            return mutated, None
        return mutated, drift_type

    def _apply_balanced_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                                     run_id=None, event_id=None):
        total_fields = len(data)
        if total_fields == 0:
            return data, None, event_id
        N = max(1, int(round(self.probability * total_fields)))
        N = min(N, total_fields)

        drift_types_pool = [
            "missing_keys",
            "extra_keys",
            "renamed_keys",
            "split_fields",
            "merged_fields",
            "nested_corruption",
            "type_mismatch",
            "value_contradiction"
        ]

        mutated = dict(data)
        used_keys = set()
        drift_type_log = None

        for _ in range(N):
            drift_type = random.choice(drift_types_pool)
            available = [k for k in mutated.keys() if k not in used_keys]
            if not available:
                break
            target_key = random.choice(available)
            used_keys.add(target_key)

            if drift_type == "missing_keys":
                del mutated[target_key]
                drift_type_log = "missing_keys"
            elif drift_type == "extra_keys":
                new_key = f"{target_key}_extra"
                mutated[new_key] = "dummy"
                drift_type_log = "extra_keys"
            elif drift_type == "renamed_keys":
                new_key = self._adversarial_rename_field(target_key)
                mutated[new_key] = mutated.pop(target_key)
                drift_type_log = "renamed_keys"
            elif drift_type == "split_fields":
                mutated, _ = self._split_field(mutated, drift_logger, run_number, api_source)
                drift_type_log = "split_fields"
            elif drift_type == "merged_fields":
                if len(mutated) >= 2:
                    mutated, _ = self._merge_fields(mutated, drift_logger, run_number, api_source)
                    drift_type_log = "merged_fields"
                else:
                    new_key = f"{target_key}_x"
                    mutated[new_key] = mutated.pop(target_key)
                    drift_type_log = "renamed_keys"
            elif drift_type == "nested_corruption":
                mutated, _ = self._nested_corruption(mutated, drift_logger, run_number, api_source)
                drift_type_log = "nested_corruption"
            elif drift_type == "type_mismatch":
                val = mutated[target_key]
                if isinstance(val, str):
                    mutated[target_key] = 0
                elif isinstance(val, (int, float)):
                    mutated[target_key] = ""
                else:
                    mutated[target_key] = "converted"
                drift_type_log = "type_mismatch"
            elif drift_type == "value_contradiction":
                val = mutated[target_key]
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    mutated[target_key] = val * random.uniform(0.9, 1.1)
                elif isinstance(val, str):
                    mutated[target_key] = val + "_mutated"
                drift_type_log = "value_contradiction"

            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="gemma",
                    chaos_level=self.probability,
                    drift_type=drift_type_log,
                    original_field=target_key,
                    mutated_field="(see metadata)",
                    metadata={"mutation_rate": self.probability},
                    run_id=run_id,
                    event_id=event_id
                )

        return mutated, drift_type_log, event_id

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                    run_id=None, event_id=None):
        if self.probability <= 0.0:
            return data, None, event_id
        return self._apply_balanced_chaos(data, drift_logger, run_number, api_source, run_id=run_id, event_id=event_id)
