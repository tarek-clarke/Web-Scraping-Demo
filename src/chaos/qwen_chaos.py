import json
import os
import random
from typing import Dict, Optional
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
        if model_path is None:
            model_path = str(ROOT / "models" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf")
        self.model_path = model_path
        self.model = None

    def load_model(self):
        if not os.path.exists(self.model_path):
            print(f"Qwen model not found at {self.model_path}")
            return
        try:
            from llama_cpp import Llama
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False
            )
            print("Qwen2.5-7B chaos generator loaded")
        except Exception as e:
            print(f"Qwen model not available: {e}")

    def generate_drift(self, packet: Dict) -> Optional[Dict]:
        if not self.model:
            self.load_model()
        if not self.model:
            return None

        data = packet.get("data", {})
        if not data or len(data) == 0:
            return None

        keys = list(data.keys())
        vals = {k: data[k] for k in keys[:3]}
        data_str = json.dumps(vals, ensure_ascii=False)

        field_name = keys[0]
        new_name = field_name.replace("_", "").lower() + "_new"

        prompt = f'''<|im_start|>system
Transform telemetry JSON by renaming one field.
Output ONLY the transformed JSON, no explanation.
<|im_end|>
<|im_start|>user
Input: {data_str}
Rename "{field_name}" to something similar like "name"->"full_name" or "id"->"identifier".
Output ONLY the transformed JSON:<|im_end|>
<|im_start|>assistant
'''

        for attempt in range(3):
            try:
                output = self.model(
                    prompt,
                    max_tokens=512,
                    temperature=0.1,
                    top_p=0.8,
                    stop=["<|im_end|>", "```"],
                    echo=False
                )
                text = output["choices"][0]["text"].strip()

                text = text.replace("```json", "").replace("```", "").strip()

                result = json.loads(text)
                if isinstance(result, dict) and len(result) > 0:
                    return {"data": result, "sub_type": "qwen_semantic"}

            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        return None

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

        return {"data": drifted, "sub_type": "qwen_fallback"}

    def _build_prompt(self, packet: Dict) -> str:
        data = packet.get("data", {})
        source = packet.get("source", "unknown")
        keys = json.dumps(list(data.keys()))

        return f"""<|im_start|>system
You are a chaos engineering agent. Introduce realistic semantic drift into telemetry JSON.
Rules:
- Rename 1-2 fields to realistic alternative names
- Keep all values unchanged
- Valid JSON only
- Be creative: "temperature" -> "temp_c", "speed" -> "velocity_mps"<|im_end|>
<|im_start|>user
Source: {source}
Fields: {keys}
Return ONLY the modified JSON object.<|im_end|>
<|im_start|>assistant
```json
"""
