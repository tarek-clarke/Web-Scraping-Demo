import random
from typing import Dict

class JSONChaos:
    """
    JSON structural manipulation.
    Drift types: noise injection, key shuffling, nested wrapping.
    """

    def inject(self, data: Dict) -> Dict:
        methods = [
            self._add_noise,
            self._shuffle_keys,
            self._nested_wrap
        ]
        method = random.choice(methods)
        return method(data)

    def _add_noise(self, data: Dict) -> Dict:
        for key in list(data.keys()):
            if isinstance(data[key], (int, float)):
                data[key] += random.uniform(-0.1, 0.1) * data[key]
        return data

    def _shuffle_keys(self, data: Dict) -> Dict:
        keys = list(data.keys())
        random.shuffle(keys)
        return {k: data[k] for k in keys}

    def _nested_wrap(self, data: Dict) -> Dict:
        return {"nested": data, "meta": {"version": 1}}
