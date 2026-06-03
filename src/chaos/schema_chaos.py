import random
from typing import Dict

class SchemaChaos:
    """
    Schema structural alteration.
    Drift types: type coercion, field renaming, nested flattening.
    """

    def alter(self, data: Dict) -> Dict:
        methods = [
            self._type_coerce,
            self._rename_fields,
            self._flatten_nested
        ]
        method = random.choice(methods)
        return method(data)

    def _type_coerce(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], str):
                try:
                    data[key] = float(data[key])
                except (ValueError, TypeError):
                    pass
            elif isinstance(data[key], (int, float)):
                data[key] = str(data[key])
        return data

    def _rename_fields(self, data: Dict) -> Dict:
        keys = list(data.keys())
        for key in keys[:2]:
            data[f"{key}_v2"] = data.pop(key)
        return data

    def _flatten_nested(self, data: Dict) -> Dict:
        if "nested" in data and isinstance(data["nested"], dict):
            for k, v in data["nested"].items():
                if k not in data:
                    data[k] = v
            del data["nested"]
        return data
