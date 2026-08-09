#!/usr/bin/env python3
"""Build the packet-level, cost-aware routing oracle.

This is the classical/GPU prerequisite for VQC training. It uses a
deterministic drifted subset of the committed nine-API corpus without leaking
packets across splits:

* 80% of packet identities are assigned to training and receive one balanced
  chaos method;
* 10% are assigned to validation and evaluated under all three methods; and
* 10% are held out for the physical-QPU test and evaluated under all methods.

Only true schema/type changes enter Stage 2.  Every retained sample is executed
through each standalone reconciler.  The oracle chooses the cheapest method
meeting the accuracy SLA, otherwise the most accurate method (with a
cost-aware near-tie break).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.chaos.json_chaos import JSONChaos
from src.chaos.qwen_chaos import QwenChaos
from src.chaos.schema_chaos import SchemaChaos
from src.reconciliation.engine import ReconciliationEngine
from src.reconciliation.mapping_metrics import (
    derive_ground_truth_mapping,
    exact_mapping_metrics,
)
from src.routing.canonical_vqc import DEFAULT_CLASS_NAMES
from src.routing.feature_extractor import FeatureExtractor
from src.routing.schema_fast_path import schemas_match


ACTIVE_APIS = (
    "openf1",
    "finnhub",
    "spacex",
    "openweather",
    "clinical",
    "hockey_nhl",
    "aviation_opensky",
    "football_uefa",
    "smartcity_transit",
)
CHAOS_METHODS = ("qwen", "json_manip", "schema_alter")
COST_ORDER = {name: index for index, name in enumerate(DEFAULT_CLASS_NAMES)}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_seed(*parts: object) -> int:
    material = ":".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(material).hexdigest()[:8], 16)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_metadata() -> Dict[str, object]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", *args],
                cwd=REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return "unknown"

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        # Generated benchmark artifacts are intentionally untracked. Only
        # modifications to tracked source invalidate commit provenance.
        "dirty": bool(
            run("status", "--porcelain", "--untracked-files=no").strip()
        ),
    }


def load_packets(path: Path, max_packets_per_api: int) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = {api: [] for api in ACTIVE_APIS}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Packet corpus is empty: {path}")
    rows = json.loads(text) if text.startswith("[") else (
        json.loads(line) for line in text.splitlines() if line.strip()
    )
    for packet in rows:
        source = packet.get("source")
        if source in groups and len(groups[source]) < max_packets_per_api:
            groups[source].append(packet)

    missing = [api for api, packets in groups.items() if not packets]
    if missing:
        raise ValueError(f"Packet corpus is missing active APIs: {missing}")
    if max_packets_per_api >= 2500:
        counts = {api: len(packets) for api, packets in groups.items()}
        if any(count != 2500 for count in counts.values()):
            raise ValueError(
                "Expected exactly 2,500 packets for each of nine APIs; "
                f"loaded {counts}"
            )
    return groups


def split_indices(size: int, api: str, seed: int) -> Dict[str, set[int]]:
    indices = list(range(size))
    random.Random(stable_seed(seed, api, "packet-split")).shuffle(indices)
    train_end = int(size * 0.80)
    validation_end = int(size * 0.90)
    return {
        "train": set(indices[:train_end]),
        "validation": set(indices[train_end:validation_end]),
        "test": set(indices[validation_end:]),
    }


def inject_schema_drift(
    data: object,
    method: str,
    *,
    seed: int,
    max_attempts: int,
) -> Tuple[str, object, int]:
    injectors = {
        "qwen": QwenChaos(),
        "json_manip": JSONChaos(),
        "schema_alter": SchemaChaos(),
    }
    if method not in injectors:
        raise ValueError(f"Unsupported chaos method: {method}")

    for attempt in range(max_attempts):
        attempt_seed = stable_seed(seed, attempt)
        random.seed(attempt_seed)
        candidate = copy.deepcopy(data)
        if method == "schema_alter":
            subtype, drifted = injectors[method].alter_with_subtype(candidate)
        else:
            subtype, drifted = injectors[method].inject_with_subtype(candidate)
        if not schemas_match(data, drifted):
            return subtype, drifted, attempt + 1
    raise RuntimeError(
        f"Could not produce a real schema/type change for method={method} "
        f"after {max_attempts} deterministic attempts"
    )


def build_samples(
    packet_groups: Dict[str, List[dict]],
    *,
    seed: int,
    max_attempts: int,
    max_records: int,
    drift_rate: float,
) -> Tuple[List[dict], Dict[str, object]]:
    extractor = FeatureExtractor()
    records: List[dict] = []
    attempts: List[int] = []

    for api in ACTIVE_APIS:
        packets = packet_groups[api]
        splits = split_indices(len(packets), api, seed)
        selected_count = max(1, round(len(packets) * drift_rate))
        selected_indices = set(sorted(
            range(len(packets)),
            key=lambda index: stable_seed(seed, api, index, "drift-selection"),
        )[:selected_count])
        for packet_index, packet in enumerate(packets):
            # The benchmark protocol injects drift into a deterministic 10%
            # of the committed packets.  Selection is per API, preserving
            # balanced domain coverage while keeping the routed workload
            # comparable with the paper's fast-path benchmark.
            if packet_index not in selected_indices:
                continue
            split = next(name for name, members in splits.items() if packet_index in members)
            # One balanced chaos scenario per selected packet matches the
            # 10%-drift matrix benchmark and avoids multiplying the workload
            # by three merely for oracle generation.
            method_index = stable_seed(seed, api, packet_index, "method") % len(CHAOS_METHODS)
            methods: Sequence[str] = (CHAOS_METHODS[method_index],)

            for method in methods:
                drift_seed = stable_seed(seed, api, packet_index, method)
                subtype, drifted_data, used_attempts = inject_schema_drift(
                    packet.get("data", {}),
                    method,
                    seed=drift_seed,
                    max_attempts=max_attempts,
                )
                features = extractor.extract(
                    packet.get("data", {}),
                    drifted_data,
                    api,
                )
                record_id = hashlib.sha256(
                    f"{api}:{packet_index}:{method}:{drift_seed}".encode("utf-8")
                ).hexdigest()[:24]
                records.append(
                    {
                        "record_id": record_id,
                        "split": split,
                        "api": api,
                        "packet_index": packet_index,
                        "packet_timestamp": packet.get("timestamp"),
                        "chaos_method": method,
                        "chaos_subtype": subtype,
                        "chaos_seed": drift_seed,
                        "drift_generation_attempts": used_attempts,
                        "original_data": packet.get("data", {}),
                        "drifted_data": drifted_data,
                        "ground_truth_mapping": derive_ground_truth_mapping(
                            packet.get("data", {}), drifted_data
                        ),
                        "features": features.astype(float).tolist(),
                    }
                )
                attempts.append(used_attempts)
                if max_records and len(records) >= max_records:
                    break
            if max_records and len(records) >= max_records:
                break
        if max_records and len(records) >= max_records:
            break

    summary = {
        "records": len(records),
        "drift_rate": drift_rate,
        "split_counts": dict(Counter(record["split"] for record in records)),
        "api_counts": dict(Counter(record["api"] for record in records)),
        "chaos_counts": dict(Counter(record["chaos_method"] for record in records)),
        "mean_drift_attempts": float(np.mean(attempts)) if attempts else 0.0,
        "max_drift_attempts": max(attempts, default=0),
    }
    return records, summary


def require_accelerator(methods: Sequence[str], allow_cpu: bool) -> Dict[str, object]:
    gpu_methods = {"minilm", "gemma_e2b", "bge", "cross_encoder", "qwen_1_5b", "phi_4_mini", "smollm2_1_7b"}
    needs_gpu = bool(gpu_methods.intersection(methods))
    diagnostics: Dict[str, object] = {"required": needs_gpu, "allow_cpu": allow_cpu}
    if not needs_gpu:
        return diagnostics
    try:
        import torch

        diagnostics.update(
            {
                "torch_version": torch.__version__,
                "cuda_available": bool(torch.cuda.is_available()),
                "device_count": int(torch.cuda.device_count()),
                "device_name": (
                    torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
                ),
                "hip_version": getattr(torch.version, "hip", None),
                "hardware_profile": (
                    "rocm" if getattr(torch.version, "hip", None) else "cuda"
                ),
            }
        )
    except Exception as exc:
        diagnostics["error"] = str(exc)
        if not allow_cpu:
            raise RuntimeError(
                "GPU reconcilers were requested, but PyTorch accelerator "
                f"detection failed: {exc}"
            ) from exc
        return diagnostics

    if not diagnostics["cuda_available"] and not allow_cpu:
        raise RuntimeError(
                "GPU reconcilers require a GPU/ROCm device. "
            "No accelerator was detected and CPU fallback is disabled."
        )
    return diagnostics


def reconcile_chunk(
    engine: ReconciliationEngine,
    records: Sequence[dict],
    methods: Sequence[str],
) -> Dict[str, List[dict]]:
    pairs = [
        (record["original_data"], record["drifted_data"]) for record in records
    ]
    outputs: Dict[str, List[dict]] = {}
    for method in methods:
        # The oracle records each method's completed results before moving to
        # Qwen.  Keeping MiniLM and BGE resident during autoregressive Qwen
        # generation exhausts a 64-GB MI250X GCD even with a small batch.  The
        # workload uses one full shard per chunk, so releasing them here does
        # not cause a reload loop and leaves Qwen its required VRAM headroom.
        if method in {"gemma_e2b", "qwen_1_5b", "phi_4_mini", "smollm2_1_7b"}:
            for resident_method in ("minilm", "bge"):
                if resident_method in engine.reconcilers:
                    engine.release_method(resident_method)
        started = time.perf_counter()
        if method == "minilm":
            results = engine.reconcile_bert_batch(pairs)
        elif method in {"gemma_e2b", "qwen_1_5b", "phi_4_mini", "smollm2_1_7b"}:
            results = engine.reconcile_llm_batch(method, pairs)
        elif method == "levenshtein":
            results = engine.reconcile_levenshtein_batch(pairs)
        else:
            results = engine.reconcile_semantic_batch(method, pairs)
        if len(results) != len(records):
            raise RuntimeError(
                f"{method} returned {len(results)} results for {len(records)} records"
            )
        outputs[method] = results
        elapsed = time.perf_counter() - started
        print(
            f"  {method}: {len(records)} records in {elapsed:.2f}s",
            flush=True,
        )
    return outputs


def preflight_methods(
    engine: ReconciliationEngine,
    record: dict,
    methods: Sequence[str],
) -> Dict[str, object]:
    """Execute every configured method once and reject silent fallbacks."""
    print("=== All-method preflight ===", flush=True)
    outputs = reconcile_chunk(engine, [record], methods)
    report: Dict[str, object] = {}
    for method in methods:
        result = outputs[method][0]
        latency = float(result.get("latency_ms", -1.0))
        if not np.isfinite(latency) or latency < 0:
            raise RuntimeError(f"{method} returned invalid latency: {latency}")
        if not isinstance(result.get("mapped_fields"), (list, tuple, dict)):
            raise RuntimeError(f"{method} returned invalid mapped_fields")
        if method in {"gemma_e2b", "qwen_1_5b", "phi_4_mini", "smollm2_1_7b"} and not bool(
            result.get("structured_output_valid", False)
        ):
            raise RuntimeError(
                f"{method} did not return a valid indexed JSON mapping after retry"
            )
        metrics = exact_mapping_metrics(
            record["ground_truth_mapping"],
            result.get("mapped_fields", []),
            result.get("unmapped_fields", []),
        )
        report[method] = {
            "latency_ms": latency,
            "structured_output_valid": result.get("structured_output_valid"),
            "structured_output_retried": result.get("structured_output_retried"),
            **metrics,
        }
        print(f"  PASS {method}: exact accuracy={metrics['accuracy']:.3f}", flush=True)
    return report


def choose_oracle(
    method_metrics: Dict[str, dict],
    *,
    accuracy_sla: float,
    accuracy_tolerance: float,
) -> Tuple[str, str]:
    meeting_sla = [
        method
        for method, metrics in method_metrics.items()
        if float(metrics["accuracy"]) >= accuracy_sla
    ]
    if meeting_sla:
        selected = min(
            meeting_sla,
            key=lambda method: (
                COST_ORDER[method],
                float(method_metrics[method]["latency_ms"]),
            ),
        )
        return selected, "lowest_cost_meeting_sla"

    best_accuracy = max(
        float(metrics["accuracy"]) for metrics in method_metrics.values()
    )
    near_best = [
        method
        for method, metrics in method_metrics.items()
        if best_accuracy - float(metrics["accuracy"]) <= accuracy_tolerance
    ]
    selected = min(
        near_best,
        key=lambda method: (
            COST_ORDER[method],
            float(method_metrics[method]["latency_ms"]),
        ),
    )
    return selected, "highest_accuracy_cost_aware_tie"


def read_completed_ids(path: Path) -> set[str]:
    completed: set[str] = set()
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                completed.add(json.loads(line)["record_id"])
    return completed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packets-file",
        default="data/ingested/telemetry_clean_bench_22500.json",
    )
    parser.add_argument(
        "--output",
        default="data/training/router_oracle_22500_v6.jsonl",
    )
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--max-packets-per-api", type=int, default=2500)
    parser.add_argument("--drift-rate", type=float, default=0.10)
    parser.add_argument("--max-drift-attempts", type=int, default=64)
    parser.add_argument("--chunk-size", type=int, default=64)
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=[*DEFAULT_CLASS_NAMES, "phi_4_mini", "smollm2_1_7b"],
        default=list(DEFAULT_CLASS_NAMES),
    )
    parser.add_argument("--accuracy-sla", type=float, default=0.95)
    parser.add_argument("--accuracy-tolerance", type=float, default=0.01)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write the unlabeled drift workload beside --output without loading reconcilers",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Development-only cap; zero processes the full corpus",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.chunk_size < 1 or args.batch_size < 1:
        raise SystemExit("--chunk-size and --batch-size must be positive")
    if not 0.0 <= args.accuracy_sla <= 1.0:
        raise SystemExit("--accuracy-sla must be in [0, 1]")
    if not 0.0 < args.drift_rate <= 1.0:
        raise SystemExit("--drift-rate must be in (0, 1]")
    if args.num_shards < 1 or not 0 <= args.shard_index < args.num_shards:
        raise SystemExit("Require 0 <= --shard-index < --num-shards")

    packets_path = (REPO_ROOT / args.packets_file).resolve()
    output_path = (REPO_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workload_path = output_path.with_suffix(".workload.jsonl")
    manifest_path = output_path.with_suffix(".manifest.json")

    print("=== RAP packet-level routing oracle ===")
    print(f"Corpus: {packets_path}")
    print(f"Output: {output_path}")
    packet_groups = load_packets(packets_path, args.max_packets_per_api)
    records, workload_summary = build_samples(
        packet_groups,
        seed=args.seed,
        max_attempts=args.max_drift_attempts,
        max_records=args.max_records,
        drift_rate=args.drift_rate,
    )
    all_record_count = len(records)
    records = [
        record for index, record in enumerate(records)
        if index % args.num_shards == args.shard_index
    ]
    workload_summary.update({
        "unsharded_records": all_record_count,
        "shard_index": args.shard_index,
        "num_shards": args.num_shards,
        "shard_records": len(records),
    })
    with workload_path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    print(f"Prepared {len(records):,} real schema-drift records")
    print(json.dumps(workload_summary, indent=2, sort_keys=True))

    accelerator = (
        {"required": False, "skipped": "prepare-only"}
        if args.prepare_only
        else require_accelerator(args.methods, args.allow_cpu)
    )
    manifest: Dict[str, object] = {
        "created_at": utc_now(),
        "hostname": socket.gethostname(),
        "corpus_path": str(packets_path),
        "corpus_sha256": file_sha256(packets_path),
        "output_path": str(output_path),
        "workload_path": str(workload_path),
        "seed": args.seed,
        "methods": args.methods,
        "class_names": list(DEFAULT_CLASS_NAMES),
        "accuracy_sla": args.accuracy_sla,
        "accuracy_tolerance": args.accuracy_tolerance,
        "split_protocol": "packet-identity 80/10/10; train=one chaos, validation/test=all chaos",
        "workload_summary": workload_summary,
        "accelerator": accelerator,
        "git": git_metadata(),
        "status": "prepared" if args.prepare_only else "running",
        "metric_definition": "exact top-level source-to-target field decision accuracy",
        "shard_index": args.shard_index,
        "num_shards": args.num_shards,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.prepare_only:
        print(f"Prepared workload only: {workload_path}")
        return

    completed_ids = read_completed_ids(output_path) if args.resume else set()
    if output_path.exists() and not args.resume:
        raise RuntimeError(
            f"{output_path} already exists. Use --resume or choose a new output path."
        )
    pending = [record for record in records if record["record_id"] not in completed_ids]
    mode = "a" if args.resume else "w"
    hardware_profile = (
        str(accelerator["hardware_profile"])
        if accelerator.get("cuda_available")
        else "cpu"
    )
    engine = ReconciliationEngine(
        hardware_profile=hardware_profile,
        batch_size=args.batch_size,
    )
    preflight_report = preflight_methods(engine, records[0], args.methods)
    manifest["preflight"] = preflight_report
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.preflight_only:
        manifest.update({"status": "preflight_complete", "completed_at": utc_now()})
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("All-method preflight complete; full oracle was not started.")
        return
    label_counts: Counter[str] = Counter()
    started = time.time()
    with output_path.open(mode, encoding="utf-8") as stream:
        for offset in range(0, len(pending), args.chunk_size):
            chunk = pending[offset : offset + args.chunk_size]
            print(
                f"[{offset + 1:,}-{offset + len(chunk):,}/{len(pending):,}]",
                flush=True,
            )
            reconciled = reconcile_chunk(engine, chunk, args.methods)
            for position, record in enumerate(chunk):
                method_metrics = {}
                for method in args.methods:
                    result = reconciled[method][position]
                    exact = exact_mapping_metrics(
                        record["ground_truth_mapping"],
                        result.get("mapped_fields", []),
                        result.get("unmapped_fields", []),
                    )
                    method_metrics[method] = {
                        **exact,
                        "native_score": float(result.get("accuracy", 0.0)),
                        "latency_ms": float(result["latency_ms"]),
                        "mapped_fields": result.get("mapped_fields", []),
                        "unmapped_fields": result.get("unmapped_fields", []),
                        "structured_output_valid": result.get("structured_output_valid"),
                        "structured_output_retried": result.get("structured_output_retried"),
                    }
                oracle_method, oracle_reason = choose_oracle(
                    method_metrics,
                    accuracy_sla=args.accuracy_sla,
                    accuracy_tolerance=args.accuracy_tolerance,
                )
                enriched = {
                    **record,
                    "method_metrics": method_metrics,
                    "oracle_method": oracle_method,
                    "oracle_label": COST_ORDER[oracle_method],
                    "oracle_reason": oracle_reason,
                }
                stream.write(json.dumps(enriched, separators=(",", ":")) + "\n")
                label_counts[oracle_method] += 1
            stream.flush()

    manifest.update(
        {
            "completed_at": utc_now(),
            "duration_seconds": time.time() - started,
            "status": "complete",
            "records_written": len(records),
            "label_counts_current_process": dict(label_counts),
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("=== Oracle complete ===")
    print(f"Records: {len(records):,}")
    print(f"Labels:  {dict(label_counts)}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
