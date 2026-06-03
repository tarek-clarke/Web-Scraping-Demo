import json
import random
from typing import Dict

class GemmaChaos:
    def __init__(self, model_path: str = "../../models/gemma4-e4b-it.gguf"):
        self.model_path = model_path
        self.model = None

    def load_model(self):
        try:
            from llama_cpp import Llama
            self.model = Llama(model_path=self.model_path, n_ctx=2048, verbose=False)
        except Exception as e:
            print(f"Gemma chaos model not available: {e}")

    def generate_drift(self, packet: Dict) -> Dict:
        if not self.model:
            return packet
        
        prompt = f"Modify this JSON with semantic drift: {json.dumps(packet)}"
        try:
            output = self.model(prompt, max_tokens=512, temperature=0.9)
            result = json.loads(output["choices"][0]["text"])
            return result
        except:
            return packet
