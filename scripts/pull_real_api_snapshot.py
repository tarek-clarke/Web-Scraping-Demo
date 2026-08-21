#!/usr/bin/env python3
"""Pull and freeze 2,500 distinct records from each v9 benchmark API.

The output is immutable by default. Every source must return exactly the
requested number of distinct record identifiers *and* payload hashes; partial,
mocked, padded, or repeated data causes a non-zero exit.

The snapshot is a controlled historical/API replay. APIs are never contacted
during hardware benchmarking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO_ROOT))

from src.benchmark_protocol import (
    ACTIVE_API_SOURCES,
    DEFAULT_SNAPSHOT_PATH,
    PACKETS_PER_SOURCE,
    SNAPSHOT_SCHEMA_VERSION,
)

USER_AGENT = "Resilient-RAP-research-snapshot/1.0 (contact: repository owner)"


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


def fetch_json(url: str, *, timeout: int = 120, attempts: int = 5) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 == attempts:
                raise RuntimeError(f"API request failed after {attempts} attempts: {url}: {exc}") from exc
            time.sleep(min(30, 2 ** attempt))
    raise AssertionError("unreachable")


def packet(source: str, record_id: object, data: object, timestamp: object = None) -> dict:
    return {
        "source": source,
        "source_record_id": str(record_id),
        "timestamp": None if timestamp is None else str(timestamp),
        "data": data,
    }


def pull_openf1(target: int) -> list[dict]:
    # A fixed historical race session prevents `latest` from moving between pulls.
    rows = fetch_json("https://api.openf1.org/v1/car_data?session_key=9159")
    if not isinstance(rows, list):
        raise RuntimeError("OpenF1 returned a non-list payload")
    return [packet("openf1", f"{r.get('session_key')}:{r.get('driver_number')}:{r.get('date')}", r, r.get("date")) for r in rows[:target]]


def pull_binance(target: int) -> list[dict]:
    output, start_ms = [], 1704067200000  # 2024-01-01T00:00:00Z
    while len(output) < target:
        limit = min(1000, target - len(output))
        query = urllib.parse.urlencode({"symbol": "BTCUSDT", "interval": "1m", "limit": limit, "startTime": start_ms})
        rows = fetch_json(f"https://api.binance.com/api/v3/klines?{query}")
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            data = {
                "open_time_ms": row[0], "open": row[1], "high": row[2], "low": row[3],
                "close": row[4], "volume": row[5], "close_time_ms": row[6],
                "quote_volume": row[7], "trade_count": row[8],
                "taker_buy_base": row[9], "taker_buy_quote": row[10],
            }
            output.append(packet("binance_market", row[0], data, datetime.fromtimestamp(row[0] / 1000, timezone.utc).isoformat()))
        start_ms = int(rows[-1][0]) + 60_000
    return output[:target]


def pull_noaa_space_weather(target: int) -> list[dict]:
    rows = fetch_json("https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind.json")
    if not isinstance(rows, list) or len(rows) < 2:
        raise RuntimeError("NOAA SWPC returned an invalid plasma feed")
    fields = [str(field) for field in rows[0]]
    output = []
    for values in rows[1:]:
        data = dict(zip(fields, values))
        timestamp = data.get("time_tag")
        output.append(packet("noaa_space_weather", timestamp, data, timestamp))
        if len(output) >= target:
            break
    return output


def pull_openmeteo(target: int) -> list[dict]:
    query = urllib.parse.urlencode({
        "latitude": 59.437, "longitude": 24.7536,
        "start_date": "2024-01-01", "end_date": "2024-05-31",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure",
        "timezone": "UTC",
    })
    body = fetch_json(f"https://archive-api.open-meteo.com/v1/archive?{query}")
    hourly = body.get("hourly", {}) if isinstance(body, dict) else {}
    times = hourly.get("time", [])
    fields = [key for key in hourly if key != "time"]
    rows = []
    for index, timestamp in enumerate(times[:target]):
        data = {"time": timestamp, **{field: hourly[field][index] for field in fields}}
        rows.append(packet("openmeteo_weather", timestamp, data, timestamp))
    return rows


def pull_openfda(target: int) -> list[dict]:
    output, skip, seen_ids, seen_payloads = [], 0, set(), set()
    api_key = os.environ.get("OPENFDA_API_KEY", "")
    while len(output) < target:
        limit = 100
        params = {"limit": limit, "skip": skip, "sort": "receivedate:asc"}
        if api_key:
            params["api_key"] = api_key
        body = fetch_json("https://api.fda.gov/drug/event.json?" + urllib.parse.urlencode(params))
        rows = body.get("results", []) if isinstance(body, dict) else []
        if not rows:
            break
        for record in rows:
            record_id = str(record.get("safetyreportid"))
            payload_hash = digest(record)
            if record_id in seen_ids or payload_hash in seen_payloads:
                continue
            seen_ids.add(record_id)
            seen_payloads.add(payload_hash)
            output.append(packet("openfda_adverse_events", record_id, record, record.get("receivedate")))
            if len(output) >= target:
                break
        skip += len(rows)
    return output[:target]


def pull_nhl(target: int) -> list[dict]:
    schedule = fetch_json("https://api-web.nhle.com/v1/club-schedule-season/TOR/20242025")
    games = schedule.get("games", []) if isinstance(schedule, dict) else []
    output, seen_ids, seen_payloads = [], set(), set()
    for game in games:
        game_id = game.get("id")
        if not game_id:
            continue
        body = fetch_json(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play")
        for play in body.get("plays", []):
            play_id = play.get("eventId") or play.get("sortOrder")
            record_id = f"{game_id}:{play_id}"
            payload_hash = digest(play)
            if record_id in seen_ids or payload_hash in seen_payloads:
                continue
            seen_ids.add(record_id)
            seen_payloads.add(payload_hash)
            output.append(packet("hockey_nhl", record_id, play, body.get("startTimeUTC")))
            if len(output) >= target:
                return output
    return output


def pull_opensky(target: int) -> list[dict]:
    body = fetch_json("https://opensky-network.org/api/states/all")
    fields = (
        "icao24", "callsign", "origin_country", "time_position", "last_contact",
        "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
        "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk",
        "spi", "position_source", "category",
    )
    output = []
    for row in body.get("states", []) if isinstance(body, dict) else []:
        data = dict(zip(fields, row))
        output.append(packet("aviation_opensky", f"{data.get('icao24')}:{data.get('last_contact')}", data, data.get("last_contact")))
        if len(output) >= target:
            break
    return output


def pull_openligadb(target: int) -> list[dict]:
    output = []
    for season in range(2015, 2026):
        rows = fetch_json(f"https://api.openligadb.de/getmatchdata/bl1/{season}")
        if not isinstance(rows, list):
            continue
        for row in rows:
            output.append(packet("football_openligadb", row.get("matchID"), row, row.get("matchDateTimeUTC")))
            if len(output) >= target:
                return output
    return output


def pull_mbta(target: int) -> list[dict]:
    # The schedules endpoint requires a route/stop/trip filter. The stops
    # endpoint provides a large, stable set of distinct real transit records.
    output, offset = [], 0
    while len(output) < target:
        params = {
            "page[limit]": min(1000, target - len(output)),
            "page[offset]": offset,
        }
        body = fetch_json("https://api-v3.mbta.com/stops?" + urllib.parse.urlencode(params))
        rows = body.get("data", []) if isinstance(body, dict) else []
        if not rows:
            break
        output.extend(packet("smartcity_mbta", r.get("id"), r, r.get("attributes", {}).get("departure_time")) for r in rows)
        offset += len(rows)
    return output[:target]


PULLERS: dict[str, Callable[[int], list[dict]]] = {
    "openf1": pull_openf1,
    "binance_market": pull_binance,
    "noaa_space_weather": pull_noaa_space_weather,
    "openmeteo_weather": pull_openmeteo,
    "openfda_adverse_events": pull_openfda,
    "hockey_nhl": pull_nhl,
    "aviation_opensky": pull_opensky,
    "football_openligadb": pull_openligadb,
    "smartcity_mbta": pull_mbta,
}

SOURCE_PROVENANCE = {
    "openf1": "https://api.openf1.org/v1/car_data?session_key=9159",
    "binance_market": "https://api.binance.com/api/v3/klines (BTCUSDT, 1m, fixed start)",
    "noaa_space_weather": "https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind.json",
    "openmeteo_weather": "https://archive-api.open-meteo.com/v1/archive (Tallinn, fixed 2024 interval)",
    "openfda_adverse_events": "https://api.fda.gov/drug/event.json (receivedate ascending)",
    "hockey_nhl": "https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play",
    "aviation_opensky": "https://opensky-network.org/api/states/all",
    "football_openligadb": "https://api.openligadb.de/getmatchdata/bl1/{season}",
    "smartcity_mbta": "https://api-v3.mbta.com/stops",
}


def validate_source(source: str, rows: Iterable[dict], target: int) -> list[dict]:
    rows = list(rows)
    ids = [row.get("source_record_id") for row in rows]
    hashes = [digest(row.get("data")) for row in rows]
    if len(rows) != target:
        raise RuntimeError(f"{source}: expected {target:,} records, received {len(rows):,}")
    if None in ids or "None" in ids or len(set(ids)) != target:
        raise RuntimeError(f"{source}: source IDs are missing or duplicated ({len(set(ids)):,}/{target:,})")
    if len(set(hashes)) != target:
        raise RuntimeError(f"{source}: payloads are duplicated ({len(set(hashes)):,}/{target:,})")
    return sorted(rows, key=lambda row: row["source_record_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--packets-per-source", type=int, default=PACKETS_PER_SOURCE)
    parser.add_argument("--sources", nargs="+", choices=ACTIVE_API_SOURCES, default=list(ACTIVE_API_SOURCES))
    parser.add_argument("--source-cache-dir", default="data/ingested/source_cache_v1")
    parser.add_argument("--refresh-source-cache", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.packets_per_source < 1:
        raise SystemExit("--packets-per-source must be positive")
    output = (REPO_ROOT / args.output).resolve()
    manifest_path = output.with_suffix(".manifest.json")
    if output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite immutable snapshot: {output}")
    if set(args.sources) != set(ACTIVE_API_SOURCES) and args.packets_per_source == PACKETS_PER_SOURCE:
        print("WARNING: partial source pull is a development artifact, not the publication corpus", file=sys.stderr)

    cache_dir = (REPO_ROOT / args.source_cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    all_rows, source_summary = [], {}
    for source in args.sources:
        cache_path = cache_dir / f"{source}_{args.packets_per_source}.json"
        if cache_path.exists() and not args.refresh_source_cache:
            print(f"[{source}] validating cached source file", flush=True)
            rows = validate_source(source, json.loads(cache_path.read_text(encoding="utf-8")), args.packets_per_source)
        else:
            print(f"[{source}] pulling {args.packets_per_source:,} distinct records", flush=True)
            rows = validate_source(source, PULLERS[source](args.packets_per_source), args.packets_per_source)
            cache_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        all_rows.extend(rows)
        source_summary[source] = {
            "records": len(rows), "first_id": rows[0]["source_record_id"],
            "last_id": rows[-1]["source_record_id"], "payload_set_sha256": digest([digest(r["data"]) for r in rows]),
            "source_cache": str(cache_path.relative_to(REPO_ROOT)),
            "api_endpoint": SOURCE_PROVENANCE[source],
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(all_rows, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, output)
    manifest = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": "Immutable real-API snapshot for deterministic replay; no mock, padding, or duplicate payloads",
        "publication_ready": set(args.sources) == set(ACTIVE_API_SOURCES) and args.packets_per_source == PACKETS_PER_SOURCE,
        "source_order": list(args.sources), "packets_per_source": args.packets_per_source,
        "total_packets": len(all_rows), "snapshot_sha256": hashlib.sha256(encoded).hexdigest(),
        "sources": source_summary,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
