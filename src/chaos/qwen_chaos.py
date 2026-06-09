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
    
    def _llm_drift(self, packet: Dict) -> Optional[Dict]:
        """Use Qwen LLM to generate semantic drift."""
        try:
            data = packet.get("data", {})
            if not data:
                return None
            
            # Create prompt for field renaming
            prompt = f"""You are a data transformation agent. Your task is to rename fields in JSON data while preserving the values.

Original JSON:
{json.dumps(data, indent=2)}

Instructions:
1. Rename 1-2 fields to semantically similar names
2. Keep all values exactly the same
3. Return ONLY the transformed JSON with renamed fields
4. Do not add any explanation or commentary

Transformed JSON:"""

            # Generate response using ModelManager
            response = self.model_manager.generate_response(
                prompt,
                max_new_tokens=512,
                temperature=0.3,  # Low temperature for more deterministic output
                top_p=0.9,
                do_sample=True
            )
            
            # Parse JSON from response
            try:
                # Try to extract JSON from response
                drifted_data = json.loads(response)
                
                # Validate it's a dict
                if isinstance(drifted_data, dict):
                    return {"data": drifted_data, "sub_type": "qwen_semantic"}
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    try:
                        drifted_data = json.loads(json_match.group(1))
                        if isinstance(drifted_data, dict):
                            return {"data": drifted_data, "sub_type": "qwen_semantic"}
                    except json.JSONDecodeError:
                        pass
                
                print(f"[QwenChaos] Failed to parse LLM response as JSON, using fallback")
                return self._fallback_drift(packet)
                
        except Exception as e:
            print(f"[QwenChaos] LLM drift generation failed: {e}")
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


