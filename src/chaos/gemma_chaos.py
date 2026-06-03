import json
import os
from typing import Dict, Optional
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

class GemmaChaos:
    """
    LLM-generated semantic schema drift.
    Prompt: temperature=0.9 for creative field renames
    """

    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            model_path = str(ROOT / "models" / "gemma4-31b-gguf.gguf")
        self.model_path = model_path
        self.model = None

    def load_model(self):
        if not os.path.exists(self.model_path):
            print(f"Gemma chaos model not found at {self.model_path}")
            return
        try:
            from llama_cpp import Llama
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False
            )
            print("Gemma4-31B chaos generator loaded")
        except Exception as e:
            print(f"Gemma chaos model not available: {e}")

    def generate_drift(self, packet: Dict) -> Optional[Dict]:
        if not self.model:
            self.load_model()
        if not self.model:
            return None

        prompt = self._build_prompt(packet)
        try:
            output = self.model(
                prompt,
                max_tokens=512,
                temperature=0.9,
                top_p=0.95,
                stop=["```"],
            )
            text = output["choices"][0]["text"].strip()
            text = text.strip()

            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            text = text.strip()

            result = json.loads(text)
            if not isinstance(result, dict):
                return None

            result["_drift_note"] = text[:200]
            return result

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Gemma chaos parse error: {e}")
            return None

    def _build_prompt(self, packet: Dict) -> str:
        data = packet.get("data", {})
        source = packet.get("source", "unknown")

        key_list = json.dumps(list(data.keys()), indent=2)

        prompt = f"""You are a chaos engineering agent. Introduce realistic semantic drift into the following telemetry JSON from a "{source}" data source.

Rules:
- Rename 1-2 fields to realistic alternative names that a human operator might use
- Keep all values unchanged
- Maintain valid JSON format
- Be creative but realistic — use real-world field naming conventions
- Example: "temperature" -> "temp_c", "vehicle_speed" -> "speed_mps", "price_usd" -> "cost"

Original fields: {key_list}

Return ONLY the modified JSON object. Do not wrap in markdown.

```json
"""
        return prompt
