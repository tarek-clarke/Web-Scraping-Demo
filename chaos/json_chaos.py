import random
import re

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

    def __call__(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        mutated, drift_type = self.apply_chaos(data, drift_logger, run_number, api_source)
        return mutated, drift_type

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
        return f"{key}_drifted"

    def _split_field(self, data: dict):
        """Split a randomly chosen field into two new fields."""
        keys = list(data.keys())
        if not keys:
            return data, None
        target_key = random.choice(keys)
        target_val = data[target_key]
        if not isinstance(target_val, str) or " " not in target_val:
            # fallback: split a numeric field into integer and fractional parts
            if isinstance(target_val, (int, float)) and not isinstance(target_val, bool):
                val_float = float(target_val)
                int_part = int(val_float)
                frac_part = int((val_float - int_part) * 1000000)
                new_data = dict(data)
                new_data[f"{target_key}_integer"] = int_part
                new_data[f"{target_key}_fraction"] = frac_part
                del new_data[target_key]
                return new_data, "split"
            # otherwise try to split a string on any punctuation
            elif isinstance(target_val, str) and len(target_val) > 1:
                mid = len(target_val) // 2
                new_data = dict(data)
                new_data[f"{target_key}_part1"] = target_val[:mid]
                new_data[f"{target_key}_part2"] = target_val[mid:]
                del new_data[target_key]
                return new_data, "split"
            else:
                # cannot split, duplicate as dummy
                new_data = dict(data)
                new_data[f"{target_key}_copy"] = target_val
                new_data[target_key] = target_val
                return new_data, "split_duplicate"
        # string with space -> split by space
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

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api"):
        """
        Applies JSON level chaos injection based on target probability.
        Logs every event via drift_logger.
        Returns (mutated_data, drift_type).
        """
        mutated_data = {}
        drift_type = None

        for key, val in data.items():
            new_key = key
            if random.random() < self.probability:
                drift_choice = random.choice(["case_drift", "synonym_rename", "typo_rename"])
                drift_type = drift_choice
                if drift_choice == "case_drift":
                    new_key = self._apply_case_drift(key)
                elif drift_choice == "synonym_rename":
                    new_key = self._rename_field(key)
                else:
                    new_key = self._introduce_typo(key)

                if drift_logger and new_key != key:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="json",
                        chaos_level=self.probability,
                        drift_type=drift_choice,
                        original_field=key,
                        mutated_field=new_key,
                        metadata={"mutation_rate": self.probability}
                    )

            new_val = val
            if random.random() < self.probability:
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    new_val = self._perturb_numeric(val)
                    if drift_logger:
                        drift_logger.log_event(
                            api_source=api_source,
                            run_number=run_number,
                            chaos_strategy="json",
                            chaos_level=self.probability,
                            drift_type="numeric_perturbation",
                            original_field=f"{key}_value",
                            mutated_field=f"{key}_value",
                            metadata={"original_value": val, "mutated_value": new_val}
                        )
                elif isinstance(val, str):
                    new_val = self._introduce_typo(val)
                    if drift_logger:
                        drift_logger.log_event(
                            api_source=api_source,
                            run_number=run_number,
                            chaos_strategy="json",
                            chaos_level=self.probability,
                            drift_type="value_typo",
                            original_field=f"{key}_value",
                            mutated_field=f"{key}_value",
                            metadata={"original_value": val, "mutated_value": new_val}
                        )

            mutated_data[new_key] = new_val

        # Ensure at least one mutation occurred. If not, apply split or merge.
        if mutated_data == data:
            if random.choice(["split", "merge"]) == "split":
                mutated_data, drift_type = self._split_field(data)
            else:
                mutated_data, drift_type = self._merge_fields(data)
            if drift_logger and drift_type:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="json",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field="forced",
                    mutated_field="forced",
                    metadata={"mutation_rate": self.probability}
                )

        # Apply split/merge with probability to increase structural drift
        if random.random() < self.probability:
            if random.choice(["split", "merge"]) == "split":
                mutated_data, st = self._split_field(mutated_data)
                if st:
                    drift_type = st
            else:
                mutated_data, st = self._merge_fields(mutated_data)
                if st:
                    drift_type = st
            if drift_logger and drift_type:
                drift_logger.log_event(
                    api_source=api_source,
                    run_number=run_number,
                    chaos_strategy="json",
                    chaos_level=self.probability,
                    drift_type=drift_type,
                    original_field="additional",
                    mutated_field="additional",
                    metadata={"mutation_rate": self.probability}
                )

        return mutated_data, drift_type
