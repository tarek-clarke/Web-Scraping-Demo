#!/usr/bin/env python3
"""
live_gpu_decoder.py — Real-time GPU-accelerated schema reconciliation
on live OpenF1 telemetry data.

Watches the telemetry_latest.json file as the Go ingestor writes to it
(in JSON Lines format — one JSON object per line), processes new packets
through chaos injection and reconciliation, and outputs results to
data/reports/live_f1/.

Usage:
    python3 live_gpu_decoder.py [--chaos-rate 0.10] [--reconciler bert] [--poll-interval 5]
"""

import argparse
import copy
import csv
import json
import os
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.hardware.detector import HardwareDetector
from src.hardware.vram_prober import VRAMProber
from src.reconciliation.engine import ReconciliationEngine
from src.chaos.json_chaos import JSONChaos
from src.chaos.schema_chaos import SchemaChaos
from src.hardware.power_profiler import GPUPowerProfiler

# Lazy imports for quantum routing
FeatureExtractor = None
QuantumRouter = None

def _init_quantum_imports():
    global FeatureExtractor, QuantumRouter
    try:
        from src.routing.feature_extractor import FeatureExtractor
        from src.routing.quantum_router import QuantumRouter
    except ImportError:
        print("[Init] Quantum routing libraries not available. Shadow routing disabled.")

OUTPUT_DIR = "data/reports/live_f1"
TELEMETRY_FILE = "data/ingested/telemetry_latest.json"


# --- Graceful SIGTERM handling (SLURM sends SIGTERM before time limit) ---
_shutdown_requested = False

def _handle_sigterm(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\n[Signal] Received signal {signum}, shutting down gracefully...")

signal.signal(signal.SIGTERM, _handle_sigterm)


class TelemetryTailer:
    """Efficiently tails a JSONL telemetry file, reading only new lines.

    Instead of re-reading the entire file on each poll (which becomes
    impossible at 100M+ lines), this class tracks the byte offset and
    only reads newly appended data. It also detects file recreation
    (when the ingestor restarts and creates a new file via symlink update)
    by monitoring the file's inode.

    Lustre-specific: forces metadata cache invalidation before each stat()
    by performing a brief open/close on the path.
    """

    def __init__(self, filepath):
        self.filepath = filepath
        self._file = None
        self._offset = 0
        self._inode = None
        self.total_count = 0
        self._malformed_count = 0

    def skip_to_end(self):
        """Skip to the end of the file, counting lines for reporting.
        Called once at startup to skip the historical backlog."""
        if not os.path.exists(self.filepath):
            return 0
        try:
            count = 0
            with open(self.filepath, "r") as f:
                for line in f:
                    if line.strip():
                        count += 1
            self.total_count = count
            self._offset = os.path.getsize(self.filepath)
            self._inode = os.stat(self.filepath).st_ino
            return count
        except Exception as e:
            print(f"[Tailer] Error during skip_to_end: {e}")
            return 0

    def _bust_lustre_cache(self):
        """Force Lustre metadata cache invalidation by reopening the path.
        This ensures os.stat() returns fresh st_size, not a stale cached value."""
        try:
            fd = os.open(self.filepath, os.O_RDONLY)
            os.close(fd)
        except OSError:
            pass

    def poll(self, max_new=100000):
        """Read new packets appended since the last poll.

        Returns:
            (new_packets, total_count) where new_packets is a list of
            newly parsed packet dicts, and total_count is the cumulative
            total of all packets seen.
        """
        if not os.path.exists(self.filepath):
            return [], self.total_count

        try:
            # Force Lustre to refresh metadata cache
            self._bust_lustre_cache()

            stat = os.stat(self.filepath)
            current_inode = stat.st_ino

            # Detect file recreation (ingestor restarted, symlink updated)
            if self._inode is not None and current_inode != self._inode:
                print(f"[Tailer] Telemetry file recreated (new inode). Resetting.")
                self._close()
                self._offset = 0
                self.total_count = 0

            self._inode = current_inode

            # Detect file truncation
            if stat.st_size < self._offset:
                print(f"[Tailer] File truncated ({stat.st_size} < {self._offset}). Resetting.")
                self._close()
                self._offset = 0
                self.total_count = 0

            # No new data
            if stat.st_size == self._offset:
                return [], self.total_count

            # Open file if needed
            if self._file is None or self._file.closed:
                self._file = open(self.filepath, "r")

            self._file.seek(self._offset)

            new_packets = []
            lines_read = 0

            while lines_read < max_new:
                pos_before = self._file.tell()
                line = self._file.readline()

                if not line:
                    break  # EOF

                if not line.endswith('\n'):
                    # Incomplete line (writer mid-flush), seek back and retry next poll
                    self._file.seek(pos_before)
                    break

                line = line.strip()
                if line:
                    try:
                        packet = json.loads(line)
                        new_packets.append(packet)
                        self.total_count += 1
                        lines_read += 1
                    except json.JSONDecodeError:
                        self._malformed_count += 1
                        if self._malformed_count % 100 == 1:
                            print(f"[Tailer] Warning: {self._malformed_count} malformed lines skipped")

            self._offset = self._file.tell()
            return new_packets, self.total_count

        except Exception as e:
            print(f"[Tailer] Error reading telemetry: {e}")
            return [], self.total_count

    def _close(self):
        if self._file and not self._file.closed:
            self._file.close()
        self._file = None

    def close(self):
        self._close()


def setup_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return timestamp


def detect_session():
    """Auto-detect the current live F1 session from the OpenF1 API.

    Note: On LUMI compute nodes (no internet), this will timeout in ~2s
    and fall back to 'Unknown' session info. This is expected behavior.
    """
    session_info = {
        "session_name": "Unknown",
        "session_type": "Unknown",
        "country_name": "Unknown",
        "circuit_short_name": "Unknown",
        "session_key": "unknown",
        "year": datetime.utcnow().year,
    }

    try:
        import requests
    except ImportError:
        print("[Session] requests library not available, skipping auto-detect")
        return session_info

    try:
        email = os.getenv("OPENF1_EMAIL", "")
        password = os.getenv("OPENF1_PASSWORD", "")
        headers = {}

        if email and password:
            token_resp = requests.post(
                "https://api.openf1.org/token",
                data={"username": email, "password": password},
                timeout=2,
            )
            if token_resp.status_code == 200:
                token = token_resp.json().get("access_token", "")
                if token:
                    headers["Authorization"] = f"Bearer {token}"

        resp = requests.get(
            "https://api.openf1.org/v1/sessions?session_key=latest",
            headers=headers,
            timeout=2,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                s = data[0]
            elif isinstance(data, dict):
                s = data
            else:
                return session_info

            session_info["session_name"] = s.get("session_name", "Unknown")
            session_info["session_type"] = s.get("session_type", "Unknown")
            session_info["country_name"] = s.get("country_name", "Unknown")
            session_info["circuit_short_name"] = s.get("circuit_short_name", "Unknown")
            session_info["session_key"] = s.get("session_key", "unknown")
            session_info["year"] = s.get("year", datetime.utcnow().year)
    except Exception as e:
        print(f"[Session] Could not auto-detect session: {e}")
        print(f"[Session] (This is expected on LUMI compute nodes with no internet access)")

    return session_info


def detect_hardware():
    detector = HardwareDetector()
    hardware = detector.detect()
    prober = VRAMProber(hardware["type"])
    vram_info = prober.probe()

    print("=== Live F1 GPU Decoder ===")
    print(f"GPU Model: {hardware['model']}")
    print(f"Hardware Type: {hardware['type']}")
    print(f"Device: {'cuda' if hardware['type'] in ['cuda', 'rocm'] else 'cpu'}")
    print(f"Total VRAM: {hardware['vram_gb']} GB")
    print(f"Free VRAM: {vram_info['free_gb']:.2f} GB")
    print()

    return hardware, vram_info


def inject_chaos(packet, chaos_method, chaos_rate, json_chaos, schema_chaos, rng_seed):
    """Inject chaos into a single packet and return (original, drifted, sub_type).

    Uses an instance-based RNG to avoid corrupting the global random state.
    """
    rng = random.Random(rng_seed)

    if rng.random() > chaos_rate:
        return None  # No drift for this packet

    original = copy.deepcopy(packet)
    drifted = copy.deepcopy(packet)
    data = drifted.get("data", {})

    if chaos_method == "json_manip":
        sub_type, modified = json_chaos.inject_with_subtype(data)
    elif chaos_method == "schema_alter":
        sub_type, modified = schema_chaos.alter_with_subtype(data)
    else:
        sub_type, modified = json_chaos.inject_with_subtype(data)

    drifted["data"] = modified
    return original, drifted, sub_type


def main():
    parser = argparse.ArgumentParser(description="Live F1 GPU Decoder")
    parser.add_argument("--chaos-rate", type=float, default=0.10,
                        help="Chaos injection rate 0-1 (default: 0.10)")
    parser.add_argument("--reconciler", type=str, default="bert",
                        choices=["levenshtein", "regex", "bert"],
                        help="Reconciler to use (default: bert)")
    parser.add_argument("--chaos-method", type=str, default="json_manip",
                        choices=["json_manip", "schema_alter"],
                        help="Chaos injection method (default: json_manip)")
    parser.add_argument("--poll-interval", type=float, default=5.0,
                        help="Seconds between file polls (default: 5)")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="Batch size for reconciliation (default: 16)")
    parser.add_argument("--shadow-routing", action="store_true",
                        help="Enable VQC shadow routing and log features for QPU execution")
    args = parser.parse_args()

    hardware, vram_info = detect_hardware()
    hw_type = hardware["type"]
    timestamp = setup_output_dir()

    # Initialize Shadow Routing components if enabled
    extractor = None
    router = None
    shadow_log_data = []
    if args.shadow_routing:
        _init_quantum_imports()
        if FeatureExtractor and QuantumRouter:
            print("[Init] Initializing VQC Shadow Router (AerSimulator)...")
            extractor = FeatureExtractor()
            router = QuantumRouter(backend="aer_simulator")
            print("[Init] VQC Shadow Router initialized successfully.")
        else:
            print("[WARNING] Could not load quantum libraries. Shadow routing disabled.")
            args.shadow_routing = False

    # Auto-detect live session
    print("[Init] Detecting live F1 session...")
    session_info = detect_session()
    session_label = f"{session_info['country_name']} — {session_info['session_name']}"
    print(f"[Session] {session_label}")
    print(f"[Session] Circuit: {session_info['circuit_short_name']}")
    print(f"[Session] Key: {session_info['session_key']}")
    print()

    # Initialize reconciliation engine
    print(f"[Init] Loading {args.reconciler} reconciler on {hw_type}...")
    engine = ReconciliationEngine(hw_type, args.batch_size)
    print(f"[Init] Reconciler ready.")
    print(f"[Init] Chaos method: {args.chaos_method} @ {args.chaos_rate:.0%} rate")
    print(f"[Init] Polling {TELEMETRY_FILE} every {args.poll_interval}s")
    print(f"[Init] Results → {OUTPUT_DIR}/")
    print()

    json_chaos = JSONChaos()
    schema_chaos = SchemaChaos()

    # CSV output for live results
    csv_path = f"{OUTPUT_DIR}/live_results_{timestamp}.csv"
    csv_fields = [
        "timestamp", "packet_idx", "source", "driver_number",
        "chaos_method", "chaos_sub_type", "reconciler",
        "accuracy", "latency_ms", "mapped_fields", "unmapped_fields"
    ]
    csvfile = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
    writer.writeheader()

    # Summary stats
    stats = {
        "total_processed": 0,
        "total_drifted": 0,
        "total_reconciled": 0,
        "accuracy_sum": 0.0,
        "latency_sum": 0.0,
    }

    # Initialize file tailer (reads only new lines, O(1) memory per poll)
    tailer = TelemetryTailer(TELEMETRY_FILE)
    backlog_count = tailer.skip_to_end()

    print("=" * 70)
    print(f"  LIVE F1 TELEMETRY DECODER — {session_label}")
    print("=" * 70)
    print(f"[Init] Skipping historical backlog of {backlog_count:,} packets to keep it truly live.")

    # Start the scientific GPU energy and power profiler
    profiler = GPUPowerProfiler(interval_sec=0.05)
    profiler.start()

    try:
        while not _shutdown_requested:
            new_packets, total_count = tailer.poll()

            if not new_packets:
                time.sleep(args.poll_interval)
                continue

            new_count = len(new_packets)
            batch_start = time.perf_counter()
            drifted_count = 0
            reconciled_count = 0

            # 1. Classical preprocessing / chaos injection
            drifted_packets_info = []
            for idx, packet in enumerate(new_packets):
                i = total_count - new_count + idx
                stats["total_processed"] += 1

                result = inject_chaos(
                    packet, args.chaos_method, args.chaos_rate,
                    json_chaos, schema_chaos, rng_seed=i
                )

                if result is not None:
                    original, drifted, sub_type = result
                    drifted_packets_info.append({
                        "original": original,
                        "drifted": drifted,
                        "sub_type": sub_type,
                        "packet_idx": i,
                        "packet": packet
                    })

                    # If shadow routing is active, extract features and get classification decision
                    if args.shadow_routing:
                        try:
                            feat = extractor.extract(original["data"], drifted["data"], packet.get("source", "openf1"))
                            reconciler_name, confidence = router.route_packet(feat)
                            shadow_log_data.append({
                                "packet_idx": i,
                                "source": packet.get("source", "openf1"),
                                "features": feat.tolist(),
                                "emulator_decision": reconciler_name,
                                "emulator_confidence": float(confidence),
                                "actual_reconciler_used": args.reconciler
                            })
                        except Exception as e:
                            print(f"[ERROR] Shadow routing failed on packet {i}: {e}")

            drifted_count = len(drifted_packets_info)
            stats["total_drifted"] += drifted_count

            # 2. Reconcile on GPU in batches (with exception guard)
            if drifted_count > 0:
                batch_size = args.batch_size
                for b_start in range(0, drifted_count, batch_size):
                    b_info = drifted_packets_info[b_start:b_start + batch_size]
                    pairs = [(x["original"]["data"], x["drifted"]["data"]) for x in b_info]

                    try:
                        # Perform batched reconciliation
                        rec_start = time.perf_counter()
                        if args.reconciler == "bert":
                            rec_results = engine.reconcile_bert_batch(pairs)
                        elif args.reconciler == "gemma_e4b":
                            rec_results = engine.reconcile_gemma_batch(pairs)
                        else:
                            rec_results = [engine.reconcile(x["original"], x["drifted"], args.reconciler) for x in b_info]

                        batch_latency_ms = (time.perf_counter() - rec_start) * 1000
                        per_packet_latency = batch_latency_ms / len(b_info)

                        for idx_b, x in enumerate(b_info):
                            rec_result = rec_results[idx_b]
                            reconciled_count += 1
                            stats["total_reconciled"] += 1
                            stats["accuracy_sum"] += rec_result["accuracy"]
                            stats["latency_sum"] += per_packet_latency

                            driver_num = x["packet"].get("data", {}).get("driver_number", "?")

                            # Write to CSV
                            writer.writerow({
                                "timestamp": datetime.utcnow().isoformat(),
                                "packet_idx": x["packet_idx"],
                                "source": x["packet"].get("source", "openf1"),
                                "driver_number": driver_num,
                                "chaos_method": args.chaos_method,
                                "chaos_sub_type": x["sub_type"],
                                "reconciler": args.reconciler,
                                "accuracy": round(rec_result["accuracy"], 4),
                                "latency_ms": round(per_packet_latency, 3),
                                "mapped_fields": rec_result["mapped_fields"],
                                "unmapped_fields": rec_result["unmapped_fields"],
                            })

                    except Exception as e:
                        print(f"[ERROR] Reconciliation failed on batch {b_start}-{b_start+len(b_info)}: {e}")
                        continue

                csvfile.flush()

            batch_elapsed = (time.perf_counter() - batch_start) * 1000

            # Print batch summary
            avg_acc = (stats["accuracy_sum"] / stats["total_reconciled"] * 100) if stats["total_reconciled"] > 0 else 0
            avg_lat = (stats["latency_sum"] / stats["total_reconciled"]) if stats["total_reconciled"] > 0 else 0

            print(
                f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
                f"Processed {new_count:,} new packets | "
                f"Drifted: {drifted_count:,} | "
                f"Reconciled: {reconciled_count:,} | "
                f"Batch: {batch_elapsed:.0f}ms | "
                f"Avg Acc: {avg_acc:.1f}% | "
                f"Avg Lat: {avg_lat:.2f}ms | "
                f"Total: {stats['total_processed']:,}"
            )

            time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        print("\n[Signal] KeyboardInterrupt received.")
    except Exception as e:
        print(f"\n[FATAL] Decoder crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always cleanup, even on crash
        print("\n" + "=" * 70)
        print("  LIVE SESSION ENDED — Writing summary...")
        print("=" * 70)

        # Stop power profiler and extract energy metrics
        energy_metrics = {"total_joules": 0.0, "avg_watts": 0.0, "samples_count": 0}
        try:
            energy_metrics = profiler.stop()
        except Exception:
            pass

        tailer.close()

        # Flush and sync CSV to disk
        try:
            csvfile.flush()
            os.fsync(csvfile.fileno())
            csvfile.close()
        except Exception:
            pass

        # Write summary manifest
        manifest = {
            "run_id": timestamp,
            "session": session_label,
            "session_name": session_info["session_name"],
            "session_type": session_info["session_type"],
            "country": session_info["country_name"],
            "circuit": session_info["circuit_short_name"],
            "session_key": session_info["session_key"],
            "year": session_info["year"],
            "hardware_model": hardware.get("model", "unknown"),
            "hardware_type": hw_type,
            "reconciler": args.reconciler,
            "chaos_method": args.chaos_method,
            "chaos_rate": args.chaos_rate,
            "total_packets_processed": stats["total_processed"],
            "total_drifted": stats["total_drifted"],
            "total_reconciled": stats["total_reconciled"],
            "avg_accuracy": round(stats["accuracy_sum"] / max(stats["total_reconciled"], 1), 4),
            "avg_latency_ms": round(stats["latency_sum"] / max(stats["total_reconciled"], 1), 3),
            "gpu_total_energy_joules": energy_metrics.get("total_joules", 0.0),
            "gpu_avg_power_watts": energy_metrics.get("avg_watts", 0.0),
            "gpu_energy_samples": energy_metrics.get("samples_count", 0),
        }

        manifest_path = f"{OUTPUT_DIR}/manifest_{timestamp}.json"
        try:
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            os.fsync(f.fileno())
        except Exception:
            pass

        if args.shadow_routing and shadow_log_data:
            shadow_path = f"{OUTPUT_DIR}/shadow_log_{timestamp}.json"
            try:
                with open(shadow_path, "w") as f:
                    json.dump(shadow_log_data, f, indent=2)
                print(f"  Shadow routing log saved to: {shadow_path}")
            except Exception as e:
                print(f"[ERROR] Failed to save shadow routing log: {e}")

        print(f"\n  Results saved to: {csv_path}")
        print(f"  Manifest saved to: {manifest_path}")
        print(f"\n  Total Packets: {stats['total_processed']:,}")
        print(f"  Total Drifted: {stats['total_drifted']:,}")
        print(f"  Total Reconciled: {stats['total_reconciled']:,}")
        if stats["total_reconciled"] > 0:
            print(f"  Avg Accuracy: {stats['accuracy_sum'] / stats['total_reconciled'] * 100:.2f}%")
            print(f"  Avg Latency: {stats['latency_sum'] / stats['total_reconciled']:.3f}ms")
        if energy_metrics.get("total_joules", 0.0) > 0:
            print(f"  Total GPU Energy Consumed: {energy_metrics['total_joules']:,} Joules")
            print(f"  Average GPU Power Draw: {energy_metrics['avg_watts']:.2f} Watts")
        print()


if __name__ == "__main__":
    main()
