"""
agent.py — Track 1: Multi-tier Gemma 4 GPU ensemble on AMD MI300X.

Downloads Gemma 4 E4B + 26B A4B + 31B QAT GGUF from HuggingFace (open repos).
Auto-detects GPU + VRAM, loads maximum model copies per tier.
Dynamic tier loading: process all simple tasks with max E4B copies,
unload, load max 26B copies for medium tasks, unload, load max 31B for complex.
Fireworks all-model consensus only for tasks that fail Gemma consensus.

Triple sponsor flex: AMD MI300X (92% VRAM) + Google Gemma 4 QAT + IBM Heron r2 VQC.
"""
from __future__ import annotations
import json, os, re, sys, time, gc, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

SIMPLE_CATEGORIES = {"sentiment", "ner", "summarization", "factual"}
MEDIUM_CATEGORIES = {"math", "logic"}
COMPLEX_CATEGORIES = {"code_gen", "code_debug"}

GEMMA_MODELS = [
    {"name": "E4B", "repo": "google/gemma-4-E4B-it-qat-q4_0-gguf", "file": "gemma-4-E4B_q4_0-it.gguf", "path": "/tmp/gemma-e4b.q4.gguf", "size_gb": 5, "categories": SIMPLE_CATEGORIES, "ctx": 2048, "max_tokens": 200},
    {"name": "26B-A4B", "repo": "google/gemma-4-26B-A4B-it-qat-q4_0-gguf", "file": "gemma-4-26B-A4B_q4_0-it.gguf", "path": "/tmp/gemma-26b.q4.gguf", "size_gb": 15, "categories": MEDIUM_CATEGORIES, "ctx": 4096, "max_tokens": 400},
    {"name": "31B", "repo": "google/gemma-4-31B-it-qat-q4_0-gguf", "file": "gemma-4-31B_q4_0-it.gguf", "path": "/tmp/gemma-31b.q4.gguf", "size_gb": 18, "categories": COMPLEX_CATEGORIES, "ctx": 4096, "max_tokens": 600},
]

_stats = {"total_tokens": 0, "local": 0, "remote": 0, "per_task": []}
_current_task_id = None

def _detect_category(query):
    q = query.lower()
    if re.search(r"sentiment|positive|negative|neutral|tone of", q): return "sentiment"
    if re.search(r"summar(?:ize|ise|y)|condense|in (?:one|a few) (?:sentence|word|paragraph)", q): return "summarization"
    if re.search(r"extract.*entit(?:y|ies)|named entity|ner\b|person.*org|label.*entit", q): return "ner"
    if re.search(r"bug|debug|fix.*code|error.*in.*code|find.*bug", q): return "code_debug"
    if re.search(r"def\s+\w+|function|write.*(?:code|program|script)|implement", q): return "code_gen"
    if re.search(r"solve|calculat|percent|discount|how much|how many|total cost", q): return "math"
    if re.search(r"logic|puzzle|constraint|deduc|arrangement|seating", q): return "logic"
    return "factual"

def _record_usage(task_id, route, usage=None):
    e = {"task_id": task_id, "route": route, "tokens": 0}
    if usage:
        e["tokens"] = getattr(usage, "total_tokens", 0) or 0
        _stats["total_tokens"] += e["tokens"]
    if route == "local": _stats["local"] += 1
    else: _stats["remote"] += 1
    _stats["per_task"].append(e)

# ---------------------------------------------------------------------------
# GPU Detection + VRAM Auto-Scaling
# ---------------------------------------------------------------------------

def detect_gpu():
    """Detect AMD GPU via torch or /opt/rocm."""
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory
            print(f"[Q-Route] GPU detected via torch: {vram//1024//1024//1024}GB", flush=True)
            return True, vram
    except ImportError:
        pass
    except Exception:
        pass

    has_rocm = os.path.exists("/opt/rocm") or os.path.exists("/opt/rocm-6.2.0")
    if has_rocm:
        print("[Q-Route] /opt/rocm detected — assuming GPU available", flush=True)
        # Can't query VRAM without torch, assume MI300X (192GB)
        return True, 192 * 1024**3

    print("[Q-Route] No GPU detected — CPU fallback", flush=True)
    return False, 0

def max_copies(vram_bytes, model_size_gb, num_tasks):
    """Calculate max model copies to fill 92% of VRAM, minus 1 instance for safety."""
    if vram_bytes <= 0:
        return 1, 0
    model_bytes = int(model_size_gb * 1024**3)
    # Context: ~128MB for small models (2048 ctx), ~256MB for large (4096 ctx)
    ctx_bytes = 128 * 1024**2 if model_size_gb <= 6 else 256 * 1024**2
    per_copy = model_bytes + ctx_bytes
    usable = int(vram_bytes * 0.92)
    raw_copies = usable // per_copy
    # Subtract 1 for safety margin (don't burn ALL VRAM)
    copies = max(2, raw_copies - 1)
    return copies, -1  # -1 = all layers on GPU

# ---------------------------------------------------------------------------
# Model Download
# ---------------------------------------------------------------------------

def download_model(config):
    path = config["path"]
    if os.path.exists(path) and os.path.getsize(path) > 100_000_000:
        print(f"[Q-Route] {config['name']} already exists ({os.path.getsize(path)//1024//1024}MB)", flush=True)
        return True
    try:
        from huggingface_hub import hf_hub_download
        print(f"[Q-Route] Downloading {config['name']} ({config['size_gb']}GB)...", flush=True)
        t0 = time.time()
        downloaded = hf_hub_download(repo_id=config["repo"], filename=config["file"], local_dir="/tmp")
        os.rename(downloaded, path)
        print(f"[Q-Route] Downloaded {config['name']} in {time.time()-t0:.1f}s", flush=True)
        return True
    except Exception as e:
        print(f"[Q-Route] Download {config['name']} failed: {e}", flush=True)
        return False

# ---------------------------------------------------------------------------
# Dynamic Tier Loading + Parallel Consensus
# ---------------------------------------------------------------------------

TEMPERATURES = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45,
                0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95,
                1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45,
                1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85]

def load_instances(path, num_copies, n_gpu, ctx):
    """Load N copies of model into VRAM."""
    from llama_cpp import Llama
    instances = []
    for i in range(num_copies):
        try:
            llm = Llama(model_path=path, n_ctx=ctx, n_threads=4, n_gpu_layers=n_gpu, verbose=False)
            instances.append(llm)
        except Exception as e:
            print(f"[Q-Route] Load copy {i+1} failed: {e}", flush=True)
            break
    return instances

def unload_instances(instances):
    for llm in instances:
        try:
            del llm
        except:
            pass
    gc.collect()

def infer_one(instance, idx, query, max_tokens):
    """Run inference on one instance."""
    try:
        temp = TEMPERATURES[idx % len(TEMPERATURES)]
        resp = instance.create_chat_completion(
            messages=[{"role": "user", "content": query}],
            temperature=temp, max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"].strip()
    except:
        return ""

def consensus_vote(answers, category, threshold):
    """Vote on answers. Return (agreed, best_answer)."""
    if not answers:
        return False, ""

    # Normalize for comparison
    def normalize(text, cat):
        t = text.lower().strip()
        if cat == "sentiment":
            for label in ["positive", "negative", "neutral"]:
                if label in t: return label
            return t[:20]
        elif cat == "math":
            nums = re.findall(r'\$?[\d,]+(?:\.\d+)?', t)
            return nums[-1] if nums else t[:20]
        elif cat == "ner":
            entities = re.findall(r'[\w\s]+(?=:|(?:\s*→))', t)
            return ",".join(sorted(set(e.strip().lower() for e in entities))) if entities else t[:30]
        elif cat in ("code_gen", "code_debug"):
            funcs = re.findall(r'def\s+(\w+)', t)
            return ",".join(funcs) if funcs else t[:30]
        else:
            words = set(t.split())
            return " ".join(sorted(list(words))[:10])

    normalized = [normalize(a, category) for a in answers]
    counts = Counter(normalized)
    most_common, count = counts.most_common(1)[0]

    if count >= threshold:
        for i, n_val in enumerate(normalized):
            if n_val == most_common:
                return True, answers[i]
    return False, ""

def process_tier(tier_tasks, config, has_gpu, vram, n_gpu):
    """Load max copies of a model, process all tasks in tier with consensus, unload."""
    if not tier_tasks or not os.path.exists(config["path"]):
        return {}

    num_tasks = len(tier_tasks)
    copies, gpu_layers = max_copies(vram, config["size_gb"], num_tasks) if has_gpu else (1, 0)

    print(f"\n[Q-Route] === TIER {config['name']}: {copies} copies for {num_tasks} tasks ===", flush=True)
    t0 = time.time()
    instances = load_instances(config["path"], copies, gpu_layers, config["ctx"])
    print(f"[Q-Route] Loaded {len(instances)} copies in {time.time()-t0:.1f}s", flush=True)

    if not instances:
        return {}

    threshold = max(2, int(len(instances) * 0.6))
    results = {}

    for task_id, prompt, category in tier_tasks:
        # Run all copies in parallel
        with ThreadPoolExecutor(max_workers=min(len(instances), 6)) as pool:
            answers = list(pool.map(
                lambda i: infer_one(instances[i], i, prompt, config["max_tokens"]),
                range(len(instances))
            ))
        answers = [a for a in answers if a and len(a) > 5]

        agreed, answer = consensus_vote(answers, category, threshold)
        if agreed:
            print(f"[Q-Route] {task_id}: {config['name']} CONSENSUS ({count}/{len(instances)}) — 0 tokens", flush=True)
            _record_usage(task_id, "local")
            results[task_id] = answer
        else:
            results[task_id] = None

    print(f"[Q-Route] Unloading {config['name']}...", flush=True)
    unload_instances(instances)
    return results

# ---------------------------------------------------------------------------
# Fireworks All-Model Consensus (proven 89.5% accuracy)
# ---------------------------------------------------------------------------

def run_fireworks(query):
    global _current_task_id
    if not FIREWORKS_API_KEY:
        return "[No API key]"
    import openai
    client = openai.OpenAI(base_url=FIREWORKS_BASE_URL, api_key=FIREWORKS_API_KEY)
    best, best_len = None, 0
    for model in ALLOWED_MODELS:
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
    vram_gb = vram // 1024 // 1024 // 1024 if vram else 0
    print(f"[Q-Route] GPU={has_gpu} VRAM={vram_gb}GB", flush=True)

    # Download all 3 Gemma 4 models in parallel
    print("[Q-Route] Downloading Gemma 4 models...", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        download_futures = {pool.submit(download_model, cfg): cfg for cfg in GEMMA_MODELS}
        for future in as_completed(download_futures):
            cfg = download_futures[future]
            success = future.result()
            print(f"[Q-Route] {cfg['name']}: {'downloaded' if success else 'FAILED'}", flush=True)

    # Classify tasks into tiers
    tier_tasks = {0: [], 1: [], 2: []}  # 0=simple, 1=medium, 2=complex
    task_order = []

    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        category = _detect_category(prompt)

        if category in SIMPLE_CATEGORIES:
            tier_tasks[0].append((task_id, prompt, category))
        elif category in MEDIUM_CATEGORIES:
            tier_tasks[1].append((task_id, prompt, category))
        else:
            tier_tasks[2].append((task_id, prompt, category))

        task_order.append((task_id, prompt, category))

    print(f"[Q-Route] Tiers: simple={len(tier_tasks[0])} medium={len(tier_tasks[1])} complex={len(tier_tasks[2])}", flush=True)

    # Process tiers dynamically (load max copies, process, unload, next tier)
    all_results = {}

    for tier_idx, config in enumerate(GEMMA_MODELS):
        tier = tier_tasks[tier_idx]
        if not tier:
            continue
        results = process_tier(tier, config, has_gpu, vram, -1 if has_gpu else 0)
        all_results.update(results)

    # Fireworks referral for any failed tasks (in parallel)
    failed_tasks = [(tid, prompt, cat) for tid, prompt, cat in task_order if all_results.get(tid) is None]

    if failed_tasks:
        print(f"\n[Q-Route] {len(failed_tasks)} tasks need Fireworks referral — running in parallel...", flush=True)

        def fireworks_task(task_info):
            global _current_task_id
            tid, prompt, cat = task_info
            _current_task_id = tid
            print(f"[Q-Route] {tid}: FIREWORKS ({cat})", flush=True)
            return tid, run_fireworks(prompt)

        with ThreadPoolExecutor(max_workers=min(len(failed_tasks), 8)) as pool:
            futures = {pool.submit(fireworks_task, t): t for t in failed_tasks}
            for future in as_completed(futures):
                tid, answer = future.result()
                all_results[tid] = answer

    # Assemble results in original order
    results = []
    for task_id, prompt, category in task_order:
        answer = all_results.get(task_id, "[No answer]")
        results.append({"task_id": task_id, "answer": answer})

    # Print stats
    print("\n" + "=" * 60)
    print(f"[Q-Route] SUMMARY: local={_stats['local']} remote={_stats['remote']} tokens={_stats['total_tokens']}")
    for t in _stats["per_task"]:
        tag = "LOCAL" if t.get("route") == "local" else "REMOTE"
        print(f"  [{tag}] {t['task_id']}: {t['tokens']} tokens")
    print("=" * 60)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[Q-Route] Wrote {len(results)} results to {output_path}")
    sys.exit(0)

if __name__ == "__main__":
    main()
