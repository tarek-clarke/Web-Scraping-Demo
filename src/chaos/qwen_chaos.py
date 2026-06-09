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
        self.model_path = model_path
        self.model_manager = None
        self.use_llm = False
        
        # Try to load Qwen model via ModelManager
        try:
            from src.inference import ModelManager
            
            # Get model ID from environment or use default
            model_id = os.environ.get("CHAOS_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
            
            # Initialize ModelManager (singleton, auto-detects platform)
            self.model_manager = ModelManager()
            
            # Check if we should use LLM or fallback
            use_llm_env = os.environ.get("USE_LLM_CHAOS", "true").lower()
            self.use_llm = use_llm_env in ("true", "1", "yes")
            
            if self.use_llm:
                print(f"[QwenChaos] Using LLM chaos injection with {model_id}")
            else:
                print(f"[QwenChaos] Using deterministic fallback chaos injection")
                
        except Exception as e:
            print(f"[QwenChaos] Failed to initialize ModelManager: {e}")
            print(f"[QwenChaos] Falling back to deterministic chaos injection")
            self.use_llm = False

    def generate_drift(self, packet: Dict) -> Optional[Dict]:
        if self.use_llm and self.model_manager:
            return self._llm_drift(packet)
        return self._fallback_drift(packet)
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response with multiple strategies."""
        import re
        text = response.strip()

        # Strategy 1: Direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        block = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if block:
            try:
                return json.loads(block.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON object with braces anywhere
        brace = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group())
            except json.JSONDecodeError:
                pass

        # Strategy 4: Extract key-value pairs line by line
        result = {}
        lines = text.split('\n')
        for line in lines:
            line = line.strip().rstrip(',').strip('"')
            if ':' in line and '"' not in line.split(':')[0]:
                continue
            try:
                pair = re.match(r'\s*"([^"]+)"\s*:\s*"([^"]*)"', line)
                if pair:
                    result[pair.group(1)] = pair.group(2)
                    continue
                pair = re.match(r'\s*"([^"]+)"\s*:\s*([0-9\.]+)', line)
                if pair:
                    result[pair.group(1)] = float(pair.group(2)) if '.' in pair.group(2) else int(pair.group(2))
            except:
                pass

        if result:
            return result

        return None

    def _llm_drift(self, packet: Dict) -> Optional[Dict]:
        """Use Qwen LLM to generate semantic drift."""
        try:
            data = packet.get("data", {})
            if not data:
                return None

            prompt = f"""Transform this JSON: {json.dumps(data)}
Rename 1-2 fields. Output ONLY the new JSON:"""

            response = self.model_manager.generate_response(
                prompt,
                max_new_tokens=256,
                temperature=0.1,
                top_p=0.9,
                do_sample=True
            )

            drifted_data = self._parse_json_response(response)
            if drifted_data and isinstance(drifted_data, dict):
                return {"data": drifted_data, "sub_type": "qwen_semantic"}

            print(f"[QwenChaos] Could not parse LLM response, using fallback")
            return self._fallback_drift(packet)

        except Exception as e:
            print(f"[QwenChaos] LLM drift failed: {e}, using fallback")
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


