#!/usr/bin/env python3
"""Validate and merge independently generated router-oracle shards."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.benchmark_protocol import ACTIVE_API_SOURCES


API_ORDER = {name: index for index, name in enumerate(ACTIVE_API_SOURCES)}
CHAOS_ORDER = {name: index for index, name in enumerate(("qwen", "json_manip", "schema_alter"))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--shards", nargs="+", required=True)
    parser.add_argument("--expected-records", type=int, default=31500)
    args = parser.parse_args()

    output = Path(args.output)
    rows, seen, manifests = [], set(), []
    for raw_path in args.shards:
        path = Path(raw_path)
        manifest_path = path.with_suffix(".manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            raise RuntimeError(f"Incomplete shard manifest: {manifest_path}")
        manifests.append(manifest)
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                record_id = row["record_id"]
                if record_id in seen:
                    raise RuntimeError(f"Duplicate record across shards: {record_id}")
                seen.add(record_id)
                rows.append(row)
    if len(rows) != args.expected_records:
        raise RuntimeError(
            f"Expected {args.expected_records:,} records, found {len(rows):,}; refusing partial merge"
        )
    rows.sort(key=lambda row: (
        API_ORDER[row["api"]], int(row["packet_index"]), CHAOS_ORDER[row["chaos_method"]]
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")

    base = dict(manifests[0])
    base.update({
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "output_path": str(output.resolve()),
        "records_written": len(rows),
        "num_shards": len(args.shards),
        "shard_paths": [str(Path(path).resolve()) for path in args.shards],
        "label_counts": dict(Counter(row["oracle_method"] for row in rows)),
        "preflight": {str(index): manifest.get("preflight", {}) for index, manifest in enumerate(manifests)},
    })
    output.with_suffix(".manifest.json").write_text(
        json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Merged {len(rows):,} unique records from {len(args.shards)} shards into {output}")


if __name__ == "__main__":
    main()
