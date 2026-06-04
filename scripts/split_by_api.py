#!/usr/bin/env python3
import json
import os
from collections import defaultdict

INPUT_FILE = "data/ingested/telemetry_latest.json"
OUTPUT_DIR = "data/ingested"

def split_by_api():
    with open(INPUT_FILE, 'r') as f:
        packets = json.load(f)

    by_api = defaultdict(list)
    for p in packets:
        by_api[p["source"]].append(p)

    print(f"Total packets: {len(packets)}")
    for api, ps in by_api.items():
        print(f"  {api}: {len(ps)}")

    targets = {
        "openf1": 2500,
        "finnhub": 2500,
        "spacex": 2500,
        "openmeteo": 2500
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for api, target_count in targets.items():
        if api in by_api and by_api[api]:
            count = min(target_count, len(by_api[api]))
            selected = by_api[api][:count]
            out_file = os.path.join(OUTPUT_DIR, f"{api}_telemetry.json")
            with open(out_file, 'w') as f:
                json.dump(selected, f, indent=2)
            print(f"Saved {count} packets to {out_file}")
        else:
            print(f"Warning: no data for {api}")

    print("\nDone. Files saved:")
    for api in targets:
        f = os.path.join(OUTPUT_DIR, f"{api}_telemetry.json")
        if os.path.exists(f):
            print(f"  {f}")

if __name__ == "__main__":
    split_by_api()