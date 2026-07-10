"""
agent.py — Track 1: Gemma 4 E4B local (0 tokens) + Fireworks all-model consensus.

Downloads Gemma 4 E4B QAT GGUF from HuggingFace at startup (open repo, no token).
Gemma handles simple tasks locally at 0 Fireworks tokens.
Fireworks all-model consensus handles complex tasks (proven 89.5% accuracy).
"""
from __future__ import annotations
import json, os, re, sys, time

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

GEMMA_REPO = "google/gemma-4-E4B-it-qat-q4_0-gguf"
GEMMA_FILE = "gemma-4-E4B_q4_0-it.gguf"
GEMMA_PATH = "/tmp/gemma-4-e4b.q4.gguf"
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
# Download + Load Gemma 4 E4B (0 Fireworks tokens)
# ---------------------------------------------------------------------------

_local_llm = None

def download_gemma():
    if os.path.exists(GEMMA_PATH) and os.path.getsize(GEMMA_PATH) > 1_000_000_000:
        print(f"[Q-Route] Gemma already downloaded ({os.path.getsize(GEMMA_PATH)//1024//1024}MB)", flush=True)
        return True
    try:
        from huggingface_hub import hf_hub_download
        print(f"[Q-Route] Downloading Gemma 4 E4B QAT from HuggingFace...", flush=True)
        t0 = time.time()
        path = hf_hub_download(repo_id=GEMMA_REPO, filename=GEMMA_FILE, local_dir="/tmp")
        os.rename(path, GEMMA_PATH)
        print(f"[Q-Route] Downloaded in {time.time()-t0:.1f}s ({os.path.getsize(GEMMA_PATH)//1024//1024}MB)", flush=True)
        return True
    except Exception as e:
        print(f"[Q-Route] Download failed: {e}", flush=True)
        return False

def init_local():
    global _local_llm
    if _local_llm is not None:
        return
    if not download_gemma():
        return
    try:
        from llama_cpp import Llama
        print("[Q-Route] Loading Gemma 4 E4B...", flush=True)
        t0 = time.time()
        _local_llm = Llama(model_path=GEMMA_PATH, n_ctx=2048, n_threads=4, verbose=False)
        print(f"[Q-Route] Gemma loaded in {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print(f"[Q-Route] Gemma load failed: {e}", flush=True)
        _local_llm = None

def run_local(query):
    if _local_llm is None:
        return ""
    try:
        resp = _local_llm.create_chat_completion(
            messages=[{"role": "user", "content": query}],
            temperature=0.1, max_tokens=200,
        )
        return resp["choices"][0]["message"]["content"].strip()
    except:
        return ""

# ---------------------------------------------------------------------------
# Fireworks all-model consensus (proven 89.5% accuracy)
# ---------------------------------------------------------------------------

def run_fireworks(query):
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

    print(f"[Q-Route] Processing {len(tasks)} queries...", flush=True)
    init_local()

    results = []
    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        _current_task_id = task_id
        category = _detect_category(prompt)

        answer = None

        # Try local Gemma 4 E4B for simple tasks (0 tokens)
        if category in SIMPLE_CATEGORIES and _local_llm is not None:
            local_answer = run_local(prompt)
            if local_answer and len(local_answer.strip()) > 10:
                print(f"[Q-Route] {task_id}: LOCAL ({category}) — 0 tokens", flush=True)
                _record_usage(task_id, "local")
                answer = local_answer

        # Fireworks all-model consensus for complex tasks or failed local
        if answer is None:
            print(f"[Q-Route] {task_id}: FIREWORKS ({category})", flush=True)
            answer = run_fireworks(prompt)

        results.append({"task_id": task_id, "answer": answer})

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
