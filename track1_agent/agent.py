"""
agent.py — Track 1: Gemma 4 via vLLM (0 tokens) + Fireworks single-model fallback.

Scoring env has ROCm 7.2 + vLLM 0.16.0 + PyTorch 2.9 pre-installed.
Starts vLLM server with Gemma 4 E4B on MI300X GPU.
Simple tasks answered locally at 0 Fireworks tokens.
Complex tasks sent to Fireworks (single best model for token efficiency).
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

GEMMA_MODEL = "google/gemma-4-E4B-it"
VLLM_PORT = 5555
VLLM_URL = f"http://localhost:{VLLM_PORT}/v1"

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
# vLLM Server (pre-installed on scoring env with ROCm 7.2)
# ---------------------------------------------------------------------------

_vllm_process = None
_vllm_ready = False

def start_vllm():
    """Start vLLM server with Gemma 4 E4B on GPU."""
    global _vllm_process, _vllm_ready

    # Check if vLLM is available
    try:
        result = subprocess.run(["python3", "-c", "import vllm; print(vllm.__version__)"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("[Q-Route] vLLM not available — using Fireworks fallback", flush=True)
            return False
        print(f"[Q-Route] vLLM {result.stdout.strip()} found", flush=True)
    except:
        print("[Q-Route] vLLM not available — using Fireworks fallback", flush=True)
        return False

    # Start vLLM server
    print(f"[Q-Route] Starting vLLM server with {GEMMA_MODEL}...", flush=True)
    t0 = time.time()

    cmd = [
        "python3", "-m", "vllm.entrypoints.openai.api_server",
        "--model", GEMMA_MODEL,
        "--port", str(VLLM_PORT),
        "--gpu-memory-utilization", "0.90",
        "--max-model-len", "4096",
        "--dtype", "bfloat16",
        "--trust-remote-code",
    ]

    _vllm_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for server to be ready
    import urllib.request
    for attempt in range(60):  # 60 seconds max
        try:
            req = urllib.request.urlopen(f"{VLLM_URL}/models", timeout=2)
            if req.status == 200:
                _vllm_ready = True
                print(f"[Q-Route] vLLM ready in {time.time()-t0:.1f}s", flush=True)
                return True
        except:
            pass
        time.sleep(1)

    print("[Q-Route] vLLM failed to start in 60s — using Fireworks fallback", flush=True)
    if _vllm_process:
        _vllm_process.kill()
        _vllm_process = None
    return False

def run_local_vllm(query):
    """Query local vLLM server (0 Fireworks tokens)."""
    if not _vllm_ready:
        return ""
    try:
        import urllib.request, json as _json
        data = _json.dumps({
            "model": GEMMA_MODEL,
            "messages": [{"role": "user", "content": query}],
            "temperature": 0.1,
            "max_tokens": 200,
        }).encode()
        req = urllib.request.Request(f"{VLLM_URL}/chat/completions", data=data,
                                    headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        result = _json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[Q-Route] vLLM inference error: {e}", flush=True)
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

    # Use only the best model to minimize tokens
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

    # Start vLLM with Gemma (uses pre-installed ROCm + vLLM on scoring env)
    vllm_ok = start_vllm()

    # Split tasks
    simple_tasks = []
    complex_tasks = []
    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        category = _detect_category(prompt)
        if category in SIMPLE_CATEGORIES and vllm_ok:
            simple_tasks.append((task_id, prompt, category))
        else:
            complex_tasks.append((task_id, prompt, category))

    print(f"[Q-Route] Split: {len(simple_tasks)} local (vLLM) + {len(complex_tasks)} remote (Fireworks)", flush=True)

    results_map = {}

    def process_local(task_info):
        global _current_task_id
        task_id, prompt, category = task_info
        _current_task_id = task_id
        answer = run_local_vllm(prompt)
        if answer and len(answer.strip()) > 10:
            print(f"[Q-Route] {task_id}: LOCAL ({category}) — 0 tokens", flush=True)
            _record_usage(task_id, "local")
            return task_id, answer
        # vLLM failed — fall back to Fireworks
        print(f"[Q-Route] {task_id}: LOCAL failed → FIREWORKS", flush=True)
        return task_id, run_fireworks(prompt)

    def process_remote(task_info):
        global _current_task_id
        task_id, prompt, category = task_info
        _current_task_id = task_id
        print(f"[Q-Route] {task_id}: FIREWORKS ({category})", flush=True)
        return task_id, run_fireworks(prompt)

    # Run both pipelines in parallel
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for t in simple_tasks:
            futures.append(pool.submit(process_local, t))
        for t in complex_tasks:
            futures.append(pool.submit(process_remote, t))

        for future in as_completed(futures):
            task_id, answer = future.result()
            results_map[task_id] = answer

    # Cleanup vLLM
    if _vllm_process:
        _vllm_process.kill()
        _vllm_process = None

    # Assemble results in order
    results = []
    for task in tasks:
        task_id = task.get("task_id")
        results.append({"task_id": task_id, "answer": results_map.get(task_id, "[No answer]")})

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
