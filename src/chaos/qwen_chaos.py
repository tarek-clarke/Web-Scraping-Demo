import random
from typing import Dict, Tuple
from .json_chaos import JSONChaos
from .schema_chaos import SchemaChaos

class QwenChaos:
    """
    Combined super-chaos injector that implements all 27 possible drift subtypes 
    spanning Qwen semantic/structural changes, traditional JSON manipulations, 
    and schema alterations. Makes drift generation as messy as possible.
    """

    def __init__(self):
        self.json_chaos = JSONChaos()
        self.schema_chaos = SchemaChaos()
        
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
        # Complete pool of all 27 subtypes across Qwen, JSON, and Schema chaos
        sub_types = [
            # Qwen custom
            "qwen_semantic_shift", "qwen_nesting_alteration", "qwen_type_mutation", "qwen_casing_scramble",
            # JSONChaos
            "field_split", "field_join", "variable_drop", "field_merge_value",
            "array_to_scalar", "scalar_to_array", "array_expansion",
            "duplicate_field_inject", "null_injection", "default_value_inject",
            "outlier_injection",
            # SchemaChaos
            "translation", "type_change", "precision_loss", "unit_conversion",
            "nesting_flatten", "nesting_deepen", "timestamp_format_change",
            "timezone_change", "date_format_change", "encoding_change",
            "key_case_change", "array_index_rename"
        ]
        
        import copy
        data = copy.deepcopy(data)
        if isinstance(data, list):
            data = {str(i): v for i, v in enumerate(data)}
        elif not isinstance(data, dict):
            data = {}
            
        sub_type = random.choice(sub_types)
        
        # Dispatch to the appropriate helper
        if sub_type.startswith("qwen_"):
            method_name = f"_{sub_type[5:]}"
            method = getattr(self, method_name, self._semantic_shift)
            return sub_type, method(data)
        elif sub_type in self.json_chaos.inject_with_subtype.__code__.co_consts or hasattr(self.json_chaos, f"_{sub_type}"):
            method = getattr(self.json_chaos, f"_{sub_type}", self.json_chaos._variable_drop)
            return f"json_{sub_type}", method(data)
        else:
            method = getattr(self.schema_chaos, f"_{sub_type}", self.schema_chaos._translation)
            return f"schema_{sub_type}", method(data)

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
                new_data[k] = str(v)
            elif isinstance(v, str) and v.replace(".", "", 1).isdigit() and random.random() < 0.5:
                new_data[k] = float(v)
            else:
                new_data[k] = v
        return new_data

    def _casing_scramble(self, data: Dict) -> Dict:
        """Alters casing standard from snake_case to camelCase or UPPERCASE."""
        new_data = {}
        for k, v in data.items():
            words = k.split("_")
            camel_key = words[0] + "".join(w.capitalize() for w in words[1:])
            if random.random() < 0.3:
                new_data[k.upper()] = v
            else:
                new_data[camel_key] = v
        return new_data
