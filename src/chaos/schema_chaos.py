import random
from typing import Dict, Tuple

class SchemaChaos:
    """
    Schema structural alteration.
    Sub-types: translation, type_change, precision_loss, unit_conversion,
    nesting_flatten, nesting_deepen, timestamp_format_change, timezone_change,
    date_format_change, encoding_change, key_case_change, array_index_rename.
    """

    def alter(self, data: Dict) -> Dict:
        _, result = self.alter_with_subtype(data)
        return result

    def alter_with_subtype(self, data: Dict) -> Tuple[str, Dict]:
        sub_types = [
            "translation", "type_change", "precision_loss", "unit_conversion",
            "nesting_flatten", "nesting_deepen", "timestamp_format_change",
            "timezone_change", "date_format_change", "encoding_change",
            "key_case_change", "array_index_rename"
        ]
        sub_type = random.choice(sub_types)
        method_map = {
            "translation": self._translation,
            "type_change": self._type_change,
            "precision_loss": self._precision_loss,
            "unit_conversion": self._unit_conversion,
            "nesting_flatten": self._nesting_flatten,
            "nesting_deepen": self._nesting_deepen,
            "timestamp_format_change": self._timestamp_format_change,
            "timezone_change": self._timezone_change,
            "date_format_change": self._date_format_change,
            "encoding_change": self._encoding_change,
            "key_case_change": self._key_case_change,
            "array_index_rename": self._array_index_rename,
        }
        method = method_map.get(sub_type, self._translation)
        return sub_type, method(data)

    def _translation(self, data: Dict) -> Dict:
        t = {"temperature": "temp_c", "speed": "velocity", "price": "cost", "timestamp": "ts"}
        for old, new in t.items():
            if old in data: data[new] = data.pop(old)
        return data

    def _type_change(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], str):
                try:
                    data[key] = float(data[key])
                except (ValueError, TypeError):
                    pass
            elif isinstance(data[key], (int, float)):
                data[key] = str(data[key])
        return data

    def _precision_loss(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], float):
                data[key] = round(data[key], 2)
        return data

    def _unit_conversion(self, data: Dict) -> Dict:
        if "speed" in data and isinstance(data["speed"], (int, float)):
            data["speed"] = data["speed"] * 1.60934
        return data

    def _nesting_flatten(self, data: Dict) -> Dict:
        if "nested" in data and isinstance(data["nested"], dict):
            for k, v in data["nested"].items():
                if k not in data:
                    data[k] = v
            del data["nested"]
        return data

    def _nesting_deepen(self, data: Dict) -> Dict:
        keys = list(data.keys())[:2]
        nested = {}
        for key in keys:
            nested[key] = data.pop(key)
        data["nested"] = nested
        return data

    def _timestamp_format_change(self, data: Dict) -> Dict:
        if "timestamp" in data:
            data["timestamp"] = str(data["timestamp"])
        return data

    def _timezone_change(self, data: Dict) -> Dict:
        if "tz" in data:
            data["tz"] = "UTC"
        return data

    def _date_format_change(self, data: Dict) -> Dict:
        if "date" in data:
            data["date"] = str(data["date"])
        return data

    def _encoding_change(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], str):
                try:
                    data[key] = data[key].encode("utf-8", errors="ignore").decode("utf-8")
                except Exception:
                    pass
        return data

    def _key_case_change(self, data: Dict) -> Dict:
        new_data = {}
        for key in data.keys():
            new_key = key.upper() if key.islower() else key.lower()
            new_data[new_key] = data[key]
        return new_data

    def _array_index_rename(self, data: Dict) -> Dict:
        if "items" in data and isinstance(data["items"], list):
            data["items"] = {f"item_{i}": v for i, v in enumerate(data["items"])}
        return data