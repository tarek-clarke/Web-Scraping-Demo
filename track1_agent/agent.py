"""
agent.py — Track 1: 100% Local Gemma 4 E4B Consensus (0 Fireworks tokens).

Downloads Gemma 4 E4B QAT GGUF from HuggingFace (open repo, not gated).
Loads multiple copies into GPU VRAM for parallel consensus voting.
No Fireworks API calls = 0 tokens.

Falls back to Fireworks single-model if GPU unavailable.
"""
from __future__ import annotations
import json, os, re, sys, time, gc
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

# Gemma 4 E4B QAT GGUF — open repo, NOT gated
GEMMA_REPO = "google/gemma-4-E4B-it-qat-q4_0-gguf"
GEMMA_FILE = "gemma-4-E4B_q4_0-it.gguf"
GEMMA_PATH = "/tmp/gemma-4-e4b.q4.gguf"
MODEL_SIZE_GB = 5.0

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
# Download Gemma 4 E4B (open repo, not gated)
# ---------------------------------------------------------------------------

def download_gemma():
    if os.path.exists(GEMMA_PATH) and os.path.getsize(GEMMA_PATH) > 1_000_000_000:
        print(f"[Q-Route] Gemma already downloaded ({os.path.getsize(GEMMA_PATH)//1024//1024}MB)", flush=True)
        return True
    try:
        from huggingface_hub import hf_hub_download
        print(f"[Q-Route] Downloading {GEMMA_FILE} from {GEMMA_REPO}...", flush=True)
        t0 = time.time()
        path = hf_hub_download(repo_id=GEMMA_REPO, filename=GEMMA_FILE, local_dir="/tmp")
        os.rename(path, GEMMA_PATH)
        print(f"[Q-Route] Downloaded in {time.time()-t0:.1f}s ({os.path.getsize(GEMMA_PATH)//1024//1024}MB)", flush=True)
        return True
    except Exception as e:
        print(f"[Q-Route] Download failed: {e}", flush=True)
        return False

# ---------------------------------------------------------------------------
# GPU Detection + VRAM Auto-Scaling
# ---------------------------------------------------------------------------

def detect_gpu():
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory
            name = torch.cuda.get_device_name(0)
            print(f"[Q-Route] GPU: {name} ({vram//1024//1024//1024}GB)", flush=True)
            return True, vram
    except:
        pass
    if os.path.exists("/opt/rocm"):
        print("[Q-Route] /opt/rocm found — assuming GPU (192GB)", flush=True)
        return True, 192 * 1024**3
    print("[Q-Route] No GPU — Fireworks fallback", flush=True)
    return False, 0

def max_copies(vram_bytes, model_size_gb):
    if vram_bytes <= 0:
        return 1
    model_bytes = int(model_size_gb * 1024**3)
    ctx_bytes = 256 * 1024**2
    per_copy = model_bytes + ctx_bytes
    usable = int(vram_bytes * 0.90)
    raw = usable // per_copy
    return max(2, raw - 1)

# ---------------------------------------------------------------------------
# Gemma 4 E4B Parallel Ensemble (0 Fireworks tokens)
# ---------------------------------------------------------------------------

_instances = []
_TEMPS = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45,
          0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95,
          1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45,
          1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85]

def init_gemma(num_copies, n_gpu):
    global _instances
    if _instances:
        return
    if not os.path.exists(GEMMA_PATH):
        if not download_gemma():
            return
    try:
        from llama_cpp import Llama
        print(f"[Q-Route] Loading {num_copies}× Gemma 4 E4B (n_gpu_layers={n_gpu})...", flush=True)
        t0 = time.time()
        for i in range(num_copies):
            llm = Llama(
                model_path=GEMMA_PATH,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=n_gpu,
                verbose=False,
            )
            _instances.append(llm)
            print(f"[Q-Route] Copy {i+1}/{num_copies} loaded", flush=True)
        print(f"[Q-Route] {len(_instances)} copies loaded in {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print(f"[Q-Route] Gemma load failed: {e}", flush=True)
        _instances = []

def infer_one(idx, query, max_tokens=300):
    if idx >= len(_instances):
        return ""
    try:
        temp = _TEMPS[idx % len(_TEMPS)]
        resp = _instances[idx].create_chat_completion(
            messages=[{"role": "user", "content": query}],
            temperature=temp,
            max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"].strip()
    except:
        return ""

def parallel_consensus(query, num_copies, category, max_tokens=300):
    n = min(num_copies, len(_instances))
    with ThreadPoolExecutor(max_workers=min(n, 8)) as pool:
        answers = list(pool.map(
            lambda i: infer_one(i, query, max_tokens),
            range(n)
        ))
    answers = [a for a in answers if a and len(a) > 5]
    if not answers:
        return None

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
    threshold = max(2, int(n * 0.5))

    if count >= threshold:
        for i, nv in enumerate(normalized):
            if nv == most_common:
                return answers[i]
    return max(answers, key=len)

# ---------------------------------------------------------------------------
# Fireworks Fallback
# ---------------------------------------------------------------------------

def run_fireworks(query):
    global _current_task_id
    if not FIREWORKS_API_KEY:
        return "[No API key]"
    import openai
    client = openai.OpenAI(base_url=FIREWORKS_BASE_URL, api_key=FIREWORKS_API_KEY)
    model = ALLOWED_MODELS[0]
    for m in ALLOWED_MODELS:
        if "deepseek" in m.lower() or "kimi" in m.lower():
            model = m
            break
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert AI assistant. Answer accurately and completely. For math and logic, show reasoning and state the final answer. For code, provide complete working code."},
                {"role": "user", "content": query},
            ],
            temperature=0.0, max_tokens=2048,
        )
        _record_usage(_current_task_id or "?", "remote", r.usage)
        return r.choices[0].message.content.strip()
    except:
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
    n_gpu = -1 if has_gpu else 0
    copies = max_copies(vram, MODEL_SIZE_GB) if has_gpu else 0

    if has_gpu:
        init_gemma(copies, n_gpu)

    results = []
    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        _current_task_id = task_id
        category = _detect_category(prompt)

        answer = None

        if _instances:
            answer = parallel_consensus(prompt, copies, category, max_tokens=300)
            if answer:
                print(f"[Q-Route] {task_id}: LOCAL ({category}) — 0 tokens", flush=True)
                _record_usage(task_id, "local")

        if answer is None:
            print(f"[Q-Route] {task_id}: FIREWORKS ({category})", flush=True)
            answer = run_fireworks(prompt)

        results.append({"task_id": task_id, "answer": answer})

    _instances.clear()
    gc.collect()

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
