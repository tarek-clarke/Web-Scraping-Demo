import random
import re
from uuid import uuid4

class JSONChaos:
    def __init__(self, probability: float):
        self.probability = probability
        self.synonyms = {
            "price": ["cost", "charge", "amount", "monetary_value", "rate"],
            "temperature": ["temp", "thermal_level", "degrees", "heat_index"],
            "speed": ["velocity", "pace", "rate_of_speed", "tempo"],
            "active": ["enabled", "running", "live", "operational"],
            "name": ["label", "identifier", "title", "designation"],
            "value": ["measure", "reading", "result", "magnitude"],
            "timestamp": ["time", "date_time", "epoch", "recorded_at"],
            "wind_speed": ["wind_velocity", "wind_pace", "breeze_speed"],
            "capsule_serial": ["capsule_id", "serial_number", "hardware_tag"],
            "driver_name": ["driver_label", "driver_title", "pilot_name"]
        }

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                 run_id=None, event_id=None):
        mutated, drift_type, event_id_out = self.apply_chaos(data, drift_logger, run_number, api_source,
                                                              run_id=run_id, event_id=event_id)
        return mutated, drift_type, event_id_out

    def _introduce_typo(self, text: str) -> str:
        if not isinstance(text, str) or len(text) < 3:
            return text
        chars = list(text)
        mutation_type = random.choice(["delete", "insert", "swap"])
        idx = random.randint(0, len(chars) - 1)

        if mutation_type == "delete" and len(chars) > 2:
            chars.pop(idx)
        elif mutation_type == "insert":
            random_char = random.choice("abcdefghijklmnopqrstuvwxyz")
            chars.insert(idx, random_char)
        elif mutation_type == "swap" and idx < len(chars) - 1:
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]

        return "".join(chars)

    def _to_camel_case(self, snake_str: str) -> str:
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def _to_pascal_case(self, snake_str: str) -> str:
        return "".join(x.title() for x in snake_str.split("_"))

    def _to_kebab_case(self, snake_str: str) -> str:
        return snake_str.replace("_", "-")

    def _apply_case_drift(self, key: str) -> str:
        if "_" not in key:
            return key
        case_style = random.choice(["camel", "pascal", "kebab"])
        if case_style == "camel":
            return self._to_camel_case(key)
        elif case_style == "pascal":
            return self._to_pascal_case(key)
        else:
            return self._to_kebab_case(key)

    def _perturb_numeric(self, val):
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            noise_percent = random.uniform(-0.1, 0.1)
            if isinstance(val, int):
                perturbation = int(val * noise_percent)
                if perturbation == 0:
                    perturbation = random.choice([-1, 1])
                return val + perturbation
            else:
                return val * (1.0 + noise_percent)
        return val

    def _rename_field(self, key: str) -> str:
        for canon, syns in self.synonyms.items():
            if canon in key or key in canon:
                return random.choice(syns)
        return f"{key}_x"

    def _split_field(self, data: dict):
        """Split a randomly chosen field into two new fields."""
        keys = list(data.keys())
        if not keys:
            return data, None
        target_key = random.choice(keys)
        target_val = data[target_key]
        if not isinstance(target_val, str) or " " not in target_val:
            if isinstance(target_val, (int, float)) and not isinstance(target_val, bool):
                val_float = float(target_val)
                int_part = int(val_float)
                frac_part = int((val_float - int_part) * 1000000)
                new_data = dict(data)
                new_data[f"{target_key}_integer"] = int_part
                new_data[f"{target_key}_fraction"] = frac_part
                del new_data[target_key]
                return new_data, "split"
            elif isinstance(target_val, str) and len(target_val) > 1:
                mid = len(target_val) // 2
                new_data = dict(data)
                new_data[f"{target_key}_part1"] = target_val[:mid]
                new_data[f"{target_key}_part2"] = target_val[mid:]
                del new_data[target_key]
                return new_data, "split"
            else:
                new_data = dict(data)
                new_data[f"{target_key}_copy"] = target_val
                new_data[target_key] = target_val
                return new_data, "split_duplicate"
        parts = target_val.split(" ", 1)
        new_data = dict(data)
        new_data[f"{target_key}_first"] = parts[0]
        new_data[f"{target_key}_second"] = parts[1]
        del new_data[target_key]
        return new_data, "split"

    def _merge_fields(self, data: dict):
        """Merge two consecutive fields into one."""
        keys = list(data.keys())
        if len(keys) < 2:
            return data, None
        idx = random.randint(0, len(keys) - 2)
        key1, key2 = keys[idx], keys[idx+1]
        val1, val2 = data[key1], data[key2]
        if isinstance(val1, str) and isinstance(val2, str):
            merged_val = val1 + " " + val2
            merged_key = f"{key1}_{key2}"
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            merged_val = val1 + val2
            merged_key = f"{key1}_{key2}"
        elif isinstance(val1, bool) and isinstance(val2, bool):
            merged_val = val1 or val2
            merged_key = f"{key1}_{key2}"
        else:
            merged_val = f"{val1},{val2}"
            merged_key = f"{key1}_{key2}"
        new_data = dict(data)
        new_data[merged_key] = merged_val
        del new_data[key1]
        del new_data[key2]
        return new_data, "merge"

    def _nested_corruption(self, data: dict):
        """Nest a flat field into an object, or flatten a nested object."""
        mutated = dict(data)
        keys = list(mutated.keys())
        if not keys:
            return mutated, None
        target_key = random.choice(keys)
        target_val = mutated[target_key]
        if isinstance(target_val, (str, int, float)) and not isinstance(target_val, bool):
            mutated[target_key] = {"raw": target_val}
            return mutated, "nested_corruption"
        elif isinstance(target_val, dict):
            for sub_key, sub_val in target_val.items():
                flat_key = f"{target_key}_{sub_key}"
                mutated[flat_key] = sub_val
            del mutated[target_key]
            return mutated, "nested_corruption"
        return mutated, None

    def _apply_balanced_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api",
                              run_id=None, event_id=None):
        """Apply exactly N mutations with balanced drift types."""
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
                new_key = self._rename_field(target_key)
                mutated[new_key] = mutated.pop(target_key)
                drift_type_log = "renamed_keys"
            elif drift_type == "split_fields":
                mutated, _ = self._split_field(mutated)
                drift_type_log = "split_fields"
            elif drift_type == "merged_fields":
                if len(mutated) >= 2:
                    mutated, _ = self._merge_fields(mutated)
                    drift_type_log = "merged_fields"
                else:
                    new_key = self._rename_field(target_key)
                    mutated[new_key] = mutated.pop(target_key)
                    drift_type_log = "renamed_keys"
            elif drift_type == "nested_corruption":
                mutated, _ = self._nested_corruption(mutated)
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
                    mutated[target_key] = self._perturb_numeric(val)
                elif isinstance(val, str):
                    mutated[target_key] = self._introduce_typo(val)
                drift_type_log = "value_contradiction"

            if drift_logger:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="json",
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
