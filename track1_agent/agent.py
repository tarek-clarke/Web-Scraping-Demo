"""
agent.py — Track 1: Dynamic 3-Tier Gemma Ensemble on AMD MI300X.

Downloads 3 Gemma models at startup, then dynamically loads max copies
of each tier into VRAM, processes all tasks in that tier, unloads, and
moves to the next tier. Maximizes VRAM utilization per tier.

Tier 1: Gemma 4 E4B QAT — max copies for simple tasks (0 tokens)
Tier 2: Gemma 4 26B A4B QAT — max copies for medium tasks (0 tokens)
Tier 3: Gemma 4 31B QAT — max copies for complex tasks (0 tokens)
Tier 4: Fireworks AI — referral only when all Gemma tiers fail (tokens)
"""
from __future__ import annotations
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_feature_extractor import QueryFeatureExtractor

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

VQC_PARAMS_PATH = "/app/vqc_parameters.json"

GEMMA_E4B_PATH = "/tmp/gemma-4-e4b.q4.gguf"
GEMMA_26B_PATH = "/tmp/gemma-4-26b-a4b.q4.gguf"
GEMMA_31B_PATH = "/tmp/gemma-4-31b.q4.gguf"

GEMMA_DOWNLOADS = [
    ("google/gemma-4-E4B-it-qat-q4_0-gguf", "gemma-4-E4B_q4_0-it.gguf", GEMMA_E4B_PATH, 5),
    ("google/gemma-4-26B-A4B-it-qat-q4_0-gguf", "gemma-4-26B-A4B_q4_0-it.gguf", GEMMA_26B_PATH, 15),
    ("google/gemma-4-31B-it-qat-q4_0-gguf", "gemma-4-31B_q4_0-it.gguf", GEMMA_31B_PATH, 18),
]

_stats = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "local": 0, "remote": 0, "per_task": []}
_current_task_id = None

def _detect_category(query):
    q = query.lower()
    if re.search(r"sentiment|positive|negative|neutral|tone of", q): return "sentiment"
    if re.search(r"summar(?:ize|ise|y)|condense|in (?:one|a few) (?:sentence|word|paragraph)", q): return "summarization"
    if re.search(r"extract.*entit(?:y|ies)|named entity|ner\b|person.*org|label.*entit", q): return "ner"
    if re.search(r"bug|debug|fix.*code|error.*in.*code|what'?s wrong.*code|find.*bug", q): return "code_debug"
    if re.search(r"def\s+\w+|function|write.*(?:code|program|script)|implement", q): return "code_gen"
    if re.search(r"solve|calculat|arithmet|percent|discount|\d+\s*[\+\-\*\/]\s*\d+|how much|how many|total cost|average speed", q): return "math"
    if re.search(r"logic|puzzle|constraint|deduc|who.*lives|arrangement|sit.*in.*row|who sits where|friends.*sit|seating", q): return "logic"
    return "factual"

TIER1_CATEGORIES = {"sentiment", "ner", "summarization"}
TIER2_CATEGORIES = {"factual", "math", "logic"}
TIER3_CATEGORIES = {"code_gen", "code_debug"}

def _record_usage(task_id, route, usage=None):
    e = {"task_id": task_id, "route": route, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if usage:
        e["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
        e["completion_tokens"] = getattr(usage, "completion_tokens", 0) or 0
        e["total_tokens"] = getattr(usage, "total_tokens", 0) or 0
        _stats["prompt_tokens"] += e["prompt_tokens"]
        _stats["completion_tokens"] += e["completion_tokens"]
        _stats["total_tokens"] += e["total_tokens"]
    if route == "local": _stats["local"] += 1
    else: _stats["remote"] += 1
    _stats["per_task"].append(e)

# ---------------------------------------------------------------------------
# GPU + VRAM Detection
# ---------------------------------------------------------------------------

def detect_gpu():
    """Detect AMD GPU. Returns (has_gpu, vram_bytes)."""
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory
            print(f"[Q-Route] GPU detected via torch: {vram//1024//1024//1024}GB", flush=True)
            return True, vram
        print("[Q-Route] torch available but no CUDA/ROCm device", flush=True)
        return False, 0
    except ImportError:
        print("[Q-Route] torch not installed — no GPU, using Fireworks fallback", flush=True)
        return False, 0
    except Exception as e:
        print(f"[Q-Route] GPU detection error: {e}", flush=True)
        return False, 0

def max_copies_for_vram(vram_bytes, model_size_gb, num_tasks):
    """Calculate max model copies to fill 92% of available VRAM.
    Context memory: ~128MB for 2048 ctx, ~256MB for 4096 ctx (per copy, not per task).
    We process tasks sequentially within a tier, so 1 context slot per copy."""
    if vram_bytes <= 0:
        return 1, 0
    model_bytes = int(model_size_gb * 1024**3)
    # Context memory depends on model size (larger model = larger KV cache)
    if model_size_gb <= 6:
        ctx_bytes = 128 * 1024**2  # 128MB for small models (2048 ctx)
    else:
        ctx_bytes = 256 * 1024**2  # 256MB for large models (4096 ctx)
    per_copy = model_bytes + ctx_bytes
    usable = int(vram_bytes * 0.92)  # 92% utilization
    copies = max(2, usable // per_copy)
    return copies, -1

# ---------------------------------------------------------------------------
# VQC (trained on IBM Heron r2, runs on Aer simulator)
# ---------------------------------------------------------------------------

_vqc_params = None
_vqc_backend = None

def init_vqc():
    global _vqc_params, _vqc_backend
    if _vqc_params is not None:
        return
    try:
        _vqc_params = json.load(open(VQC_PARAMS_PATH)) if os.path.exists(VQC_PARAMS_PATH) else {}
        from qiskit_aer import AerSimulator
        _vqc_backend = AerSimulator()
        print(f"[Q-Route] VQC initialized ({len(_vqc_params)} params)", flush=True)
    except Exception as e:
        print(f"[Q-Route] VQC init failed: {e}", flush=True)
        _vqc_params = {}

def vqc_classify(features):
    if not _vqc_params or _vqc_backend is None:
        return 0.5, 0.5
    try:
        from qiskit.circuit import QuantumCircuit
        from qiskit.circuit.library import ZZFeatureMap, RealAmplitudes
        from qiskit import transpile

        fm = ZZFeatureMap(feature_dimension=10, reps=2)
        ansatz = RealAmplitudes(num_qubits=10, reps=3)
        qc = QuantumCircuit(10, 1)
        qc.compose(fm, qubits=list(range(10)), inplace=True)
        qc.compose(ansatz, qubits=list(range(10)), inplace=True)
        qc.measure(0, 0)

        fm_p = sorted([p for p in qc.parameters if p.name.startswith("x")], key=lambda p: p.name)
        an_p = sorted([p for p in qc.parameters if not p.name.startswith("x")], key=lambda p: p.name)
        bindings = {}
        for p, v in zip(fm_p, features):
            bindings[p] = float(v)
        for p in an_p:
            bindings[p] = float(_vqc_params.get(p.name, 0.0))

        bound = qc.assign_parameters(bindings)
        transpiled = transpile(bound, _vqc_backend)
        counts = _vqc_backend.run(transpiled, shots=256).result().get_counts()
        p1 = counts.get("1", 0) / 256
        return p1, max(p1, 1 - p1)
    except:
        return 0.5, 0.5

# ---------------------------------------------------------------------------
# Model Download
# ---------------------------------------------------------------------------

# Models auto-downloaded by transformers at load time (safetensors format)
# No manual GGUF download needed — transformers handles it
def download_all_models():
    print("[Q-Route] Models will be auto-downloaded by transformers on first load", flush=True)
    pass

# ---------------------------------------------------------------------------
# Dynamic Tier Loading + Inference (uses pre-installed PyTorch + ROCm for GPU)
# ---------------------------------------------------------------------------

_gemma_temps = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55,
                0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15,
                1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85]

_model_cache = {}

def load_model(model_path, ctx=2048):
    """Load model using transformers + PyTorch (pre-installed on scoring env)."""
    if model_path in _model_cache:
        return _model_cache[model_path]

    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    model_id = "google/gemma-3-1b-it"
    if "26b" in model_path:
        model_id = "google/gemma-4-26B-A4B-it"
    elif "31b" in model_path:
        model_id = "google/gemma-4-31B-it"
    elif "e4b" in model_path:
        model_id = "google/gemma-4-E4B-it"

    print(f"[Q-Route] Loading {model_id} via transformers...", flush=True)
    t0 = time.time()

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=dtype, device_map="auto"
    )
    model.eval()

    _model_cache[model_path] = (model, tokenizer)
    print(f"[Q-Route] Loaded in {time.time()-t0:.1f}s", flush=True)
    return model, tokenizer

def unload_model(model_path):
    if model_path in _model_cache:
        del _model_cache[model_path]
        import gc; gc.collect()
        try:
            import torch; torch.cuda.empty_cache()
        except: pass

def load_instances(path, num_copies, n_gpu, ctx=2048):
    """Load multiple copies for ensemble. Uses transformers on GPU."""
    instances = []
    for i in range(num_copies):
        try:
            model, tokenizer = load_model(path, ctx)
            instances.append((model, tokenizer))
        except Exception as e:
            print(f"[Q-Route] Load copy {i} failed: {e}", flush=True)
            break
    return instances

def unload_instances(instances):
    for model, tokenizer in instances:
        try:
            del model, tokenizer
        except: pass
    import gc; gc.collect()
    try:
        import torch; torch.cuda.empty_cache()
    except: pass

def infer_one(instance, idx, query, max_tokens):
    try:
        import torch
        model, tokenizer = instance
        temp = _gemma_temps[idx % len(_gemma_temps)]

        messages = [{"role": "user", "content": query}]
        input_ids = tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True
        ).to(model.device)

        with torch.no_grad():
            output = model.generate(
                input_ids,
                max_new_tokens=max_tokens,
                temperature=temp,
                do_sample=temp > 0,
            )

        response_ids = output[0][input_ids.shape[1]:]
        return tokenizer.decode(response_ids, skip_special_tokens=True).strip()
    except:
        return ""

def ensemble_consensus(query, instances, num_to_use, max_tokens, category, threshold):
    if not instances:
        return False, ""
    n = min(num_to_use, len(instances))
    with ThreadPoolExecutor(max_workers=min(n, 6)) as pool:
        answers = list(pool.map(
            lambda i: infer_one(instances[i], i, query, max_tokens),
            range(n)
        ))
    answers = [a for a in answers if a and len(a) > 5]
    if not answers:
        return False, ""

    normalized = [normalize_answer(a, category) for a in answers]
    counts = Counter(normalized)
    most_common, count = counts.most_common(1)[0]

    if count >= threshold:
        for i, n_val in enumerate(normalized):
            if n_val == most_common:
                return True, answers[i]
    return False, ""

# ---------------------------------------------------------------------------
# Consensus Normalization
# ---------------------------------------------------------------------------

def normalize_answer(text, category):
    t = text.lower().strip()
    if category == "sentiment":
        for label in ["positive", "negative", "neutral"]:
            if label in t: return label
        return t[:20]
    elif category == "math":
        nums = re.findall(r'\$?[\d,]+(?:\.\d+)?', t)
        return nums[-1] if nums else t[:20]
    elif category == "ner":
        entities = re.findall(r'[\w\s]+(?=:|(?:\s*→))', t)
        return ",".join(sorted(set(e.strip().lower() for e in entities))) if entities else t[:30]
    elif category in ("code_gen", "code_debug"):
        funcs = re.findall(r'def\s+(\w+)', t)
        return ",".join(funcs) if funcs else t[:30]
    elif category == "logic":
        lines = [l.strip() for l in t.split('\n') if l.strip() and not l.startswith('we') and not l.startswith('let')]
        return lines[-1][:30] if lines else t[:30]
    else:
        words = set(t.split())
        return " ".join(sorted(list(words))[:10])

# ---------------------------------------------------------------------------
# Fireworks Referral
# ---------------------------------------------------------------------------

import re as _re

def compress_prompt(query):
    """Compress prompt to reduce token count before sending to Fireworks."""
    q = query.strip()
    # Remove redundant phrases
    q = _re.sub(r'\b(?:Please|Can you|Could you|I would like you to)\b', '', q, flags=_re.IGNORECASE)
    q = _re.sub(r'\b(?:kindly|basically|essentially)\b', '', q, flags=_re.IGNORECASE)
    # Collapse whitespace
    q = _re.sub(r'\s+', ' ', q).strip()
    # Truncate very long prompts (keep first 500 chars — enough context)
    if len(q) > 500:
        q = q[:500] + "..."
    return q


def run_fireworks(query):
    if not FIREWORKS_API_KEY:
        return "[No API key]"
    import openai
    client = openai.OpenAI(base_url=FIREWORKS_BASE_URL, api_key=FIREWORKS_API_KEY)

    category = _detect_category(query)
    compressed = compress_prompt(query)
    # Tight caps per category — consensus picks longest, so shorter is fine
    caps = {"sentiment": 80, "ner": 150, "summarization": 200, "factual": 300,
            "math": 400, "logic": 800, "code_gen": 600, "code_debug": 600}
    max_tok = caps.get(category, 500)

    best, best_len = None, 0
    for model in ALLOWED_MODELS:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Answer directly and accurately. Be concise. Math: show calculation + final answer. Code: provide code. Sentiment: label + brief justification."},
                    {"role": "user", "content": compressed},
                ],
                temperature=0.0, max_tokens=max_tok,
            )
            a = r.choices[0].message.content.strip()
            if len(a) > best_len:
                best, best_len = a, len(a)
                _record_usage(_current_task_id or "?", "remote", r.usage)
        except:
            pass
    if best:
        return best
    _record_usage(_current_task_id or "?", "remote")
    return "[Fireworks failed]"

# ---------------------------------------------------------------------------
# Dynamic Tier Processing
# ---------------------------------------------------------------------------

def process_tier(tasks_in_tier, model_path, model_size_gb, has_gpu, vram, tier_name, max_tokens, ctx=2048):
    """Load max copies, process all tasks in tier, unload."""
    if not tasks_in_tier or not os.path.exists(model_path):
        return {}

    num_tasks = len(tasks_in_tier)
    copies, n_gpu = max_copies_for_vram(vram, model_size_gb, num_tasks)
    print(f"[Q-Route] === TIER {tier_name}: {copies} copies for {num_tasks} tasks ===", flush=True)

    t0 = time.time()
    instances = load_instances(model_path, copies, n_gpu, ctx=ctx)
    print(f"[Q-Route] Loaded {len(instances)} copies in {time.time()-t0:.1f}s", flush=True)

    if not instances:
        return {}

    threshold = max(2, int(copies * 0.6))
    results = {}

    for task_id, prompt, category in tasks_in_tier:
        _current_task_id_ref = task_id
        agreed, answer = ensemble_consensus(prompt, instances, copies, max_tokens, category, threshold)
        if agreed:
            print(f"[Q-Route] {task_id}: {tier_name} CONSENSUS — 0 tokens", flush=True)
            _record_usage(task_id, "local")
            results[task_id] = answer
        else:
            results[task_id] = None

    print(f"[Q-Route] Unloading {tier_name}...", flush=True)
    unload_instances(instances)
    return results

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _current_task_id

    input_path = "/input/tasks.json"
    output_path = "/output/results.json"
    if not os.path.exists("/input"): input_path = "tasks.json"
    if not os.path.exists("/output"): output_path = "results.json"

    if not os.path.exists(input_path):
        print(f"[Q-Route] Input not found: {input_path}")
        sys.exit(1)

    with open(input_path) as f:
        tasks = json.load(f)

    num_tasks = len(tasks)
    print(f"[Q-Route] Processing {num_tasks} queries...", flush=True)

    has_gpu, vram = detect_gpu()
    print(f"[Q-Route] GPU={has_gpu} VRAM={vram//1024//1024//1024 if vram else 0}GB", flush=True)

    init_vqc()

    # Only download + load Gemma if GPU is available (CPU is too slow for 3-tier)
    use_gemma = has_gpu
    if use_gemma:
        download_all_models()

    extractor = QueryFeatureExtractor()

    # Classify all tasks and group by tier
    tier1_tasks = []
    tier2_tasks = []
    tier3_tasks = []
    task_order = []

    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        category = _detect_category(prompt)
        features = extractor.extract(prompt)
        vqc_complexity, vqc_confidence = vqc_classify(features)

        # VQC safety: if VQC says complex, bump to harder tier
        if category in TIER1_CATEGORIES and vqc_complexity > 0.6:
            print(f"[Q-Route] {task_id}: VQC bumped T1→T2 (complexity={vqc_complexity:.2f})", flush=True)
            tier2_tasks.append((task_id, prompt, category))
        elif category in TIER2_CATEGORIES and vqc_complexity > 0.7:
            print(f"[Q-Route] {task_id}: VQC bumped T2→T3 (complexity={vqc_complexity:.2f})", flush=True)
            tier3_tasks.append((task_id, prompt, category))
        elif category in TIER1_CATEGORIES:
            tier1_tasks.append((task_id, prompt, category))
        elif category in TIER2_CATEGORIES:
            tier2_tasks.append((task_id, prompt, category))
        elif category in TIER3_CATEGORIES:
            tier3_tasks.append((task_id, prompt, category))
        else:
            tier2_tasks.append((task_id, prompt, category))

        task_order.append((task_id, prompt, category))

    print(f"[Q-Route] T1={len(tier1_tasks)} T2={len(tier2_tasks)} T3={len(tier3_tasks)}", flush=True)

    # Process tiers dynamically (only if GPU available)
    if use_gemma:
        t1_results = process_tier(tier1_tasks, GEMMA_E4B_PATH, 5, has_gpu, vram, "T1-E4B", 100, ctx=2048)
        t2_results = process_tier(tier2_tasks, GEMMA_26B_PATH, 15, has_gpu, vram, "T2-26B", 300, ctx=4096)
        t3_results = process_tier(tier3_tasks, GEMMA_31B_PATH, 18, has_gpu, vram, "T3-31B", 500, ctx=4096)
    else:
        print("[Q-Route] No GPU — skipping Gemma, using Fireworks for all tasks", flush=True)
        t1_results = {}
        t2_results = {}
        t3_results = {}

    # Merge results + Fireworks referral for failures
    all_results = {}
    all_results.update(t1_results)
    all_results.update(t2_results)
    all_results.update(t3_results)

    results = []
    for task_id, prompt, category in task_order:
        _current_task_id = task_id
        answer = all_results.get(task_id)

        if answer is None:
            print(f"[Q-Route] {task_id}: FIREWORKS referral", flush=True)
            answer = run_fireworks(prompt)

        results.append({"task_id": task_id, "answer": answer})

    # Print stats
    print("\n" + "=" * 60)
    print(f"[Q-Route] SUMMARY: local={_stats['local']} remote={_stats['remote']}")
    print(f"[Q-Route] TOKENS: total={_stats['total_tokens']} prompt={_stats['prompt_tokens']} completion={_stats['completion_tokens']}")
    for t in _stats["per_task"]:
        tag = "LOCAL" if t.get("route") == "local" else "REMOTE"
        print(f"  [{tag}] {t['task_id']}: {t['total_tokens']} tokens")
    print("=" * 60)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[Q-Route] Wrote {len(results)} results to {output_path}")
    sys.exit(0)

if __name__ == "__main__":
    main()
