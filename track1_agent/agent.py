"""
agent.py — Track 1: 100% Local Gemma 4 E4B. 0 Fireworks tokens.

Baked-in model. No downloads. No API calls. Pure local consensus.
"""
from __future__ import annotations
import json, os, re, sys, time, gc
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

GEMMA_PATH = "/models/gemma-3-4b.q4.gguf"
NUM_COPIES = 4
_TEMPS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]

_stats = {"local": 0, "per_task": []}
_instances = []

def _detect_category(query):
    q = query.lower()
    if re.search(r"sentiment|positive|negative|neutral|tone of", q): return "sentiment"
    if re.search(r"summar(?:ize|ise|y)|condense", q): return "summarization"
    if re.search(r"extract.*entit|named entity|ner|person.*org|label.*entit", q): return "ner"
    if re.search(r"bug|debug|fix.*code|error.*in.*code|find.*bug", q): return "code_debug"
    if re.search(r"def\s+\w+|function|write.*(?:code|program|script)|implement", q): return "code_gen"
    if re.search(r"solve|calculat|percent|discount|how much|how many|total cost", q): return "math"
    if re.search(r"logic|puzzle|constraint|deduc|arrangement|seating", q): return "logic"
    return "factual"

# ---------------------------------------------------------------------------
# Load Gemma 4 E4B — baked in, 0 downloads
# ---------------------------------------------------------------------------

def init_gemma():
    global _instances
    if _instances:
        return True
    try:
        from llama_cpp import Llama
        print(f"[Q-Route] Loading {NUM_COPIES}× Gemma 4 E4B...", flush=True)
        t0 = time.time()
        for i in range(NUM_COPIES):
            # Try GPU first, fall back to CPU
            try:
                llm = Llama(model_path=GEMMA_PATH, n_ctx=2048, n_threads=4, n_gpu_layers=-1, verbose=False)
            except:
                llm = Llama(model_path=GEMMA_PATH, n_ctx=2048, n_threads=4, n_gpu_layers=0, verbose=False)
            _instances.append(llm)
            print(f"[Q-Route] Copy {i+1}/{NUM_COPIES} loaded", flush=True)
        print(f"[Q-Route] All loaded in {time.time()-t0:.1f}s", flush=True)
        return True
    except Exception as e:
        print(f"[Q-Route] Gemma load failed: {e}", flush=True)
        return False

def infer_one(idx, query, max_tokens=200):
    if idx >= len(_instances):
        return ""
    try:
        temp = _TEMPS[idx % len(_TEMPS)]
        resp = _instances[idx].create_chat_completion(
            messages=[{"role": "user", "content": query}],
            temperature=temp, max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"].strip()
    except:
        return ""

def ensemble_vote(query, category, max_tokens=200):
    n = len(_instances)
    with ThreadPoolExecutor(max_workers=n) as pool:
        answers = list(pool.map(lambda i: infer_one(i, query, max_tokens), range(n)))
    answers = [a for a in answers if a and len(a) > 5]
    if not answers:
        return None

    def normalize(text, cat):
        t = text.lower().strip()
        if cat == "sentiment":
            for label in ["positive", "negative", "neutral"]:
                if label in t: return label
        elif cat == "math":
            nums = re.findall(r'\$?[\d,]+(?:\.\d+)?', t)
            return nums[-1] if nums else ""
        elif cat == "ner":
            ents = re.findall(r'[\w\s]+(?=:|(?:\s*→))', t)
            return ",".join(sorted(set(e.strip().lower() for e in ents))) if ents else ""
        elif cat in ("code_gen", "code_debug"):
            funcs = re.findall(r'def\s+(\w+)', t)
            return ",".join(funcs) if funcs else ""
        words = set(t.split())
        return " ".join(sorted(list(words))[:10])

    normalized = [normalize(a, category) for a in answers]
    counts = Counter(normalized)
    mc, cnt = counts.most_common(1)[0]
    threshold = max(2, int(n * 0.5))

    if cnt >= threshold:
        for i, nv in enumerate(normalized):
            if nv == mc:
                return answers[i]
    return max(answers, key=len)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    input_path = "/input/tasks.json"
    output_path = "/output/results.json"
    if not os.path.exists("/input"): input_path = "tasks.json"
    if not os.path.exists("/output"): output_path = "results.json"

    if not os.path.exists(input_path):
        print(f"[Q-Route] Input not found: {input_path}")
        sys.exit(1)

    with open(input_path) as f:
        tasks = json.load(f)

    print(f"[Q-Route] Processing {len(tasks)} queries (0 tokens - local only)...", flush=True)

    if not init_gemma():
        print("[Q-Route] FAILED to load Gemma", flush=True)
        sys.exit(1)

    results = []
    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        category = _detect_category(prompt)
        max_tok = {"sentiment": 80, "ner": 150, "summarization": 200, "factual": 200,
                   "math": 300, "logic": 400, "code_gen": 400, "code_debug": 400}.get(category, 200)

        answer = ensemble_vote(prompt, category, max_tok)
        if answer:
            print(f"[Q-Route] {task_id}: LOCAL ({category}) — 0 tokens", flush=True)
            _stats["local"] += 1
        else:
            answer = "[Gemma failed]"
            print(f"[Q-Route] {task_id}: FAILED ({category})", flush=True)

        results.append({"task_id": task_id, "answer": answer})

    # Cleanup
    for llm in _instances:
        try: del llm
        except: pass
    _instances.clear()
    gc.collect()

    print(f"\n[Q-Route] SUMMARY: {_stats['local']}/{len(tasks)} local — 0 Fireworks tokens")
    print(f"[Q-Route] Wrote {len(results)} results to {output_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    sys.exit(0)

if __name__ == "__main__":
    main()
