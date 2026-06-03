import json
import os
from typing import Dict, Optional
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

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

        prompt = self._build_prompt(packet)
        try:
            output = self.model(
                prompt,
                max_tokens=512,
                temperature=0.9,
                top_p=0.95,
                stop=["<|im_end|>", "```"],
            )
            text = output["choices"][0]["text"].strip()

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            if not isinstance(result, dict):
                return None

            return result

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Qwen chaos parse error: {e}")
            return None

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
