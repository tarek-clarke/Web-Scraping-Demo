#!/usr/bin/env python3
"""Generate and freeze model-backed Qwen schema drift on LUMI-G.

Only packets deterministically assigned to the `qwen` chaos family are sent to
the model. Qwen returns a one-to-one top-level key-renaming map; values are
copied byte-for-byte from the real source packet. Invalid, identity, partial,
or duplicate mappings fail loudly. The saved JSONL is reused by every oracle
and hardware run, so Qwen is never called independently per platform.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.benchmark_protocol import ACTIVE_API_SOURCES, DEFAULT_SNAPSHOT_PATH


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: object) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


def stable_seed(*parts: object) -> int:
    return int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def load_packets(path: Path) -> dict[str, list[dict]]:
    text = path.read_text(encoding="utf-8").strip()
    rows = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines() if line.strip()]
    groups = defaultdict(list)
    for row in rows:
        groups[str(row["source"])].append(row)
    counts = {source: len(groups[source]) for source in ACTIVE_API_SOURCES}
    if any(value != 2500 for value in counts.values()):
        raise RuntimeError(f"Qwen publication run requires 2,500 packets per source; found {counts}")
    return groups


def selected_packets(groups: dict[str, list[dict]], seed: int, drift_rate: float):
    methods = ("qwen", "json_manip", "schema_alter")
    for source in ACTIVE_API_SOURCES:
        packets = groups[source]
        count = round(len(packets) * drift_rate)
        indices = sorted(range(len(packets)), key=lambda i: stable_seed(seed, source, i, "drift-selection"))[:count]
        for packet_index in indices:
            method = methods[stable_seed(seed, source, packet_index, "method") % len(methods)]
            if method == "qwen":
                yield source, packet_index, packets[packet_index]


def schema_prompt(source: str, data: dict) -> str:
    schema = [{"key": str(key), "type": type(value).__name__} for key, value in data.items()]
    return (
        "You generate realistic API schema drift for a reproducible research benchmark. "
        "Return only one JSON object mapping every input key to one unique replacement key. "
        "Preserve meaning, use plausible snake_case API names, do not add or omit keys, and "
        "change at least one key. Source domain: " + source + ". Schema: " + stable_json(schema)
    )


def extract_json_object(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Qwen response contains no JSON object")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("Qwen response is not a JSON object")
    return value


def validate_mapping(data: dict, mapping: dict) -> dict[str, str]:
    expected = {str(key) for key in data}
    normalized = {str(key): str(value) for key, value in mapping.items()}
    if set(normalized) != expected:
        raise ValueError(f"mapping keys differ from schema: expected={sorted(expected)} got={sorted(normalized)}")
    if len(set(normalized.values())) != len(normalized):
        raise ValueError("replacement keys are not one-to-one")
    if any(not value.strip() for value in normalized.values()):
        raise ValueError("replacement key is empty")
    if all(key == value for key, value in normalized.items()):
        raise ValueError("mapping is an identity transform")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--output", default="data/training/qwen_model_chaos_22500_v1.jsonl")
    parser.add_argument("--model", default=os.environ.get("QWEN_CHAOS_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct"))
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--drift-rate", type=float, default=0.10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not 0 < args.drift_rate <= 1 or args.batch_size < 1:
        raise SystemExit("invalid drift rate or batch size")
    output = (REPO_ROOT / args.output).resolve()
    if output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite frozen Qwen chaos: {output}")

    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Qwen chaos generation requires a scheduler-bound GPU; CPU fallback is forbidden")
    from transformers import AutoModelForCausalLM, AutoTokenizer

    packets_path = (REPO_ROOT / args.packets).resolve()
    groups = load_packets(packets_path)
    selected = list(selected_packets(groups, args.seed, args.drift_rate))
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype="auto").to("cuda").eval()

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    written = 0
    with temporary.open("w", encoding="utf-8") as stream, torch.inference_mode():
        for start in range(0, len(selected), args.batch_size):
            batch = selected[start:start + args.batch_size]
            prompts = []
            for source, _, packet in batch:
                data = packet.get("data")
                if not isinstance(data, dict) or not data:
                    raise RuntimeError(f"{source} contains a non-object/empty packet")
                message = [{"role": "user", "content": schema_prompt(source, data)}]
                prompts.append(tokenizer.apply_chat_template(message, tokenize=False, add_generation_prompt=True))
            encoded = tokenizer(prompts, return_tensors="pt", padding=True).to("cuda")
            generated = model.generate(**encoded, do_sample=False, max_new_tokens=args.max_new_tokens, pad_token_id=tokenizer.pad_token_id)
            prompt_width = encoded["input_ids"].shape[1]
            responses = tokenizer.batch_decode(generated[:, prompt_width:], skip_special_tokens=True)
            for (source, packet_index, packet), response in zip(batch, responses):
                original = packet["data"]
                try:
                    mapping = validate_mapping(original, extract_json_object(response))
                except Exception as exc:
                    raise RuntimeError(f"Invalid Qwen mapping for {source}[{packet_index}]: {exc}; response={response[:500]!r}") from exc
                drifted = {mapping[str(key)]: value for key, value in original.items()}
                row = {
                    "source": source, "packet_index": packet_index,
                    "source_record_id": packet.get("source_record_id"),
                    "model": args.model, "generation": {"do_sample": False, "max_new_tokens": args.max_new_tokens},
                    "original_sha256": sha(original), "mapping": mapping,
                    "drifted_data": drifted, "drifted_sha256": sha(drifted),
                }
                stream.write(stable_json(row) + "\n")
                written += 1
            stream.flush()
            print(f"Qwen chaos: {written:,}/{len(selected):,}", flush=True)
    os.replace(temporary, output)
    manifest = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "packets": str(packets_path), "packets_sha256": hashlib.sha256(packets_path.read_bytes()).hexdigest(),
        "model": args.model, "seed": args.seed, "drift_rate": args.drift_rate,
        "records": written, "output": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "deterministic_generation": True, "cpu_fallback": False,
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
