import os
import csv
import json
import time
from datetime import datetime
from models.device_selector import get_device_info

class DriftLogger:
    def __init__(self, base_dir: str = "logs"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.csv_path = os.path.join(self.base_dir, "drift_events.csv")
        self.json_path = os.path.join(self.base_dir, "drift_events.json")
        
        # Get hardware and cloud platform specs
        self.device_info = get_device_info()
        self.hardware_platform = self.device_info["device"].upper()
        self.hardware_model = self.device_info["model"]
        self.cloud_platform = self.device_info["cloud"]
        
        self.headers = [
            "timestamp", "api_source", "run_number", "hardware_platform", 
            "hardware_model", "cloud_platform", "chaos_strategy", "chaos_level", 
            "drift_type", "original_field", "mutated_field", "metadata"
        ]
        
        # Initialize in-memory write buffers
        self.buffered_rows = []
        self.buffered_events = []
        
        # Initialize files with headers
        self._initialize_files()

    def _initialize_files(self):
        # CSV initialization
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)
        
        # JSON initialization
        if not os.path.exists(self.json_path):
            with open(self.json_path, mode="w", encoding="utf-8") as f:
                json.dump([], f)

    def log_event(self, api_source: str, run_number: int, chaos_strategy: str, 
                  chaos_level: float, drift_type: str, original_field: str, 
                  mutated_field: str, metadata: dict = None):
        """
        Logs a single drift event by buffering it in memory to minimize I/O overhead.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        metadata_str = json.dumps(metadata or {})
        
        row = [
            timestamp, api_source, run_number, self.hardware_platform,
            self.hardware_model, self.cloud_platform, chaos_strategy, chaos_level,
            drift_type, original_field, mutated_field, metadata_str
        ]
        self.buffered_rows.append(row)
        
        event = {
            "timestamp": timestamp,
            "api_source": api_source,
            "run_number": run_number,
            "hardware_platform": self.hardware_platform,
            "hardware_model": self.hardware_model,
            "cloud_platform": self.cloud_platform,
            "chaos_strategy": chaos_strategy,
            "chaos_level": chaos_level,
            "drift_type": drift_type,
            "original_field": original_field,
            "mutated_field": mutated_field,
            "metadata": metadata or {}
        }
        self.buffered_events.append(event)

    def flush(self):
        """
        Flushes all buffered events and rows to disk in a single I/O operation.
        """
        if not self.buffered_rows and not self.buffered_events:
            return
            
        # 1. Flush CSV
        try:
            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(self.buffered_rows)
            self.buffered_rows.clear()
        except Exception as e:
            print(f"[Logger] Error flushing to CSV: {e}")
            
        # 2. Flush JSON
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, mode="r", encoding="utf-8") as f:
                    try:
                        events = json.load(f)
                    except json.JSONDecodeError:
                        events = []
            else:
                events = []
                
            events.extend(self.buffered_events)
            self.buffered_events.clear()
            
            with open(self.json_path, mode="w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)
        except Exception as e:
            print(f"[Logger] Error flushing to JSON: {e}")

    def add_runtime_to_drift_logs(self, api_source: str, run_number: int, total_runtime_sec: float):
        """
        Dynamically updates the drift JSON and CSV logs, injecting total_runtime_sec into the metadata.
        """
        # 1. Update JSON
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, mode="r", encoding="utf-8") as f:
                    try:
                        events = json.load(f)
                    except json.JSONDecodeError:
                        events = []
                updated = False
                for ev in events:
                    if ev.get("api_source") == api_source and str(ev.get("run_number")) == str(run_number):
                        if "metadata" not in ev or not isinstance(ev["metadata"], dict):
                            ev["metadata"] = {}
                        ev["metadata"]["total_runtime_sec"] = total_runtime_sec
                        updated = True
                if updated:
                    with open(self.json_path, mode="w", encoding="utf-8") as f:
                        json.dump(events, f, indent=2)
        except Exception as e:
            print(f"[Logger] Error updating JSON drift logs: {e}")

        # 2. Update CSV
        try:
            if os.path.exists(self.csv_path):
                rows = []
                with open(self.csv_path, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    try:
                        headers = next(reader)
                        rows.append(headers)
                    except StopIteration:
                        headers = []
                    
                    if headers:
                        try:
                            api_idx = headers.index("api_source")
                            run_idx = headers.index("run_number")
                            meta_idx = headers.index("metadata")
                        except ValueError:
                            api_idx, run_idx, meta_idx = 1, 2, 11
                        
                        for row in reader:
                            if len(row) > max(api_idx, run_idx, meta_idx):
                                if row[api_idx] == api_source and str(row[run_idx]) == str(run_number):
                                    try:
                                        meta = json.loads(row[meta_idx]) if row[meta_idx] else {}
                                    except Exception:
                                        meta = {}
                                    meta["total_runtime_sec"] = total_runtime_sec
                                    row[meta_idx] = json.dumps(meta)
                            rows.append(row)
                
                if rows:
                    with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerows(rows)
        except Exception as e:
            print(f"[Logger] Error updating CSV drift logs: {e}")

    # --- Additional logging methods for chaos/reconciliation pipeline ---

    def _append_to_json_file(self, filename, data_dict):
        """Helper to append a dict to a JSON list in base_dir/filename."""
        path = os.path.join(self.base_dir, filename)
        items = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if not isinstance(items, list):
                        items = []
            except (json.JSONDecodeError, FileNotFoundError):
                items = []
        items.append(data_dict)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)

    def log_chaos(self, chaos_trace: dict):
        """Record the chaos trace for this mutation."""
        self._append_to_json_file("chaos_log.json", chaos_trace)

    def log_drift(self, drift_info: dict):
        """Record drift detection results."""
        self._append_to_json_file("drift_detection_log.json", drift_info)

    def log_reconciliation(self, recon_info: dict):
        """Record reconciliation outcome."""
        self._append_to_json_file("reconciliation_log.json", recon_info)
