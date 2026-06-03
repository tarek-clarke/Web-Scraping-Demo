import json
import random
from typing import Dict

class JSONChaos:
    def inject(self, packet: Dict) -> Dict:
        methods = [
            self._add_noise,
            self._shuffle_keys,
            self._nested_wrap
        ]
        method = random.choice(methods)
        return method(packet)

    def _add_noise(self, packet: Dict) -> Dict:
        data = packet.get("data", {})
        for key in list(data.keys()):
            if isinstance(data[key], (int, float)):
                data[key] += random.uniform(-0.1, 0.1) * data[key]
        return packet

    def _shuffle_keys(self, packet: Dict) -> Dict:
        data = packet.get("data", {})
        keys = list(data.keys())
        random.shuffle(keys)
        packet["data"] = {k: data[k] for k in keys}
        return packet

    def _nested_wrap(self, packet: Dict) -> Dict:
        data = packet.get("data", {})
        packet["data"] = {"nested": data, "meta": {"version": 1}}
        return packet
