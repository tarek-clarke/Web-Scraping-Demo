import json
import random
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from .qwen_chaos import QwenChaos
from .json_chaos import JSONChaos
from .schema_chaos import SchemaChaos

ROOT = Path(__file__).resolve().parent.parent.parent

class ChaosInjector:
    def __init__(self, chaos_rate: float = 0.10):
        self.chaos_rate = chaos_rate
        self.chaos_log = []
        self.chaos_methods = {
            "qwen": self._apply_qwen_drift,
            "json_manip": self._apply_json_drift,
            "schema_alter": self._apply_schema_drift,
        }
        self.qwen_chaos = QwenChaos()
        self.json_chaos = JSONChaos()
        self.schema_chaos = SchemaChaos()
        self._sub_type_store: Dict[Tuple[int, int], str] = {}

    def inject(self, packets: List[Dict], force_method: str = None, seed: int = 0) -> List[Dict]:
        injected = []
        methods_list = ["qwen", "json_manip", "schema_alter"]
        random.seed(seed)

        # Ensure exact same number of drifted packets across all runs
        num_to_drift = max(1, int(len(packets) * self.chaos_rate))
        drift_indices = set(random.sample(range(len(packets)), num_to_drift))

        for i, packet in enumerate(packets):
            if i in drift_indices:
                method = force_method if force_method else random.choice(methods_list)
                drifted, drift_event, sub_type = self._apply_drift(packet, method, seed, i)
                self.chaos_log.append(drift_event)
                self._sub_type_store[(i, seed)] = sub_type
                injected.append(drifted)
            else:
                injected.append(packet)

        return injected

    def get_sub_type(self, packet_idx: int, seed: int) -> str:
        return self._sub_type_store.get((packet_idx, seed), "unknown")

    def _apply_drift(self, packet: Dict, method: str, seed: int, packet_idx: int) -> tuple:
        import copy
        orig_copy = copy.deepcopy(packet)
        method_fn = self.chaos_methods.get(method, self._apply_json_drift)
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "drift_type": None,
            "original_packet": copy.deepcopy(orig_copy),
            "source": packet.get("source", "unknown"),
            "drift_description": None,
        }
        return method_fn(orig_copy, event, seed, packet_idx)

    def _apply_qwen_drift(self, packet: Dict, event: Dict, seed: int, packet_idx: int) -> tuple:
        drifted = packet.copy()
        try:
            sub_type, modified_data = self.qwen_chaos.inject_with_subtype(drifted.get("data", {}))
            drifted["data"] = modified_data
            event["drift_type"] = "qwen_semantic"
            event["drift_description"] = f"Qwen-style semantic field drift: {sub_type}"
            event["chaos_model"] = "qwen_local"
        except Exception:
            drifted, ev, sub_type = self._fallback_traditional(packet, seed, packet_idx)
            event["drift_type"] = ev["drift_type"]
            event["drift_description"] = "Fallback to traditional drift"
            event["chaos_model"] = "fallback"
            sub_type = ev["drift_type"]
        event["drifted_packet"] = drifted
        return drifted, event, sub_type

    def _apply_json_drift(self, packet: Dict, event: Dict, seed: int, packet_idx: int) -> tuple:
        drifted = packet.copy()
        sub_type, modified_data = self.json_chaos.inject_with_subtype(drifted.get("data", {}))
        drifted["data"] = modified_data
        event["drift_type"] = "json_manipulation"
        event["drift_description"] = f"JSON structure manipulation: {sub_type}"
        event["drifted_packet"] = drifted
        return drifted, event, sub_type

    def _apply_schema_drift(self, packet: Dict, event: Dict, seed: int, packet_idx: int) -> tuple:
        drifted = packet.copy()
        sub_type, modified_data = self.schema_chaos.alter_with_subtype(drifted.get("data", {}))
        drifted["data"] = modified_data
        event["drift_type"] = "schema_alteration"
        event["drift_description"] = f"Schema structural alteration: {sub_type}"
        event["drifted_packet"] = drifted
        return drifted, event, sub_type

    def _fallback_traditional(self, packet: Dict, seed: int, packet_idx: int) -> tuple:
        drift_types = ["field_split", "field_join", "translation", "variable_drop"]
        drift_type = random.choice(drift_types)
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": "fallback",
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
        return drifted, event, drift_type

    def _field_split(self, data: Dict) -> Dict:
        if not data: return data
        key = random.choice(list(data.keys()))
        val = data.pop(key)
        data[f"{key}_part1"] = val
        data[f"{key}_part2"] = val
        return data

    def _field_join(self, data: Dict) -> Dict:
        keys = list(data.keys())
        if len(keys) < 2: return data
        k1, k2 = random.sample(keys, 2)
        joined = f"{k1}_{k2}"
        data[joined] = data.pop(k1)
        data.pop(k2, None)
        return data

    def _translation(self, data: Dict) -> Dict:
        t = {"temperature": "temp_c", "speed": "velocity", "price": "cost", "timestamp": "ts"}
        for old, new in t.items():
            if old in data: data[new] = data.pop(old)
        return data

    def _variable_drop(self, data: Dict) -> Dict:
        if not data: return data
        data.pop(random.choice(list(data.keys())), None)
        return data

    def get_ground_truth_map(self, original: Dict, drifted: Dict) -> Dict[str, str]:
        orig_keys = set(original.get("data", {}).keys())
        drift_keys = set(drifted.get("data", {}).keys())
        added = drift_keys - orig_keys
        removed = orig_keys - drift_keys
        unchanged = orig_keys & drift_keys
        mapping = {}
        for key in added:
            mapping[key] = f"added:{key}"
        for key in removed:
            mapping[f"removed:{key}"] = key
        for key in unchanged:
            if original.get("data", {}).get(key) != drifted.get("data", {}).get(key):
                mapping[key] = f"modified:{key}"
            else:
                mapping[key] = key
        return mapping