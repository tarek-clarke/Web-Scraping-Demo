#!/usr/bin/env python3
"""Build the v9 frozen stream from the real snapshot and frozen Qwen chaos.

This creates the common 22,500-event workload without running a reconciler or
calling an API. The Qwen transformations are read from the immutable artifact
generated once on LUMI-G; the other two chaos families are deterministic local
transformations using the same seed contract as the routing oracle.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.benchmark_protocol import ACTIVE_API_SOURCES, DEFAULT_SNAPSHOT_PATH
from src.chaos.json_chaos import JSONChaos
from src.chaos.schema_chaos import SchemaChaos
from src.routing.schema_fast_path import schemas_match
from src.reconciliation.mapping_metrics import derive_ground_truth_mapping


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def stable_seed(*parts: object) -> int:
    return int(hashlib.sha256(":".join(map(str, parts)).encode("utf-8")).hexdigest()[:8], 16)


def load_json_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Empty snapshot: {path}")
    rows = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError(f"Snapshot is not a list of objects: {path}")
    return rows


def load_qwen(path: Path) -> dict[tuple[str, int], dict]:
    result: dict[tuple[str, int], dict] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row["source"]), int(row["packet_index"]))
            if key in result:
                raise RuntimeError(f"Duplicate Qwen artifact key at line {line_number}: {key}")
            result[key] = row
    if not result:
        raise RuntimeError(f"Frozen Qwen artifact is empty: {path}")
    return result


def inject_rule(data: dict, method: str, seed: int) -> tuple[str, dict]:
    random.seed(seed)
    if method == "json_manip":
        subtype, drifted = JSONChaos().inject_with_subtype(copy.deepcopy(data))
    elif method == "schema_alter":
        subtype, drifted = SchemaChaos().alter_with_subtype(copy.deepcopy(data))
    else:
        raise ValueError(f"Unsupported rule chaos method: {method}")
    if schemas_match(data, drifted):
        raise RuntimeError(f"{method} did not create structural drift")
    return subtype, drifted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--qwen-chaos", default="data/training/qwen_model_chaos_22500_v1.jsonl")
    parser.add_argument("--output", default="data/replay/telemetry_frozen_22500_v9.jsonl")
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--drift-rate", type=float, default=0.10)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 0.0 < args.drift_rate <= 1.0:
        raise SystemExit("--drift-rate must be in (0, 1]")

    packets_path = (REPO_ROOT / args.packets).resolve()
    qwen_path = (REPO_ROOT / args.qwen_chaos).resolve()
    output_path = (REPO_ROOT / args.output).resolve()
    manifest_path = output_path.with_suffix(".manifest.json")
    if not packets_path.is_file():
        raise SystemExit(f"Missing real API snapshot: {packets_path}")
    if not qwen_path.is_file():
        raise SystemExit(f"Missing frozen Qwen chaos; run generate_qwen_chaos_v9.slurm first: {qwen_path}")
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite frozen replay: {output_path}")

    packets = load_json_rows(packets_path)
    groups: dict[str, list[dict]] = defaultdict(list)
    for packet in packets:
        groups[str(packet["source"])].append(packet)
    counts = {source: len(groups[source]) for source in ACTIVE_API_SOURCES}
    if len(packets) != 22500 or any(count != 2500 for count in counts.values()):
        raise RuntimeError(f"v9 requires 22,500 packets and 2,500 per source; found {len(packets)} / {counts}")
    qwen = load_qwen(qwen_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    workload_hash = hashlib.sha256()
    counts_out = Counter()
    chaos_counts = Counter()
    expected_qwen_keys: set[tuple[str, int]] = set()
    try:
        with temporary.open("w", encoding="utf-8") as target:
            sequence_id = 0
            for source in ACTIVE_API_SOURCES:
                packets_for_source = groups[source]
                drift_count = round(len(packets_for_source) * args.drift_rate)
                selected = set(sorted(
                    range(len(packets_for_source)),
                    key=lambda index: stable_seed(args.seed, source, index, "drift-selection"),
                )[:drift_count])
                for packet_index, packet in enumerate(packets_for_source):
                    canonical = packet.get("data")
                    if not isinstance(canonical, dict) or not canonical:
                        raise RuntimeError(f"{source}[{packet_index}] has no non-empty object payload")
                    if packet_index not in selected:
                        payload = canonical
                        event = {
                            "sequence_id": sequence_id,
                            "record_id": f"clean_{source}_{packet_index}",
                            "source": source,
                            "source_packet_index": packet_index,
                            "event_timestamp": packet.get("timestamp"),
                            "split": "clean",
                            "is_drifted": False,
                            "chaos_method": "none",
                            "chaos_subtype": "none",
                            "canonical_data": canonical,
                            "payload": payload,
                            "ground_truth_mapping": {str(field): str(field) for field in canonical},
                        }
                        counts_out["clean"] += 1
                    else:
                        method = ("qwen", "json_manip", "schema_alter")[stable_seed(args.seed, source, packet_index, "method") % 3]
                        drift_seed = stable_seed(args.seed, source, packet_index, method)
                        if method == "qwen":
                            key = (source, packet_index)
                            frozen = qwen.get(key)
                            if frozen is None:
                                raise RuntimeError(f"Missing frozen Qwen record for {key}")
                            if frozen.get("original_sha256") != digest(canonical):
                                raise RuntimeError(f"Frozen Qwen source mismatch for {key}")
                            payload = frozen["drifted_data"]
                            subtype = "qwen_model_semantic_key_rename"
                            expected_qwen_keys.add(key)
                        else:
                            subtype, payload = inject_rule(canonical, method, drift_seed)
                        record_id = hashlib.sha256(f"{source}:{packet_index}:{method}:{drift_seed}".encode("utf-8")).hexdigest()[:24]
                        event = {
                            "sequence_id": sequence_id,
                            "record_id": record_id,
                            "source": source,
                            "source_packet_index": packet_index,
                            "event_timestamp": packet.get("timestamp"),
                            "split": "drifted",
                            "is_drifted": True,
                            "chaos_method": method,
                            "chaos_subtype": subtype,
                            "chaos_seed": drift_seed,
                            "canonical_data": canonical,
                            "payload": payload,
                            "ground_truth_mapping": derive_ground_truth_mapping(canonical, payload),
                        }
                        counts_out["drifted"] += 1
                        chaos_counts[method] += 1
                    event["canonical_sha256"] = digest(event["canonical_data"])
                    event["payload_sha256"] = digest(event["payload"])
                    encoded = (stable_json(event) + "\n").encode("utf-8")
                    target.write(encoded.decode("utf-8"))
                    workload_hash.update(encoded)
                    sequence_id += 1
        expected_qwen = {
            (source, packet_index)
            for source in ACTIVE_API_SOURCES
            for packet_index in sorted(
                range(2500),
                key=lambda index: stable_seed(args.seed, source, index, "drift-selection"),
            )[:round(2500 * args.drift_rate)]
            if ("qwen", "json_manip", "schema_alter")[stable_seed(args.seed, source, packet_index, "method") % 3] == "qwen"
        }
        if expected_qwen_keys != expected_qwen:
            raise RuntimeError(f"Qwen artifact coverage mismatch: expected {len(expected_qwen)}, used {len(expected_qwen_keys)}")
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Deterministic v9 historical replay from real API snapshot and frozen Qwen chaos",
        "packets_path": str(packets_path),
        "packets_sha256": hashlib.sha256(packets_path.read_bytes()).hexdigest(),
        "qwen_chaos_path": str(qwen_path),
        "qwen_chaos_sha256": hashlib.sha256(qwen_path.read_bytes()).hexdigest(),
        "workload_path": str(output_path),
        "workload_sha256": workload_hash.hexdigest(),
        "seed": args.seed,
        "drift_rate": args.drift_rate,
        "counts": dict(counts_out),
        "chaos_counts": dict(sorted(chaos_counts.items())),
        "not_live_capture": True,
        "publication_ready": counts_out["clean"] + counts_out["drifted"] == 22500 and counts_out["drifted"] == 2250,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
