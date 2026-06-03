import random
from typing import Dict

class SchemaChaos:
    def alter(self, packet: Dict) -> Dict:
        methods = [
            self._type_coerce,
            self._rename_fields,
            self._flatten_nested
        ]
        method = random.choice(methods)
        return method(packet)

    def _type_coerce(self, packet: Dict) -> Dict:
        data = packet.get("data", {})
        for key in list(data.keys()):
            if isinstance(data[key], str):
                try:
                    data[key] = float(data[key])
                except:
                    pass
        return packet

    def _rename_fields(self, packet: Dict) -> Dict:
        data = packet.get("data", {})
        for key in list(data.keys())[:2]:
            data[f"{key}_v2"] = data.pop(key)
        return packet

    def _flatten_nested(self, packet: Dict) -> Dict:
        data = packet.get("data", {})
        if "nested" in data and isinstance(data["nested"], dict):
            for k, v in data["nested"].items():
                data[k] = v
            del data["nested"]
        return packet
