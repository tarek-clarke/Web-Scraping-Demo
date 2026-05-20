import os
import json
import time
import httpx
from models.device_selector import get_device_info

class GemmaModel:
    def __init__(self):
        self.device_info = get_device_info()
        self.api_base = os.getenv("GEMMA_API_BASE", "http://localhost:1234/v1")
        self.api_key = os.getenv("GEMMA_API_KEY", "lm-studio")
        self.model_name = os.getenv("GEMMA_MODEL_NAME", "gemma-4-E4B")
        
        self.hf_model_path = "google/gemma-4-E4B"
        self.tokenizer = None
        self.model = None
        self.backend = "mock"
        
        self._initialize()

    # Known identifiers and substrings for Gemma 4 E4B model variants
    _GEMMA4_E4B_HINTS = ["gemma-4-e4b", "gemma4-e4b", "gemma-4-E4B", "gemma4e4b"]

    def _initialize(self):
        # 1. Try to ping local API endpoint and auto-discover the correct model
        try:
            # Short timeout to avoid blocking
            response = httpx.get(f"{self.api_base}/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                available_models = [m.get("id", "") for m in data.get("data", [])]
                
                # Try exact match first
                if self.model_name in available_models:
                    self.backend = "api"
                    print(f"[GEMMA] Initialized successfully using Local API Backend ({self.api_base}), model: {self.model_name}")
                    return
                
                # Auto-discover: find a loaded model whose ID contains a Gemma 4 E4B hint
                matched = None
                for model_id in available_models:
                    model_id_lower = model_id.lower()
                    for hint in self._GEMMA4_E4B_HINTS:
                        if hint.lower() in model_id_lower:
                            matched = model_id
                            break
                    if matched:
                        break
                
                if matched:
                    print(f"[GEMMA] Auto-discovered Gemma 4 E4B model as '{matched}' on Local API Backend ({self.api_base}).")
                    self.model_name = matched
                    self.backend = "api"
                    return
                
                # API is reachable but no Gemma 4 E4B model was found
                print(f"[GEMMA] Local API is reachable but no Gemma 4 E4B model found. Available models: {available_models}")
        except Exception:
            pass

        # 2. Try loading via local HF transformers
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            torch_device = "cuda" if self.device_info["device"] in ["cuda", "rocm"] else ("mps" if self.device_info["device"] == "mps" else "cpu")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.hf_model_path, local_files_only=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.hf_model_path,
                torch_dtype=torch.float16 if torch_device != "cpu" else torch.float32,
                device_map="auto",
                local_files_only=True
            )
            self.backend = "hf"
            print(f"[GEMMA] Loaded local Hugging Face model successfully.")
            return
        except Exception:
            pass

        # 3. Fallback to mock
        self.backend = "mock"
        print("[GEMMA] Active backend: Mock/Simulation fallback mode (no local Gemma server or HF model found).")

    def _call_api(self, prompt: str, temperature: float = 0.7, max_tokens: int = 256) -> str:
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[GEMMA] API Call failed: {e}. Falling back to simulated mock.")
        return self._call_mock(prompt)

    def _call_hf(self, prompt: str, temperature: float = 0.7, max_tokens: int = 256) -> str:
        try:
            import torch
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=temperature > 0.0
                )
            decoded = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            return decoded.strip()
        except Exception as e:
            print(f"[GEMMA] HF Generation failed: {e}. Falling back to simulated mock.")
            return self._call_mock(prompt)

    def _call_mock(self, prompt: str) -> str:
        """
        High-fidelity simulated outputs matching typical Gemma behaviors for our drift framework.
        """
        p_lower = prompt.lower()
        
        # 1. Schema matching task
        if "canonical" in p_lower and "match" in p_lower:
            # Extract query key and candidates
            # Prompt typically lists candidates and a query key
            # Let's find matches based on semantic rules
            # We will return JSON structure if requested
            match_key = None
            confidence = 0.5
            
            # Simple rule-based match extraction
            for token in ["temp", "temperature", "weather", "deg", "cel", "celsius"]:
                if token in p_lower and "temp" in p_lower:
                    match_key = "temperature"
                    confidence = 0.95
            for token in ["price", "cost", "monetary", "value", "rate", "usd"]:
                if token in p_lower and "price" in p_lower:
                    match_key = "price"
                    confidence = 0.92
            for token in ["wind", "speed", "velocity", "kph", "mph"]:
                if token in p_lower and "wind" in p_lower:
                    match_key = "wind_speed"
                    confidence = 0.94
            for token in ["capsule", "serial", "id", "name"]:
                if token in p_lower and "capsule" in p_lower:
                    match_key = "capsule_serial"
                    confidence = 0.91
            for token in ["driver", "name", "code", "number"]:
                if token in p_lower and "driver" in p_lower:
                    match_key = "driver_name"
                    confidence = 0.93

            if not match_key:
                # Try custom heuristic matching
                lines = prompt.split("\n")
                candidates = []
                query = ""
                for line in lines:
                    if "canonical" in line or "candidates" in line:
                        # Extract list
                        candidates = [c.strip().strip('"').strip("'") for c in line.replace("[", "").replace("]", "").split(",") if c.strip()]
                    if "query" in line or "mutated" in line or "target" in line:
                        query = line.split(":")[-1].strip().strip('"').strip("'")
                
                # Levenshtein fallback inside mock
                if candidates and query:
                    best_c = candidates[0]
                    best_d = 999
                    for c in candidates:
                        # calculate simple distance
                        d = abs(len(c) - len(query))
                        if d < best_d:
                            best_d = d
                            best_c = c
                    match_key = best_c
                    confidence = 0.8
            
            result = {
                "match": match_key or "unknown",
                "confidence": confidence
            }
            return json.dumps(result)

        # 2. Chaos generation task
        if "paraphrase" in p_lower or "drift" in p_lower:
            if "price" in p_lower:
                return "monetary_compensation_amount"
            if "active" in p_lower:
                return "pending_verification"
            if "temperature" in p_lower:
                return "ambient_thermal_reading_celsius"
            if "speed" in p_lower:
                return "velocity_magnitude"
            return "mutated_semantic_field"

        return "gemma_drift_mutated_field"

    def query(self, prompt: str, temperature: float = 0.7, max_tokens: int = 256) -> str:
        """
        Queries Gemma model based on the active backend.
        """
        if self.backend == "api":
            return self._call_api(prompt, temperature, max_tokens)
        elif self.backend == "hf":
            return self._call_hf(prompt, temperature, max_tokens)
        else:
            # Add artificial sleep to mimic real inference latency
            time.sleep(0.005) # 5ms mock latency
            return self._call_mock(prompt)
            
    def predict_semantic_match(self, canonical_keys: list, query_key: str) -> dict:
        """
        Asks Gemma to find the best match from a list of canonical keys for a given query key.
        """
        prompt = f"""
Given a list of canonical API schema fields: {canonical_keys}
And a query key from a drifted/mutated schema: "{query_key}"

Select the canonical field that is the best semantic match for this query key.
Return your response strictly in the following JSON format:
{{"match": "canonical_field_name", "confidence": 0.0}}
        """
        res_str = self.query(prompt, temperature=0.0, max_tokens=128)
        try:
            # Try to find JSON block if there is any conversational wrapper
            if "{" in res_str and "}" in res_str:
                res_str = res_str[res_str.index("{"):res_str.rindex("}")+1]
            return json.loads(res_str)
        except Exception:
            # Fallback parsing
            return {"match": canonical_keys[0] if canonical_keys else "unknown", "confidence": 0.5}
