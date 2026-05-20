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
            noise_percent = random.uniform(-0.1, 0.1) # Up to +/- 10%
            if isinstance(val, int):
                # Ensure it perturbations by at least 1 for non-zero ints
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
        # Fallback to random renamed key
        return f"{key}_drifted"

    def apply_chaos(self, data: dict, drift_logger=None, run_number=1, api_source="api") -> dict:
        """
        Applies JSON level chaos injection based on target probability.
        Logs every event via drift_logger.
        """
        mutated_data = {}
        for key, val in data.items():
            # Roll dice for key mutations
            new_key = key
            drift_occurred = False
            drift_type = None
            
            if random.random() < self.probability:
                drift_occurred = True
                drift_type = random.choice(["case_drift", "synonym_rename", "typo_rename"])
                
                if drift_type == "case_drift":
                    new_key = self._apply_case_drift(key)
                elif drift_type == "synonym_rename":
                    new_key = self._rename_field(key)
                else:
                    new_key = self._introduce_typo(key)
                    
                if drift_logger and new_key != key:
                    drift_logger.log_event(
                        api_source=api_source,
                        run_number=run_number,
                        chaos_strategy="json",
                        chaos_level=self.probability,
                        drift_type=drift_type,
                        original_field=key,
                        mutated_field=new_key,
                        metadata={"mutation_rate": self.probability}
                    )

            # Roll dice for value mutations
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
            
        return mutated_data
