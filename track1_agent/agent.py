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
    has_rocm = os.path.exists("/opt/rocm") or os.path.exists("/opt/rocm-6.2.0")
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory
            return True, vram
    except:
        pass
    return has_rocm, 0

def max_copies_for_vram(vram_bytes, model_size_gb, num_tasks):
    if vram_bytes <= 0:
        return 1, 0
    model_bytes = int(model_size_gb * 1024**3)
    ctx_bytes = int(0.3 * 1024**3) * num_tasks
    per_copy = model_bytes + ctx_bytes
    usable = int(vram_bytes * 0.90)
    copies = max(2, min(38, usable // per_copy))
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

def download_all_models():
    for repo, fname, dest, size_gb in GEMMA_DOWNLOADS:
        if os.path.exists(dest) and os.path.getsize(dest) > 100_000_000:
            print(f"[Q-Route] {fname} already exists ({os.path.getsize(dest)//1024//1024}MB)", flush=True)
            continue
        try:
            from huggingface_hub import hf_hub_download
            print(f"[Q-Route] Downloading {fname} ({size_gb}GB)...", flush=True)
            t0 = time.time()
            path = hf_hub_download(repo_id=repo, filename=fname, local_dir="/tmp")
            os.rename(path, dest)
            print(f"[Q-Route] Downloaded in {time.time()-t0:.1f}s", flush=True)
        except Exception as e:
            print(f"[Q-Route] Download {fname} failed: {e}", flush=True)

# ---------------------------------------------------------------------------
# Dynamic Tier Loading + Inference
# ---------------------------------------------------------------------------

_gemma_temps = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55,
                0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15,
                1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85]

def load_instances(path, num_copies, n_gpu, ctx=2048):
    from llama_cpp import Llama
    instances = []
    for i in range(num_copies):
        llm = Llama(model_path=path, n_ctx=ctx, n_threads=4, n_gpu_layers=n_gpu, verbose=False)
        instances.append(llm)
    return instances

def unload_instances(instances):
    for llm in instances:
        try:
            del llm
        except:
            pass
    import gc
    gc.collect()

def infer_one(instance, idx, query, max_tokens):
    try:
        temp = _gemma_temps[idx % len(_gemma_temps)]
        resp = instance.create_chat_completion(
            messages=[{"role": "user", "content": query}],
            temperature=temp,
            max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"].strip()
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

def run_fireworks(query):
    if not FIREWORKS_API_KEY:
        return "[No API key]"
    import openai
    client = openai.OpenAI(base_url=FIREWORKS_BASE_URL, api_key=FIREWORKS_API_KEY)
    models = ALLOWED_MODELS[:2] if len(ALLOWED_MODELS) >= 2 else ALLOWED_MODELS
    best, best_len = None, 0
    for model in models:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert AI assistant. Answer accurately and completely. For math and logic, show reasoning and state the final answer. For code, provide complete working code."},
                    {"role": "user", "content": query},
                ],
                temperature=0.0, max_tokens=2048,
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

    # Process tiers dynamically
    t1_results = process_tier(tier1_tasks, GEMMA_E4B_PATH, 5, has_gpu, vram, "T1-E4B", 100, ctx=2048)
    t2_results = process_tier(tier2_tasks, GEMMA_26B_PATH, 15, has_gpu, vram, "T2-26B", 300, ctx=4096)
    t3_results = process_tier(tier3_tasks, GEMMA_31B_PATH, 18, has_gpu, vram, "T3-31B", 500, ctx=4096)

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
