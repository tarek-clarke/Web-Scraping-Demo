import json
import random
import os
from typing import Dict, List
from datetime import datetime
from pathlib import Path
from .gemma_chaos import GemmaChaos
from .json_chaos import JSONChaos
from .schema_chaos import SchemaChaos

ROOT = Path(__file__).resolve().parent.parent.parent

class ChaosInjector:
    def __init__(self, chaos_rate: float = 0.05):
        self.chaos_rate = chaos_rate
        self.chaos_log = []
        self.chaos_methods = {
            "gemma": self._apply_gemma_drift,
            "json_manip": self._apply_json_drift,
            "schema_alter": self._apply_schema_drift,
        }
        self.gemma_chaos = GemmaChaos(str(ROOT / "models" / "gemma4-e4b-it.gguf"))
        self.json_chaos = JSONChaos()
        self.schema_chaos = SchemaChaos()

    def inject(self, packets: List[Dict], force_method: str = None) -> List[Dict]:
        injected = []
        methods_list = ["gemma", "json_manip", "schema_alter"]

        for i, packet in enumerate(packets):
            if random.random() < self.chaos_rate:
                method = force_method if force_method else random.choice(methods_list)
                drifted, drift_event = self._apply_drift(packet, method)
                self.chaos_log.append(drift_event)
                injected.append(drifted)
            else:
                injected.append(packet)

        log_path = ROOT / "data" / "chaos_log" / "chaos_events.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(self.chaos_log, f, indent=2)

        return injected

    def _apply_drift(self, packet: Dict, method: str) -> tuple:
        method_fn = self.chaos_methods.get(method, self._apply_json_drift)

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "drift_type": None,
            "original_packet": packet.copy(),
            "source": packet.get("source", "unknown"),
            "drift_description": None,
        }

        result = method_fn(packet, event)
        return result

    def _apply_gemma_drift(self, packet: Dict, event: Dict) -> tuple:
        drifted = packet.copy()
        result = self.gemma_chaos.generate_drift(packet)
        if result and result.get("data"):
            drifted["data"] = result["data"]
            event["drift_type"] = "llm_semantic_31b"
            event["drift_description"] = result.get("_drift_note", "Gemma4-31B semantic drift")
            event["chaos_model"] = "gemma4-31b"
        else:
            drifted, ev = self._fallback_traditional(packet)
            event["drift_type"] = ev["drift_type"]
            event["drift_description"] = "Fallback to traditional drift"
            event["chaos_model"] = "fallback"
        event["drifted_packet"] = drifted
        return drifted, event

    def _apply_json_drift(self, packet: Dict, event: Dict) -> tuple:
        drifted = packet.copy()
        drifted["data"] = self.json_chaos.inject(drifted.get("data", {}))
        event["drift_type"] = "json_manipulation"
        event["drift_description"] = "JSON structure manipulation (noise/shuffle/wrap)"
        event["drifted_packet"] = drifted
        return drifted, event

    def _apply_schema_drift(self, packet: Dict, event: Dict) -> tuple:
        drifted = packet.copy()
        drifted["data"] = self.schema_chaos.alter(drifted.get("data", {}))
        event["drift_type"] = "schema_alteration"
        event["drift_description"] = "Schema structural alteration (type_coerce/rename/flatten)"
        event["drifted_packet"] = drifted
        return drifted, event

    def _fallback_traditional(self, packet: Dict) -> tuple:
        """Fallback if Gemma LLM fails — use traditional drift types."""
        drift_types = ["field_split", "field_join", "translation", "variable_drop"]
        drift_type = random.choice(drift_types)

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": "gemma_fallback",
            "drift_type": drift_type,
            "original_packet": packet.copy(),
            "source": packet.get("source", "unknown"),
        }

        drifted = packet.copy()
        data = drifted.get("data", {})

        if drift_type == "field_split":
            data = self._field_split(data)
        elif drift_type == "field_join":
            data = self._field_join(data)
        elif drift_type == "translation":
            data = self._translation(data)
        elif drift_type == "variable_drop":
            data = self._variable_drop(data)

        drifted["data"] = data
        event["drifted_packet"] = drifted
        return drifted, event

    def _field_split(self, data: Dict) -> Dict:
        if not data:
            return data
        key = random.choice(list(data.keys()))
        val = data.pop(key)
        data[f"{key}_part1"] = val
        data[f"{key}_part2"] = val
        return data

    def _field_join(self, data: Dict) -> Dict:
        keys = list(data.keys())
        if len(keys) < 2:
            return data
        k1, k2 = random.sample(keys, 2)
        joined = f"{k1}_{k2}"
        data[joined] = data.pop(k1)
        data.pop(k2, None)
        return data

    def _translation(self, data: Dict) -> Dict:
        translations = {
            "temperature": "temp_c",
            "speed": "velocity",
            "price": "cost",
            "timestamp": "ts"
        }
        for old, new in translations.items():
            if old in data:
                data[new] = data.pop(old)
        return data

    def _variable_drop(self, data: Dict) -> Dict:
        if not data:
            return data
        key = random.choice(list(data.keys()))
        data.pop(key)
        return data
