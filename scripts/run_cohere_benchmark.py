#!/usr/bin/env python3
"""
run_cohere_benchmark.py

Benchmark Cohere-based reconciliation over the 22,500-packet corpus with
granular timing, token, billing, and host-observed metrics.

The script keeps the repository's "clean packets bypass the heavy path"
assumption: only packets selected for drift undergo Cohere reconciliation.
All packets are still processed and logged so the full corpus remains
comparable across backends.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.chaos.json_chaos import JSONChaos
from src.chaos.qwen_chaos import QwenChaos
from src.chaos.schema_chaos import SchemaChaos

try:
    from src.telemetry.metrics_logger import EnergyTracker
except Exception:  # pragma: no cover - optional dependency path
    EnergyTracker = None


ACTIVE_APIS = [
    "openf1",
    "finnhub",
    "spacex",
    "openweather",
    "clinical",
    "hockey_nhl",
    "aviation_opensky",
    "football_uefa",
    "smartcity_transit",
]

DEFAULT_METHODS = ["qwen", "json_manip", "schema_alter"]
COHERE_CHAT_URL = "https://api.cohere.com/v2/chat"


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sorted_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _extract_json_text(raw: str) -> Optional[str]:
    if not raw:
        return None
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
    if candidate.startswith("{") and candidate.endswith("}"):
        return candidate

    first = candidate.find("{")
    last = candidate.rfind("}")
    if first >= 0 and last > first:
        return candidate[first:last + 1]
    return None


def _coerce_json_object(raw: str) -> Optional[Dict[str, Any]]:
    text = _extract_json_text(raw)
    if not text:
        return None
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _packet_seed(seed: int, packet_idx: int, api: str, method: str, repetition: int) -> int:
    payload = f"{seed}:{packet_idx}:{api}:{method}:{repetition}"
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def _should_drift(seed: int, packet_idx: int, api: str, method: str, repetition: int, drift_rate: float) -> bool:
    digest = _packet_seed(seed, packet_idx, api, method, repetition)
    return (digest / float(0xFFFFFFFFFFFFFFFF)) < drift_rate


def _inject_drift(method: str, payload: Dict[str, Any], seed: int) -> Tuple[str, Dict[str, Any]]:
    prev_state = random.getstate()
    random.seed(seed)
    try:
        if method == "qwen":
            injector = QwenChaos()
            subtype, drifted = injector.inject_with_subtype(copy.deepcopy(payload))
            return subtype, drifted
        if method == "json_manip":
            injector = JSONChaos()
            subtype, drifted = injector.inject_with_subtype(copy.deepcopy(payload))
            return subtype, drifted
        if method == "schema_alter":
            injector = SchemaChaos()
            subtype, drifted = injector.alter_with_subtype(copy.deepcopy(payload))
            return subtype, drifted
        raise ValueError(f"Unknown chaos method: {method}")
    finally:
        random.setstate(prev_state)


def _load_corpus(path: Path, max_packets_per_api: int) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {api: [] for api in ACTIVE_APIS}
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            packet = json.loads(line)
            api = packet.get("source")
            if api not in groups:
                continue
            if len(groups[api]) >= max_packets_per_api:
                continue
            groups[api].append(packet)
            total += 1
    if total == 0:
        raise RuntimeError(f"No active API packets found in {path}")
    if max_packets_per_api >= 2500 and total != 22500:
        raise RuntimeError(f"Expected 22,500 active packets, loaded {total}")
    return groups


def _build_prompt(
    source: str,
    canonical_keys: List[str],
    drifted_payload: Dict[str, Any],
) -> List[Dict[str, str]]:
    schema_hint = {
        "source": source,
        "canonical_keys": canonical_keys,
    }
    system = (
        "You repair telemetry packets. Return strict JSON only, with the same top-level "
        "shape as the input when possible. Do not explain. Do not use markdown."
    )
    user = {
        "schema_hint": schema_hint,
        "drifted_packet": drifted_payload,
        "instructions": [
            "Reconstruct the canonical packet data for the listed source.",
            "Output JSON with a single 'data' object when the source packet has one.",
            "Do not add prose or code fences.",
        ],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, sort_keys=True, separators=(",", ":"))},
    ]


def _call_cohere_stream(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout_s: float,
    client_name: str,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.0,
    }

    req = urllib.request.Request(
        COHERE_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Client-Name": client_name,
        },
        method="POST",
    )

    response_text = ""
    response_id = ""
    finish_reason = ""
    usage: Dict[str, Any] = {}
    billed_units: Dict[str, Any] = {}
    first_token_at: Optional[float] = None
    delta_count = 0
    start = time.perf_counter()

    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except Exception:
                continue

            event_type = event.get("type")
            if event_type == "content-delta":
                delta = (
                    event.get("delta", {})
                    .get("message", {})
                    .get("content", {})
                    .get("text", "")
                )
                if delta:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    response_text += delta
                    delta_count += 1
            elif event_type == "stream-end":
                finish_reason = str(event.get("finish_reason", ""))
                response = event.get("response", {}) or {}
                response_id = str(response.get("id", ""))
                usage = response.get("usage", {}) or response.get("meta", {}) or {}
                billed_units = usage.get("billed_units", {}) if isinstance(usage, dict) else {}
                if "message" in response:
                    content = response.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        response_text = "".join(
                            part.get("text", "") for part in content if isinstance(part, dict)
                        ) or response_text
                    elif isinstance(content, str):
                        response_text = content or response_text
                elif "text" in response and isinstance(response["text"], str):
                    response_text = response["text"] or response_text

    end = time.perf_counter()
    return {
        "response_text": response_text.strip(),
        "response_id": response_id,
        "finish_reason": finish_reason,
        "usage": usage if isinstance(usage, dict) else {},
        "billed_units": billed_units if isinstance(billed_units, dict) else {},
        "request_start_perf": start,
        "request_end_perf": end,
        "time_to_first_token_ms": ((first_token_at - start) * 1000.0) if first_token_at else None,
        "output_generation_ms": ((end - first_token_at) * 1000.0) if first_token_at else None,
        "round_trip_ms": (end - start) * 1000.0,
        "delta_count": delta_count,
    }


def _normalize_prediction(prediction: Dict[str, Any]) -> Dict[str, Any]:
    if "data" in prediction and isinstance(prediction["data"], dict):
        return prediction["data"]
    return prediction


def _compare_structures(expected: Dict[str, Any], predicted: Dict[str, Any]) -> bool:
    return _sorted_json(expected) == _sorted_json(predicted)


def _format_ms(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.3f}"


def _format_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Cohere reconciliation on the 22,500-packet corpus")
    parser.add_argument(
        "--packets-file",
        default="data/ingested/telemetry_clean_bench_22500.json",
        help="JSONL packet corpus to benchmark",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for benchmark outputs. Defaults to data/reports/cohere_<date>_run<run-number>",
    )
    parser.add_argument(
        "--run-number",
        type=int,
        default=1,
        help="Run number to embed in output filenames",
    )
    parser.add_argument(
        "--model",
        default="command-a-plus-05-2026",
        help="Cohere model name",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        default=DEFAULT_METHODS,
        choices=DEFAULT_METHODS,
        help="Chaos methods to benchmark",
    )
    parser.add_argument(
        "--drift-rate",
        type=float,
        default=0.10,
        help="Fraction of packets to drift for each method",
    )
    parser.add_argument(
        "--max-packets-per-api",
        type=int,
        default=2500,
        help="Maximum packets per API to load from the corpus",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="How many times to repeat the benchmark for each packet-method pair",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--fail-on-api-error",
        action="store_true",
        help="Abort immediately after recording the first failed Cohere API request",
    )
    parser.add_argument(
        "--client-name",
        default="resilient-rap-framework",
        help="X-Client-Name header value",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260723,
        help="Deterministic sampling seed",
    )
    parser.add_argument(
        "--limit-packets",
        type=int,
        default=0,
        help="Optional hard cap on packets processed per API after loading",
    )
    args = parser.parse_args()

    api_key = os.getenv("COHERE_API_KEY", "").strip()
    if not api_key:
        print("ERROR: COHERE_API_KEY is not set in this shell.")
        sys.exit(1)

    packets_path = Path(args.packets_file)
    if not packets_path.exists():
        print(f"ERROR: packets file not found: {packets_path}")
        sys.exit(1)

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = ROOT / "data" / "reports" / f"cohere_{datetime.now().strftime('%Y%m%d')}_run{args.run_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows_path = output_dir / f"cohere_benchmark_{run_stamp}_run{args.run_number}.csv"
    jsonl_path = output_dir / f"cohere_benchmark_{run_stamp}_run{args.run_number}.jsonl"
    summary_path = output_dir / f"cohere_benchmark_{run_stamp}_run{args.run_number}_summary.json"
    tex_path = output_dir / f"cohere_benchmark_{run_stamp}_run{args.run_number}_summary.tex"
    energy_path = output_dir / f"cohere_benchmark_{run_stamp}_run{args.run_number}_energy.csv"

    print("=== Cohere Benchmark ===")
    print(f"Packets file: {packets_path}")
    print(f"Output dir:   {output_dir}")
    print(f"Model:        {args.model}")
    print(f"Run number:    {args.run_number}")
    print(f"Drift rate:    {args.drift_rate:.2%}")
    print(f"Methods:       {', '.join(args.methods)}")
    print()

    groups = _load_corpus(packets_path, args.max_packets_per_api)
    if args.limit_packets and args.limit_packets > 0:
        for api in groups:
            groups[api] = groups[api][: args.limit_packets]

    total_packets = sum(len(v) for v in groups.values())
    print(f"[Load] Active packets loaded: {total_packets:,}")

    tracker = None
    if EnergyTracker is not None:
        try:
            tracker = EnergyTracker(output_path=str(energy_path))
            tracker.start()
            print(f"[Energy] Host metrics will be sampled to {energy_path}")
        except Exception as exc:
            print(f"[Energy] Tracker unavailable, continuing without host telemetry: {exc}")
            tracker = None

    summary_rows: List[Dict[str, Any]] = []
    by_method = defaultdict(lambda: {
        "packets": 0,
        "drifted": 0,
        "calls": 0,
        "correct": 0,
        "round_trip_ms": [],
        "time_to_first_token_ms": [],
        "output_generation_ms": [],
        "input_prep_ms": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "billed_input_tokens": 0,
        "billed_output_tokens": 0,
        "cpu_energy_j": 0.0,
        "gpu_energy_j": 0.0,
        "estimated_gco2e": 0.0,
    })

    per_api_method = defaultdict(lambda: {
        "packets": 0,
        "drifted": 0,
        "calls": 0,
        "correct": 0,
        "round_trip_ms": [],
        "time_to_first_token_ms": [],
        "output_generation_ms": [],
        "input_prep_ms": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "billed_input_tokens": 0,
        "billed_output_tokens": 0,
        "cpu_energy_j": 0.0,
        "gpu_energy_j": 0.0,
        "estimated_gco2e": 0.0,
    })

    total_drifted = 0
    total_calls = 0
    total_correct = 0

    try:
        with rows_path.open("w", newline="", encoding="utf-8") as csv_fh, jsonl_path.open("w", encoding="utf-8") as jsonl_fh:
            writer = csv.DictWriter(
                csv_fh,
                fieldnames=[
                    "run_stamp",
                    "run_number",
                    "packet_idx",
                    "api",
                    "repetition",
                    "chaos_method",
                    "is_drifted",
                    "drift_subtype",
                    "input_prep_ms",
                    "network_round_trip_ms",
                    "time_to_first_token_ms",
                    "output_generation_ms",
                    "response_chars",
                    "response_id",
                    "finish_reason",
                    "json_parse_ok",
                    "exact_match",
                    "input_tokens",
                    "output_tokens",
                    "billed_input_tokens",
                    "billed_output_tokens",
                    "host_elapsed_seconds",
                    "host_power_w",
                    "host_temperature_c",
                    "host_cpu_energy_j",
                    "host_gpu_energy_j",
                    "host_cumulative_kwh",
                    "host_estimated_gco2e",
                    "host_measurement_quality",
                    "error",
                    "prompt_hash",
                    "response_hash",
                ],
            )
            writer.writeheader()

            for repetition in range(args.repetitions):
                for api in ACTIVE_APIS:
                    packets = groups.get(api, [])
                    for packet_idx, packet in enumerate(packets):
                        canonical_data = packet.get("data", {})
                        for method in args.methods:
                            row_state = by_method[method]
                            api_state = per_api_method[(api, method)]
                            row_state["packets"] += 1
                            api_state["packets"] += 1

                            if not _should_drift(args.seed, packet_idx, api, method, repetition, args.drift_rate):
                                host = tracker.get_metrics() if tracker else {}
                                row = {
                                    "run_stamp": run_stamp,
                                    "run_number": args.run_number,
                                    "packet_idx": packet_idx,
                                    "api": api,
                                    "repetition": repetition,
                                    "chaos_method": method,
                                    "is_drifted": False,
                                    "drift_subtype": "",
                                    "input_prep_ms": 0.0,
                                    "network_round_trip_ms": 0.0,
                                    "time_to_first_token_ms": 0.0,
                                    "output_generation_ms": 0.0,
                                    "response_chars": 0,
                                    "response_id": "",
                                    "finish_reason": "FAST_PATH",
                                    "json_parse_ok": True,
                                    "exact_match": True,
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                    "billed_input_tokens": 0,
                                    "billed_output_tokens": 0,
                                    "host_elapsed_seconds": host.get("elapsed_seconds", 0.0),
                                    "host_power_w": host.get("power_draw_w", 0.0),
                                    "host_temperature_c": host.get("temperature_c", 0.0),
                                    "host_cpu_energy_j": host.get("cpu_energy_draw_joules", 0.0),
                                    "host_gpu_energy_j": host.get("gpu_energy_draw_joules", 0.0),
                                    "host_cumulative_kwh": host.get("cumulative_kwh", 0.0),
                                    "host_estimated_gco2e": host.get("estimated_gCO2e", 0.0),
                                    "host_measurement_quality": host.get("measurement_quality", "estimated"),
                                    "error": "",
                                    "prompt_hash": "",
                                    "response_hash": "",
                                }
                                writer.writerow(row)
                                jsonl_fh.write(json.dumps(row) + "\n")
                                continue

                            drift_seed = _packet_seed(args.seed, packet_idx, api, method, repetition)
                            drift_subtype, drifted_payload = _inject_drift(method, canonical_data, drift_seed)
                            total_drifted += 1
                            row_state["drifted"] += 1
                            api_state["drifted"] += 1

                            input_prep_start = time.perf_counter()
                            prompt = _build_prompt(api, list(canonical_data.keys()), drifted_payload)
                            prompt_blob = json.dumps(prompt, sort_keys=True, separators=(",", ":"))
                            prompt_hash = _stable_hash(prompt_blob)
                            input_prep_ms = (time.perf_counter() - input_prep_start) * 1000.0

                            error = ""
                            response_text = ""
                            response_id = ""
                            finish_reason = ""
                            json_parse_ok = False
                            exact_match = False
                            usage: Dict[str, Any] = {}
                            billed_units: Dict[str, Any] = {}
                            network_round_trip_ms = 0.0
                            time_to_first_token_ms = None
                            output_generation_ms = None
                            response_chars = 0

                            try:
                                result = _call_cohere_stream(
                                    api_key=api_key,
                                    model=args.model,
                                    messages=prompt,
                                    timeout_s=args.timeout,
                                    client_name=args.client_name,
                                )
                                response_text = result["response_text"]
                                response_id = result["response_id"]
                                finish_reason = result["finish_reason"]
                                usage = result["usage"] or {}
                                billed_units = result["billed_units"] or {}
                                network_round_trip_ms = result["round_trip_ms"]
                                time_to_first_token_ms = result["time_to_first_token_ms"]
                                output_generation_ms = result["output_generation_ms"]
                                response_chars = len(response_text)
                                row_state["calls"] += 1
                                api_state["calls"] += 1
                                total_calls += 1

                                prediction_obj = _coerce_json_object(response_text)
                                if prediction_obj is not None:
                                    json_parse_ok = True
                                    predicted_data = _normalize_prediction(prediction_obj)
                                    exact_match = _compare_structures(canonical_data, predicted_data)
                                    if exact_match:
                                        row_state["correct"] += 1
                                        api_state["correct"] += 1
                                        total_correct += 1
                            except urllib.error.HTTPError as exc:
                                error = f"HTTPError:{exc.code}"
                            except urllib.error.URLError as exc:
                                error = f"URLError:{exc.reason}"
                            except Exception as exc:
                                error = f"{type(exc).__name__}:{exc}"

                            host = tracker.get_metrics() if tracker else {}
                            row_state["round_trip_ms"].append(network_round_trip_ms)
                            api_state["round_trip_ms"].append(network_round_trip_ms)
                            if time_to_first_token_ms is not None:
                                row_state["time_to_first_token_ms"].append(time_to_first_token_ms)
                                api_state["time_to_first_token_ms"].append(time_to_first_token_ms)
                            if output_generation_ms is not None:
                                row_state["output_generation_ms"].append(output_generation_ms)
                                api_state["output_generation_ms"].append(output_generation_ms)
                            row_state["input_prep_ms"].append(input_prep_ms)
                            api_state["input_prep_ms"].append(input_prep_ms)

                            input_tokens = int((usage.get("tokens") or {}).get("input_tokens", 0) or 0)
                            output_tokens = int((usage.get("tokens") or {}).get("output_tokens", 0) or 0)
                            billed_input_tokens = int((billed_units.get("input_tokens", 0) or 0))
                            billed_output_tokens = int((billed_units.get("output_tokens", 0) or 0))

                            row_state["input_tokens"] += input_tokens
                            row_state["output_tokens"] += output_tokens
                            row_state["billed_input_tokens"] += billed_input_tokens
                            row_state["billed_output_tokens"] += billed_output_tokens
                            api_state["input_tokens"] += input_tokens
                            api_state["output_tokens"] += output_tokens
                            api_state["billed_input_tokens"] += billed_input_tokens
                            api_state["billed_output_tokens"] += billed_output_tokens

                            row_state["cpu_energy_j"] += float(host.get("cpu_energy_draw_joules", 0.0) or 0.0)
                            row_state["gpu_energy_j"] += float(host.get("gpu_energy_draw_joules", 0.0) or 0.0)
                            row_state["estimated_gco2e"] += float(host.get("estimated_gCO2e", 0.0) or 0.0)
                            api_state["cpu_energy_j"] += float(host.get("cpu_energy_draw_joules", 0.0) or 0.0)
                            api_state["gpu_energy_j"] += float(host.get("gpu_energy_draw_joules", 0.0) or 0.0)
                            api_state["estimated_gco2e"] += float(host.get("estimated_gCO2e", 0.0) or 0.0)

                            row = {
                                "run_stamp": run_stamp,
                                "run_number": args.run_number,
                                "packet_idx": packet_idx,
                                "api": api,
                                "repetition": repetition,
                                "chaos_method": method,
                                "is_drifted": True,
                                "drift_subtype": drift_subtype,
                                "input_prep_ms": input_prep_ms,
                                "network_round_trip_ms": network_round_trip_ms,
                                "time_to_first_token_ms": time_to_first_token_ms or 0.0,
                                "output_generation_ms": output_generation_ms or 0.0,
                                "response_chars": response_chars,
                                "response_id": response_id,
                                "finish_reason": finish_reason,
                                "json_parse_ok": json_parse_ok,
                                "exact_match": exact_match,
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "billed_input_tokens": billed_input_tokens,
                                "billed_output_tokens": billed_output_tokens,
                                "host_elapsed_seconds": host.get("elapsed_seconds", 0.0),
                                "host_power_w": host.get("power_draw_w", 0.0),
                                "host_temperature_c": host.get("temperature_c", 0.0),
                                "host_cpu_energy_j": host.get("cpu_energy_draw_joules", 0.0),
                                "host_gpu_energy_j": host.get("gpu_energy_draw_joules", 0.0),
                                "host_cumulative_kwh": host.get("cumulative_kwh", 0.0),
                                "host_estimated_gco2e": host.get("estimated_gCO2e", 0.0),
                                "host_measurement_quality": host.get("measurement_quality", ""),
                                "error": error,
                                "prompt_hash": prompt_hash,
                                "response_hash": _stable_hash(response_text) if response_text else "",
                            }
                            writer.writerow(row)
                            jsonl_fh.write(json.dumps(row) + "\n")
                            csv_fh.flush()
                            jsonl_fh.flush()

                            if error and args.fail_on_api_error:
                                raise RuntimeError(
                                    f"Cohere API request failed for {api}/{method}: {error}. "
                                    f"See {rows_path} for the recorded failure."
                                )

    finally:
        if tracker is not None:
            try:
                tracker.stop()
            except Exception:
                pass

    def _avg(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _std(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = _avg(values)
        return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5

    for method in args.methods:
        stats = by_method[method]
        summary_rows.append({
            "scope": "method",
            "api": "all",
            "chaos_method": method,
            "packets": stats["packets"],
            "drifted_packets": stats["drifted"],
            "cohere_calls": stats["calls"],
            "exact_match": stats["correct"],
            "accuracy": (stats["correct"] / stats["calls"]) if stats["calls"] else 0.0,
            "mean_round_trip_ms": _avg(stats["round_trip_ms"]),
            "std_round_trip_ms": _std(stats["round_trip_ms"]),
            "mean_time_to_first_token_ms": _avg(stats["time_to_first_token_ms"]),
            "mean_output_generation_ms": _avg(stats["output_generation_ms"]),
            "mean_input_prep_ms": _avg(stats["input_prep_ms"]),
            "input_tokens": stats["input_tokens"],
            "output_tokens": stats["output_tokens"],
            "billed_input_tokens": stats["billed_input_tokens"],
            "billed_output_tokens": stats["billed_output_tokens"],
            "cpu_energy_j": stats["cpu_energy_j"],
            "gpu_energy_j": stats["gpu_energy_j"],
            "estimated_gco2e": stats["estimated_gco2e"],
        })

    for (api, method), stats in sorted(per_api_method.items()):
        summary_rows.append({
            "scope": "api",
            "api": api,
            "chaos_method": method,
            "packets": stats["packets"],
            "drifted_packets": stats["drifted"],
            "cohere_calls": stats["calls"],
            "exact_match": stats["correct"],
            "accuracy": (stats["correct"] / stats["calls"]) if stats["calls"] else 0.0,
            "mean_round_trip_ms": _avg(stats["round_trip_ms"]),
            "std_round_trip_ms": _std(stats["round_trip_ms"]),
            "mean_time_to_first_token_ms": _avg(stats["time_to_first_token_ms"]),
            "mean_output_generation_ms": _avg(stats["output_generation_ms"]),
            "mean_input_prep_ms": _avg(stats["input_prep_ms"]),
            "input_tokens": stats["input_tokens"],
            "output_tokens": stats["output_tokens"],
            "billed_input_tokens": stats["billed_input_tokens"],
            "billed_output_tokens": stats["billed_output_tokens"],
            "cpu_energy_j": stats["cpu_energy_j"],
            "gpu_energy_j": stats["gpu_energy_j"],
            "estimated_gco2e": stats["estimated_gco2e"],
        })

    summary = {
        "run_stamp": run_stamp,
        "run_number": args.run_number,
        "model": args.model,
        "packets_file": str(packets_path),
        "output_dir": str(output_dir),
        "methods": args.methods,
        "drift_rate": args.drift_rate,
        "repetitions": args.repetitions,
        "total_packets": total_packets,
        "total_drifted": total_drifted,
        "total_cohere_calls": total_calls,
        "total_exact_matches": total_correct,
        "overall_accuracy": (total_correct / total_calls) if total_calls else 0.0,
        "summary_rows": summary_rows,
    }

    if total_calls == 0:
        raise RuntimeError(
            "No successful Cohere API calls were recorded. "
            "The run is invalid; check COHERE_API_KEY, model availability, "
            "container environment propagation, and the Cohere API response logs."
        )

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    headers = [
        "Scope", "API", "Method", "Packets", "Drifted", "Calls", "Exact",
        "Accuracy", "RTT ms", "TTFT ms", "Gen ms", "Prep ms",
        "InTok", "OutTok", "BillIn", "BillOut", "CPU J", "GPU J", "gCO2e"
    ]
    with tex_path.open("w", encoding="utf-8") as handle:
        handle.write("\\begin{table}[t]\n\\centering\n\\small\n")
        handle.write(f"\\caption{{Cohere benchmark summary for run {args.run_number} ({run_stamp})}}\n")
        handle.write("\\begin{tabular}{llrrrrrrr rrr rrrrrr}\n")
        handle.write("\\toprule\n")
        handle.write(" & ".join(headers) + " \\\\\n")
        handle.write("\\midrule\n")
        for row in summary_rows:
            handle.write(
                f"{row['scope']} & {row['api']} & {row['chaos_method']} & "
                f"{row['packets']} & {row['drifted_packets']} & {row['cohere_calls']} & {row['exact_match']} & "
                f"{row['accuracy']:.3f} & {_format_ms(row['mean_round_trip_ms'])} & "
                f"{_format_ms(row['mean_time_to_first_token_ms'])} & {_format_ms(row['mean_output_generation_ms'])} & "
                f"{_format_ms(row['mean_input_prep_ms'])} & {row['input_tokens']} & {row['output_tokens']} & "
                f"{row['billed_input_tokens']} & {row['billed_output_tokens']} & "
                f"{_format_float(row['cpu_energy_j'])} & {_format_float(row['gpu_energy_j'])} & "
                f"{_format_float(row['estimated_gco2e'])} \\\\\n"
            )
        handle.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

    print()
    print("=== Benchmark Complete ===")
    print(f"Rows written:      {rows_path}")
    print(f"JSONL written:     {jsonl_path}")
    print(f"Summary written:   {summary_path}")
    print(f"LaTeX written:     {tex_path}")
    print(f"Energy written:    {energy_path}")
    print(f"Packets processed: {total_packets:,}")
    print(f"Drifted packets:   {total_drifted:,}")
    print(f"Cohere calls:      {total_calls:,}")
    print(f"Exact matches:     {total_correct:,}")
    if total_calls:
        print(f"Accuracy:          {total_correct / total_calls:.2%}")


if __name__ == "__main__":
    main()
