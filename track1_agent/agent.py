"""
agent.py — Track 1: Gemma 4 E4B via transformers on ROCm GPU + Fireworks fallback.

Scoring env has ROCm 7.2 + PyTorch 2.13 pre-installed.
Gemma handles simple tasks at 0 Fireworks tokens on MI300X.
Fireworks single-model handles complex tasks (minimal tokens).
"""
from __future__ import annotations
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

GEMMA_MODEL = "google/gemma-4-E4B-it"
SIMPLE_CATEGORIES = {"sentiment", "ner", "summarization", "factual"}

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
# Gemma 4 E4B on ROCm GPU (0 Fireworks tokens)
# ---------------------------------------------------------------------------

_model = None
_tokenizer = None
_gpu_ok = False

def init_gemma():
    global _model, _tokenizer, _gpu_ok
    try:
        import torch
        if not torch.cuda.is_available():
            print("[Q-Route] No GPU — using Fireworks fallback", flush=True)
            return False
        device_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory // 1024 // 1024 // 1024
        print(f"[Q-Route] GPU: {device_name} ({vram}GB)", flush=True)
    except:
        print("[Q-Route] No torch — using Fireworks fallback", flush=True)
        return False

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        print(f"[Q-Route] Loading {GEMMA_MODEL}...", flush=True)
        t0 = time.time()
        _tokenizer = AutoTokenizer.from_pretrained(GEMMA_MODEL)
        _model = AutoModelForCausalLM.from_pretrained(
            GEMMA_MODEL, torch_dtype=torch.bfloat16, device_map="auto",
        )
        _model.eval()
        _gpu_ok = True
        print(f"[Q-Route] Gemma loaded in {time.time()-t0:.1f}s", flush=True)
        return True
    except Exception as e:
        print(f"[Q-Route] Gemma load failed: {e}", flush=True)
        return False

def run_local(query):
    """Inference on MI300X via transformers (0 Fireworks tokens)."""
    if not _gpu_ok:
        return ""
    try:
        import torch
        messages = [{"role": "user", "content": query}]
        inputs = _tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to(_model.device)
        with torch.no_grad():
            outputs = _model.generate(inputs, max_new_tokens=200, temperature=0.1, do_sample=True)
        return _tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True).strip()
    except Exception as e:
        print(f"[Q-Route] Local error: {e}", flush=True)
        return ""

# ---------------------------------------------------------------------------
# Fireworks (single best model for token efficiency)
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

    print(f"[Q-Route] Processing {len(tasks)} queries...", flush=True)

    gemma_ok = init_gemma()

    simple_tasks = []
    complex_tasks = []
    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        category = _detect_category(prompt)
        if category in SIMPLE_CATEGORIES and gemma_ok:
            simple_tasks.append((task_id, prompt, category))
        else:
            complex_tasks.append((task_id, prompt, category))

    print(f"[Q-Route] {len(simple_tasks)} local (Gemma) + {len(complex_tasks)} remote (Fireworks)", flush=True)

    results_map = {}

    def do_local(task_info):
        global _current_task_id
        tid, prompt, cat = task_info
        _current_task_id = tid
        ans = run_local(prompt)
        if ans and len(ans.strip()) > 10:
            print(f"[Q-Route] {tid}: LOCAL ({cat}) — 0 tokens", flush=True)
            _record_usage(tid, "local")
            return tid, ans
        print(f"[Q-Route] {tid}: LOCAL failed → FIREWORKS", flush=True)
        return tid, run_fireworks(prompt)

    def do_remote(task_info):
        global _current_task_id
        tid, prompt, cat = task_info
        _current_task_id = tid
        print(f"[Q-Route] {tid}: FIREWORKS ({cat})", flush=True)
        return tid, run_fireworks(prompt)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(do_local, t) for t in simple_tasks]
        futures += [pool.submit(do_remote, t) for t in complex_tasks]
        for f in as_completed(futures):
            tid, ans = f.result()
            results_map[tid] = ans

    results = []
    for task in tasks:
        tid = task.get("task_id")
        results.append({"task_id": tid, "answer": results_map.get(tid, "[No answer]")})

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
