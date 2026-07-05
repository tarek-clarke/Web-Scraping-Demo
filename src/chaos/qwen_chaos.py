import random
from typing import Dict, Tuple

class QwenChaos:
    """
    Simulates schema drifts typical of Qwen LLM reformatting.
    Combines semantic translation, nested structure changes, casing shifts,
    and type conversions to represent agent-driven schema modifications.
    """

    def __init__(self):
        # Qwen-style key translations
        self.synonyms = {
            "driver_number": "driver_id",
            "speed": "velocity_kmh",
            "rpm": "engine_rotations",
            "gear": "selected_gear",
            "throttle": "gas_pedal_pct",
            "brake": "brake_pressure_pct",
            "drs": "drs_status",
            "date": "timestamp_utc",
            "session_key": "meeting_session_id",
            "meeting_key": "event_id",
        }

    def inject(self, data: Dict) -> Dict:
        _, result = self.inject_with_subtype(data)
        return result

    def inject_with_subtype(self, data: Dict) -> Tuple[str, Dict]:
        sub_types = ["semantic_shift", "nesting_alteration", "type_mutation", "casing_scramble", "field_split", "field_join"]
        sub_type = random.choice(sub_types)
        
        method_map = {
            "semantic_shift": self._semantic_shift,
            "nesting_alteration": self._nesting_alteration,
            "type_mutation": self._type_mutation,
            "casing_scramble": self._casing_scramble,
            "field_split": self._field_split,
            "field_join": self._field_join,
        }
        
        method = method_map.get(sub_type, self._semantic_shift)
        return f"qwen_{sub_type}", method(data)

    def _semantic_shift(self, data: Dict) -> Dict:
        """Translates keys to realistic synonyms used by Qwen."""
        new_data = {}
        for k, v in data.items():
            if k in self.synonyms:
                new_data[self.synonyms[k]] = v
            else:
                new_data[k] = v
        return new_data

    def _nesting_alteration(self, data: Dict) -> Dict:
        """Deepens or flattens schema fields typical of LLM refactorings."""
        if not data:
            return data
        
        keys = list(data.keys())
        # Pick 2 random keys and wrap them in a nested object
        if len(keys) >= 3:
            nested_keys = random.sample(keys, 2)
            nested_obj = {}
            new_data = {}
            for k, v in data.items():
                if k in nested_keys:
                    nested_obj[k] = v
                else:
                    new_data[k] = v
            new_data["telemetry_metrics"] = nested_obj
            return new_data
        return data

    def _type_mutation(self, data: Dict) -> Dict:
        """Simulates type safety drifts (converting floats to strings or numbers to lists)."""
        new_data = {}
        for k, v in data.items():
            if isinstance(v, (int, float)) and random.random() < 0.5:
                # Stringify numerical values
                new_data[k] = str(v)
            elif isinstance(v, str) and v.replace(".", "", 1).isdigit() and random.random() < 0.5:
                # Parse strings to float
                new_data[k] = float(v)
            else:
                new_data[k] = v
        return new_data

    def _casing_scramble(self, data: Dict) -> Dict:
        """Alters casing standard from snake_case to camelCase or UPPERCASE."""
        new_data = {}
        for k, v in data.items():
            # Convert snake_case to camelCase
            words = k.split("_")
            camel_key = words[0] + "".join(w.capitalize() for w in words[1:])
            # Randomly upper case the key
            if random.random() < 0.3:
                new_data[k.upper()] = v
            else:
                new_data[camel_key] = v
        return new_data

    def _field_split(self, data: Dict) -> Dict:
        """Splits a single telemetry field into composite partition parts."""
        if not data: return data
        new_data = data.copy()
        key = random.choice(list(new_data.keys()))
        val = new_data.pop(key)
        new_data[f"{key}_part1"] = val
        new_data[f"{key}_part2"] = val
        return new_data

    def _field_join(self, data: Dict) -> Dict:
        """Joins two related telemetry fields into a unified composite key."""
        new_data = data.copy()
        keys = list(new_data.keys())
        if len(keys) < 2: return new_data
        k1, k2 = random.sample(keys, 2)
        joined = f"{k1}_{k2}"
        new_data[joined] = new_data.pop(k1)
        new_data.pop(k2, None)
        return new_data
