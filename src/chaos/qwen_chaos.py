import json
import random
from typing import Dict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

MAPPINGS = {
    "temperature": "temp_c", "speed": "velocity_mps", "price": "cost",
    "timestamp": "ts", "latitude": "lat", "longitude": "lon",
    "altitude": "alt_m", "pressure": "pressure_hpa", "humidity": "humidity_pct",
    "driver": "driver_name", "team": "team_name", "position": "pos",
    "throttle": "throttle_pct", "brake": "brake_pct", "gear": "n_gear",
}

class QwenChaos:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or str(ROOT / "models" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf")

    def generate_drift(self, packet: Dict) -> Optional[Dict]:
        return self._fallback_drift(packet)

    def _fallback_drift(self, packet: Dict) -> Optional[Dict]:
        data = packet.get("data", {})
        if not data:
            return None

        drifted = json.loads(json.dumps(data))
        renamed = 0

        for old_key in list(drifted.keys()):
            if old_key in MAPPINGS and random.random() < 0.3:
                new_key = MAPPINGS[old_key]
                drifted[new_key] = drifted.pop(old_key)
                renamed += 1
                if renamed >= 1:
                    break

        if renamed == 0:
            keys = list(drifted.keys())
            if len(keys) >= 2:
                k1, k2 = random.sample(keys, 2)
                drifted[f"{k1}_alt"] = drifted.pop(k1)
                drifted[f"{k2}_backup"] = drifted[k2]
                renamed = 2

        return {"data": drifted, "sub_type": "qwen_semantic"}


