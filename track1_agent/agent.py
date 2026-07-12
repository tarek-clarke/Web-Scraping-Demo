"""
agent.py — Track 1: Multi-Model Gemma 4 Ensemble on MI300X (0 Fireworks tokens).

Loads multiple Gemma 4 models from HuggingFace cache (cached by scoring env).
Each model votes with temperature diversity. Consensus = 0 tokens.
Falls back to Fireworks single-model if no GPU/no cached models.
"""
from __future__ import annotations
import json, os, re, sys, time, gc
from collections import Counter

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
ALLOWED_MODELS = [m.strip() for m in os.environ.get("ALLOWED_MODELS", "").split(",") if m.strip()]
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

GEMMA_MODELS = [
    "google/gemma-4-E4B-it",
    "google/gemma-4-12B-it",
    "google/gemma-4-26B-A4B-it",
]

_stats = {"total_tokens": 0, "local": 0, "remote": 0, "per_task": []}
_current_task_id = None
_models = []  # [(model, tokenizer, name), ...]
_gpu_ok = False
_TEMPS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]

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
# Load Multiple Gemma 4 Models from HF Cache
# ---------------------------------------------------------------------------

def init_models():
    global _models, _gpu_ok
    try:
        import torch
        if not torch.cuda.is_available():
            print("[Q-Route] No GPU — Fireworks fallback", flush=True)
            return False
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory // 1024 // 1024 // 1024
        print(f"[Q-Route] GPU: {name} ({vram}GB)", flush=True)
    except Exception as e:
        print(f"[Q-Route] torch not available: {e} — Fireworks fallback", flush=True)
        return False

    from transformers import AutoModelForCausalLM, AutoTokenizer

    for model_name in GEMMA_MODELS:
        try:
            t0 = time.time()
            tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.bfloat16, device_map="auto", local_files_only=True,
            )
            model.eval()
            _models.append((model, tokenizer, model_name))
            print(f"[Q-Route] Loaded {model_name} in {time.time()-t0:.1f}s", flush=True)
        except Exception:
            print(f"[Q-Route] {model_name.split('/')[-1]} not cached — skipping", flush=True)

    if _models:
        _gpu_ok = True
        print(f"[Q-Route] {len(_models)} models loaded for ensemble", flush=True)
    else:
        print("[Q-Route] No models cached — Fireworks fallback", flush=True)

    return _gpu_ok

# ---------------------------------------------------------------------------
# Multi-Model Ensemble Inference
# ---------------------------------------------------------------------------

def infer_one(model, tokenizer, query, temp, max_tokens):
    try:
        import torch
        messages = [{"role": "user", "content": query}]
        inputs = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to(model.device)
        with torch.no_grad():
            outputs = model.generate(inputs, max_new_tokens=max_tokens, temperature=temp, do_sample=temp > 0, pad_token_id=tokenizer.eos_token_id)
        return tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True).strip()
    except Exception as e:
        print(f"[Q-Route] Inference error: {e}", flush=True)
        return ""

def ensemble_vote(query, category, max_tokens=400):
    """Run all models × 3 temperatures each. Consensus vote. 0 Fireworks tokens."""
    if not _gpu_ok or not _models:
        return None

    answers = []
    for model, tokenizer, name in _models:
        for i in range(3):
            ans = infer_one(model, tokenizer, query, _TEMPS[i % len(_TEMPS)], max_tokens)
            if ans and len(ans) > 5:
                answers.append((ans, name))

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

    normalized = [normalize(a, cat) for a, _ in answers]
    counts = Counter(normalized)
    most_common, count = counts.most_common(1)[0]
    threshold = max(2, int(len(answers) * 0.4))

    if count >= threshold:
        for i, nv in enumerate(normalized):
            if nv == most_common:
                return answers[i][0]
    # No consensus — return longest answer
    return max(answers, key=lambda x: len(x[0]))[0]

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

    print(f"[Q-Route] Processing {len(tasks)} queries...", flush=True)
    gemma_ok = init_models()

    results = []
    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        _current_task_id = task_id
        category = _detect_category(prompt)

        answer = None
        if gemma_ok:
            answer = ensemble_vote(prompt, category, max_tokens=400)
            if answer:
                print(f"[Q-Route] {task_id}: LOCAL ({category}) — 0 tokens", flush=True)
                _record_usage(task_id, "local")

        if answer is None:
            print(f"[Q-Route] {task_id}: FIREWORKS ({category})", flush=True)
            answer = run_fireworks(prompt)

        results.append({"task_id": task_id, "answer": answer})

    # Cleanup
    for model, _, _ in _models:
        try:
            del model
        except: pass
    _models.clear()
    gc.collect()
    try:
        import torch; torch.cuda.empty_cache()
    except: pass

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
