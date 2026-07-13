import random
from typing import Dict, Tuple

class JSONChaos:
    """
    JSON structural manipulation.
    Sub-types: field_split, field_join, variable_drop, field_merge_value,
    array_to_scalar, scalar_to_array, array_expansion, duplicate_field_inject,
    null_injection, default_value_inject, outlier_injection.
    """

    def inject(self, data: Dict) -> Dict:
        _, result = self.inject_with_subtype(data)
        return result

    def inject_with_subtype(self, data: Dict) -> Tuple[str, Dict]:
        if not isinstance(data, dict):
            return "none", data
        sub_types = [
            "field_split", "field_join", "variable_drop", "field_merge_value",
            "array_to_scalar", "scalar_to_array", "array_expansion",
            "duplicate_field_inject", "null_injection", "default_value_inject",
            "outlier_injection"
        ]
        sub_type = random.choice(sub_types)

        method_map = {
            "field_split": self._field_split,
            "field_join": self._field_join,
            "variable_drop": self._variable_drop,
            "field_merge_value": self._field_merge_value,
            "array_to_scalar": self._array_to_scalar,
            "scalar_to_array": self._scalar_to_array,
            "array_expansion": self._array_expansion,
            "duplicate_field_inject": self._duplicate_field_inject,
            "null_injection": self._null_injection,
            "default_value_inject": self._default_value_inject,
            "outlier_injection": self._outlier_injection,
        }
        method = method_map.get(sub_type, self._variable_drop)
        return sub_type, method(data)


    def _field_split(self, data: Dict) -> Dict:
        if not data: return data
        key = random.choice(list(data.keys()))
        val = data.pop(key)
        data[f"{key}_part1"] = val
        data[f"{key}_part2"] = val
        return data

    def _field_join(self, data: Dict) -> Dict:
        keys = list(data.keys())
        if len(keys) < 2: return data
        k1, k2 = random.sample(keys, 2)
        joined = f"{k1}_{k2}"
        data[joined] = data.pop(k1)
        data.pop(k2, None)
        return data

    def _variable_drop(self, data: Dict) -> Dict:
        if not data: return data
        data.pop(random.choice(list(data.keys())), None)
        return data

    def _field_merge_value(self, data: Dict) -> Dict:
        keys = list(data.keys())
        if len(keys) < 2: return data
        k1, k2 = random.sample(keys, 2)
        data[f"{k1}_{k2}"] = f"{data.pop(k1)}_{data.pop(k2)}"
        return data

    def _array_to_scalar(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], list) and len(data[key]) == 1:
                data[key] = data[key][0]
        return data

    def _scalar_to_array(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if not isinstance(data[key], list):
                data[key] = [data[key]]
        return data

    def _array_expansion(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], list) and len(data[key]) == 1:
                data[key] = data[key] * 3
        return data

    def _duplicate_field_inject(self, data: Dict) -> Dict:
        if not data: return data
        key = random.choice(list(data.keys()))
        data[f"{key}_copy"] = data[key]
        return data

    def _null_injection(self, data: Dict) -> Dict:
        if not data: return data
        key = random.choice(list(data.keys()))
        data[key] = None
        return data

    def _default_value_inject(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if data[key] is None:
                data[key] = 0
        return data

    def _outlier_injection(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], (int, float)):
                data[key] = data[key] * 10
        return data