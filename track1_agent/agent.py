"""
agent.py — Track 1: Hybrid Token-Efficient Routing Agent (Q-Route Agent).

An AI agent designed to handle a wide variety of natural language tasks
across multiple capability domains, using local CPU/GPU models (cost = 0)
or Fireworks AI API models as efficiently as possible.

Complies fully with the AMD Developer Hackathon submission specifications:
1. Reads tasks from /input/tasks.json on startup
2. Writes results to /output/results.json before exiting
3. Routes Fireworks calls through FIREWORKS_BASE_URL environment variable
4. Dynamically selects models from the ALLOWED_MODELS environment variable list
5. Returns exit code 0 on success, non-zero on failure
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add parent directory to path so we can import src.routing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from query_feature_extractor import QueryFeatureExtractor


# ---------------------------------------------------------------------------
# Dynamic Environment Configurations (Injected by Harness at Runtime)
# ---------------------------------------------------------------------------

FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")

# ALLOWED_MODELS contains a comma-separated list of permitted model IDs
ALLOWED_MODELS_ENV = os.environ.get("ALLOWED_MODELS", "")
ALLOWED_MODELS = [m.strip() for m in ALLOWED_MODELS_ENV.split(",") if m.strip()]

# Default fallbacks if launch day environment variables are missing
if not ALLOWED_MODELS:
    ALLOWED_MODELS = ["accounts/fireworks/models/deepseek-v4-pro"]

# Local model identifier (not used — Gemma GGUF is loaded directly)
LOCAL_MODEL_ID = os.environ.get("LOCAL_MODEL_ID", "gemma-3-4b")

# Router confidence and local quality thresholds
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.50"))
QUALITY_THRESHOLD = float(os.environ.get("QUALITY_THRESHOLD", "0.45"))


# ---------------------------------------------------------------------------
# Quantum Router (Binary: Local=0, Remote=1)
# ---------------------------------------------------------------------------

class BinaryQuantumRouter:
    """Lightweight VQC router for binary local/remote classification.

    Uses 10 feature qubits + 1 output qubit = 11 total qubits.
    Class 0 = route to local model (cost = $0).
    Class 1 = route to remote Fireworks AI API (cost = tokens).
    """

    def __init__(self, shots: int = 1024):
        self.shots = shots
        self.feature_count = 10
        self.num_output_qubits = 1
        self._backend = None

    def _init_backend(self):
        """Lazy-initialize the Aer simulator."""
        try:
            from qiskit_aer import AerSimulator
            self._backend = AerSimulator()
        except ImportError:
            self._backend = None

    def route(self, features: np.ndarray) -> Tuple[str, float]:
        """Route a query based on its feature vector.

        Returns
        -------
        tuple of (str, float)
            ``("local", confidence)`` or ``("remote", confidence)``.
        """
        if self._backend is None:
            self._init_backend()

        if self._backend is None:
            return self._classical_fallback(features)

        try:
            return self._quantum_route(features)
        except Exception:
            return self._classical_fallback(features)

    def _quantum_route(self, features: np.ndarray) -> Tuple[str, float]:
        """Execute the VQC circuit for binary routing."""
        from qiskit.circuit import QuantumCircuit
        from qiskit.circuit.library import ZZFeatureMap, RealAmplitudes
        from qiskit import transpile

        num_qubits = self.feature_count + self.num_output_qubits
        qc = QuantumCircuit(num_qubits, self.num_output_qubits)

        # Feature encoding on first 10 qubits
        feature_map = ZZFeatureMap(feature_dimension=self.feature_count, reps=2)
        qc.compose(feature_map, qubits=list(range(self.feature_count)), inplace=True)

        # Trainable ansatz on all qubits
        ansatz = RealAmplitudes(num_qubits=num_qubits, reps=2)
        qc.compose(ansatz, inplace=True)

        # Measure only the output qubit
        qc.measure([self.feature_count], [0])

        # Bind feature parameters
        feature_params = sorted(
            [p for p in qc.parameters if p.name.startswith("x")],
            key=lambda p: p.name,
        )
        trainable_params = sorted(
            [p for p in qc.parameters if not p.name.startswith("x")],
            key=lambda p: p.name,
        )

        param_dict = {}
        for p, v in zip(feature_params, features):
            param_dict[p] = float(v)
        for p in trainable_params:
            param_dict[p] = 0.0

        bound = qc.assign_parameters(param_dict)
        transpiled = transpile(bound, self._backend)
        job = self._backend.run(transpiled, shots=self.shots)
        counts = job.result().get_counts()

        count_0 = counts.get("0", 0)  # local
        count_1 = counts.get("1", 0)  # remote

        if count_0 >= count_1:
            confidence = count_0 / self.shots
            return "local", confidence
        else:
            confidence = count_1 / self.shots
            return "remote", confidence

    @staticmethod
    def _classical_fallback(features: np.ndarray) -> Tuple[str, float]:
        """Heuristic fallback when quantum simulator library is unavailable."""
        import math

        token_estimate = features[1] / math.pi
        has_code = features[4] / math.pi
        complexity = features[6] / math.pi

        score = 0.3 * token_estimate + 0.4 * has_code + 0.3 * complexity
        if score > 0.45:
            return "remote", 0.7 + 0.3 * min(score, 1.0)
        else:
            return "local", 0.7 + 0.3 * (1.0 - score)


# ---------------------------------------------------------------------------
# Local Model Inference (Cost = 0 Fireworks Tokens)
# Gemma 3 GGUF via llama-cpp-python
# ---------------------------------------------------------------------------

_gemma_1b = None
_gemma_4b = None

GEMMA_1B_PATH = "/app/gemma_cache/google_gemma-3-1b-it-Q4_K_M.gguf"
GEMMA_4B_PATH = "/app/gemma_cache/google_gemma-3-4b-it-Q4_K_M.gguf"


def _init_gemma_1b():
    global _gemma_1b
    if _gemma_1b is not None:
        return
    try:
        from llama_cpp import Llama
        print("[Q-Route] Loading Gemma 3 1B GGUF...")
        _gemma_1b = Llama(model_path=GEMMA_1B_PATH, n_ctx=2048, n_threads=4, verbose=False)
        print("[Q-Route] Gemma 3 1B loaded.")
    except Exception as e:
        print(f"[Q-Route] Gemma 1B load failed: {e}")
        _gemma_1b = None


def _init_gemma_4b():
    global _gemma_4b
    if _gemma_4b is not None:
        return
    try:
        from llama_cpp import Llama
        print("[Q-Route] Loading Gemma 3 4B GGUF...")
        _gemma_4b = Llama(model_path=GEMMA_4B_PATH, n_ctx=4096, n_threads=4, verbose=False)
        print("[Q-Route] Gemma 3 4B loaded.")
    except Exception as e:
        print(f"[Q-Route] Gemma 4B load failed: {e}")
        _gemma_4b = None


def run_local_model(query: str, use_4b: bool = True) -> str:
    """Run inference on local Gemma. Cost = 0 Fireworks tokens."""
    if use_4b:
        _init_gemma_4b()
        llm = _gemma_4b
    else:
        _init_gemma_1b()
        llm = _gemma_1b

    if llm is None:
        if not use_4b:
            return ""
        _init_gemma_1b()
        llm = _gemma_1b
        if llm is None:
            return ""

    try:
        response = llm.create_chat_completion(
            messages=[{"role": "user", "content": query}],
            temperature=0.1,
            max_tokens=512,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[Q-Route] Local inference error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Token & Routing Statistics Tracker
# ---------------------------------------------------------------------------

_stats = {
    "total_tasks": 0,
    "routed_local": 0,
    "routed_remote": 0,
    "fireworks_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "per_task": [],
}


def _record_usage(task_id: str, route: str, usage=None):
    entry = {
        "task_id": task_id,
        "route": route,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    if usage:
        entry["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
        entry["completion_tokens"] = getattr(usage, "completion_tokens", 0) or 0
        entry["total_tokens"] = getattr(usage, "total_tokens", 0) or 0
        _stats["prompt_tokens"] += entry["prompt_tokens"]
        _stats["completion_tokens"] += entry["completion_tokens"]
        _stats["total_tokens"] += entry["total_tokens"]
    if route == "local":
        _stats["routed_local"] += 1
    else:
        _stats["routed_remote"] += 1
        _stats["fireworks_calls"] += 1
    _stats["total_tasks"] += 1
    _stats["per_task"].append(entry)


def _print_stats():
    print("\n" + "=" * 60)
    print("[Q-Route] ROUTING & TOKEN USAGE SUMMARY")
    print("=" * 60)
    print(f"  Total tasks processed : {_stats['total_tasks']}")
    print(f"  Routed to LOCAL (free): {_stats['routed_local']}")
    print(f"  Routed to REMOTE      : {_stats['routed_remote']}")
    print(f"  Fireworks API calls   : {_stats['fireworks_calls']}")
    print(f"  Prompt tokens         : {_stats['prompt_tokens']}")
    print(f"  Completion tokens     : {_stats['completion_tokens']}")
    print(f"  TOTAL tokens          : {_stats['total_tokens']}")
    print("-" * 60)
    for t in _stats["per_task"]:
        tag = "LOCAL" if t["route"] == "local" else "REMOTE"
        tok = t["total_tokens"]
        print(f"  [{tag}] {t['task_id']}: {tok} tokens (prompt={t['prompt_tokens']}, completion={t['completion_tokens']})")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Remote Model Inference (Fireworks AI)
# ---------------------------------------------------------------------------

_current_task_id = None


def _fireworks_inference(query: str, system_prompt: str, max_tokens: int = 500, model: str = None) -> str:
    """Call Fireworks API via chat completions."""
    import openai

    client = openai.OpenAI(
        base_url=FIREWORKS_BASE_URL,
        api_key=FIREWORKS_API_KEY,
    )

    if model is None:
        model = ALLOWED_MODELS[0]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    _record_usage(_current_task_id or "?", "remote", response.usage)
    return response.choices[0].message.content.strip()


MAX_TOKENS_PER_CATEGORY = {
    "sentiment": 200,
    "math": 500,
    "factual": 400,
    "summarization": 300,
    "ner": 300,
    "code_debug": 600,
    "code_gen": 600,
    "logic": 500,
}

SYSTEM_PROMPTS = {
    "default": "You are an AI assistant. Answer the user's question accurately and completely. Provide full, detailed answers.",
    "sentiment": "You are an AI assistant. Classify the sentiment as positive, negative, or neutral, and provide a brief justification for your classification.",
    "math": "You are an AI assistant. Solve the math problem step by step and clearly state the final answer.",
    "logic": "You are an AI assistant. Solve the logic puzzle step by step and clearly state the final answer.",
    "code_debug": "You are an AI assistant. Identify the bug in the code, explain it, and provide the corrected code.",
    "code_gen": "You are an AI assistant. Write the requested code with any necessary imports. Provide a complete, working solution.",
    "ner": "You are an AI assistant. Extract all named entities from the text and label each as Person, Organization, Location, or Date.",
    "summarization": "You are an AI assistant. Summarize the text as requested.",
    "factual": "You are an AI assistant. Answer the question accurately and completely.",
}


_selected_model = None

def _pick_best_model(client, query):
    """Test all models on first task, pick the one with the longest answer."""
    global _selected_model
    if _selected_model is not None:
        return _selected_model

    best_model = ALLOWED_MODELS[0]
    best_len = 0

    for model in ALLOWED_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant. Answer accurately and completely."},
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            answer = response.choices[0].message.content.strip()
            print(f"[Q-Route] Model test: {model} -> len={len(answer)}")
            if len(answer) > best_len:
                best_len = len(answer)
                best_model = model
                _record_usage(_current_task_id or "?", "remote", response.usage)
        except Exception as e:
            print(f"[Q-Route] Model test: {model} failed: {e}")

    _selected_model = best_model
    print(f"[Q-Route] Selected model: {_selected_model}")
    return _selected_model


FEW_SHOT_EXAMPLES = {
    "sentiment": [
        {"role": "user", "content": "What is the sentiment of this review: 'The food was amazing and the staff was friendly!'"},
        {"role": "assistant", "content": "Positive. The reviewer expresses satisfaction with both the food quality and the staff service, using strong positive words like 'amazing' and 'friendly.'"},
    ],
    "math": [
        {"role": "user", "content": "A book costs $20. With a 10% discount, what is the final price?"},
        {"role": "assistant", "content": "The final price is $18.\n\nStep 1: Discount = 10% of $20 = $2\nStep 2: Final price = $20 - $2 = $18"},
    ],
    "ner": [
        {"role": "user", "content": "Extract named entities from: 'John Smith works at Google in New York since 2020.'"},
        {"role": "assistant", "content": "Person: John Smith\nOrganization: Google\nLocation: New York\nDate: 2020"},
    ],
    "logic": [
        {"role": "user", "content": "If A > B and B > C, who is the tallest?"},
        {"role": "assistant", "content": "A is the tallest. Since A > B and B > C, the order from tallest to shortest is A, B, C."},
    ],
    "code_debug": [
        {"role": "user", "content": "Fix the bug: def add(a, b): return a - b"},
        {"role": "assistant", "content": "The bug is that the function uses subtraction (-) instead of addition (+).\n\nCorrected code:\n```python\ndef add(a, b):\n    return a + b\n```"},
    ],
    "code_gen": [
        {"role": "user", "content": "Write a function that returns the square of a number."},
        {"role": "assistant", "content": "```python\ndef square(n):\n    return n * n\n```"},
    ],
    "summarization": [
        {"role": "user", "content": "Summarize in one sentence: 'The sun is a star at the center of the solar system. It provides light and heat to all planets.'"},
        {"role": "assistant", "content": "The sun is the central star of the solar system that provides light and heat to all planets."},
    ],
}


def _pick_model_for_category(query: str) -> str:
    """Use deepseek for reasoning, kimi for code, fallback to first model."""
    category = _detect_category(query)
    
    if category in ("math", "logic"):
        for m in ALLOWED_MODELS:
            if "deepseek" in m.lower():
                return m
    if category in ("code_gen", "code_debug"):
        for m in ALLOWED_MODELS:
            if "kimi" in m.lower():
                return m
    if category in ("factual", "sentiment", "summarization", "ner"):
        for m in ALLOWED_MODELS:
            if "deepseek" in m.lower() or "kimi" in m.lower():
                return m
    
    return ALLOWED_MODELS[0]


def run_remote_model(query: str) -> str:
    if not FIREWORKS_API_KEY:
        _record_usage(_current_task_id or "?", "remote")
        return "[FIREWORKS_API_KEY environment variable missing]"

    import openai

    client = openai.OpenAI(
        base_url=FIREWORKS_BASE_URL,
        api_key=FIREWORKS_API_KEY,
    )

    system_prompt = "You are an expert AI assistant. Answer accurately and completely. For classification or extraction tasks, state the direct answer first. For math and logic problems, show your reasoning and then state the final answer explicitly at the end. For code, provide complete working code."
    
    model = _pick_model_for_category(query)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        _record_usage(_current_task_id or "?", "remote", response.usage)
        return response.choices[0].message.content.strip()
    except Exception as e:
        _record_usage(_current_task_id or "?", "remote")
        return f"[Fireworks API Error: {e}]"


# ---------------------------------------------------------------------------
# Local Quality Evaluation (Free) — Structural / Category-Aware Scorer
# ---------------------------------------------------------------------------

_ERROR_MARKERS = re.compile(
    r"\[.*error.*\]|\[.*fallback.*\]|i (?:don'?t|cannot|can'?t) (?:know|have|understand)",
    re.IGNORECASE,
)

_CODE_BLOCK = re.compile(r"```[\s\S]*?```")
_NUMERIC_ANSWER = re.compile(r"(?:^|\s|=|:)\s*-?\d+(?:\.\d+)?\s*(?:%|km/?h|kg|m|s|°|dollars?|euros?|\$)?\s*$", re.MULTILINE)
_SENTIMENT_LABEL = re.compile(r"\b(positive|negative|neutral|mixed)\b", re.IGNORECASE)
_ENTITY_PATTERN = re.compile(r"\b(?:person|org(?:anization)?|location|date|time|event)\b", re.IGNORECASE)


def _detect_category(query: str) -> str:
    q = query.lower()
    if re.search(r"sentiment|positive|negative|neutral|tone of", q):
        return "sentiment"
    if re.search(r"summar(?:ize|ise|y)|condense|in (?:one|a few) (?:sentence|word|paragraph)", q):
        return "summarization"
    if re.search(r"extract.*entit(?:y|ies)|named entity|ner\b|person.*org|label.*entit", q):
        return "ner"
    if re.search(r"bug|debug|fix.*code|error.*in.*code|what'?s wrong.*code|find.*bug", q):
        return "code_debug"
    if re.search(r"def\s+\w+|function|write.*(?:code|program|script)|implement", q):
        return "code_gen"
    if re.search(r"solve|calculat|arithmet|percent|discount|\d+\s*[\+\-\*\/]\s*\d+|if.*then.*how|how much|how many|total cost|average speed", q):
        return "math"
    if re.search(r"logic|puzzle|constraint|deduc|who.*lives|arrangement|sit.*in.*row|who sits where|friends.*sit|seating", q):
        return "logic"
    return "factual"


def local_eval(query: str, answer: str) -> float:
    if not answer or len(answer.strip()) < 3:
        return 0.0

    stripped = answer.strip()

    if _ERROR_MARKERS.search(stripped):
        return 0.0

    category = _detect_category(query)
    score = 0.40

    if len(stripped) >= 5:
        score += 0.10
    if len(stripped) >= 15:
        score += 0.05

    if category == "sentiment":
        if _SENTIMENT_LABEL.search(stripped):
            score += 0.30
        elif len(stripped) > 20:
            score += 0.10
    elif category == "math":
        if _NUMERIC_ANSWER.search(stripped):
            score += 0.30
        elif any(c.isdigit() for c in stripped):
            score += 0.15
    elif category in ("code_gen", "code_debug"):
        if _CODE_BLOCK.search(stripped):
            score += 0.30
        elif "def " in stripped or "class " in stripped or "return " in stripped:
            score += 0.20
    elif category == "ner":
        if _ENTITY_PATTERN.search(stripped):
            score += 0.25
        if ":" in stripped or "-" in stripped:
            score += 0.10
    elif category == "summarization":
        q_len = len(query)
        a_len = len(stripped)
        if a_len < q_len:
            score += 0.25
        else:
            score += 0.05
    elif category == "logic":
        if len(stripped) > 30:
            score += 0.15
        if any(w in stripped.lower() for w in ["because", "therefore", "since", "thus", "so "]):
            score += 0.15
    else:
        if len(stripped) > 10:
            score += 0.15
        query_words = set(query.lower().split())
        answer_words = set(stripped.lower().split())
        overlap = len(query_words & answer_words)
        if overlap >= 3:
            score += 0.10

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Process Query Pipeline
# ---------------------------------------------------------------------------

SIMPLE_CATEGORIES = {"factual", "sentiment", "summarization", "ner"}
COMPLEX_CATEGORIES = {"math", "code_debug", "code_gen", "logic"}


def process_task(prompt: str, router: BinaryQuantumRouter,
                 extractor: QueryFeatureExtractor) -> str:
    global _current_task_id
    
    features = extractor.extract(prompt)
    route_decision, confidence = router.route(features)
    category = _detect_category(prompt)

    print(f"[Q-Route] Task {_current_task_id}: cat={category} VQC={route_decision} (conf={confidence:.2f})")

    if category in SIMPLE_CATEGORIES:
        use_4b = category != "sentiment"
        local_answer = run_local_model(prompt, use_4b=use_4b)
        
        if local_answer and len(local_answer.strip()) > 10:
            print(f"[Q-Route] Task {_current_task_id}: LOCAL answer (0 tokens), len={len(local_answer)}")
            _record_usage(_current_task_id or "?", "local")
            return local_answer
        else:
            print(f"[Q-Route] Task {_current_task_id}: LOCAL failed, escalating to Fireworks")
            return run_remote_model(prompt)
    else:
        return run_remote_model(prompt)


def run_fireworks_confirm(prompt: str, draft: str) -> str:
    if not FIREWORKS_API_KEY:
        _record_usage(_current_task_id or "?", "local")
        return draft

    try:
        category = _detect_category(prompt)
        system_prompt = SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["default"])
        max_tokens = MAX_TOKENS_PER_CATEGORY.get(category, 200)

        user_content = f"Q: {prompt[:300]}\nDraft: {draft[:500]}\nAnswer:"

        model = _select_model_for_query(prompt)
        return _fireworks_inference(user_content, system_prompt, max_tokens=max_tokens, model=model)
    except Exception:
        _record_usage(_current_task_id or "?", "local")
        return draft


# ---------------------------------------------------------------------------
# Output Cleaner — strips non-essential tokens before writing to JSON
# ---------------------------------------------------------------------------

_RE_FENCE_START = re.compile(r"^\s*```[a-zA-Z]*\s*\n?", re.MULTILINE)
_RE_FENCE_END = re.compile(r"\n?```\s*$", re.MULTILINE)
_RE_SENTIMENT = re.compile(r"\b(positive|negative|neutral)\b", re.IGNORECASE)
_RE_DOLLAR = re.compile(r"\$[\d,]+(?:\.\d+)?")
_RE_NUMBER = re.compile(r"(?:^|\s|=|:)\s*(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:%|km/?h|kg|m|s|°|dollars?|euros?|\$|hours?|hrs?|minutes?|mins?|mph|miles?|feet|ft|seconds?|secs?)?\s*$", re.MULTILINE | re.IGNORECASE)
_RE_TRAILING_LINES = re.compile(r"\n{2,}$")
_RE_CARRIAGE = re.compile(r"\r")
_RE_CODE_START = re.compile(r"(^|\n)((?:def |import |from |class |#|@\w+))", re.MULTILINE)


def clean_target_output(text: str, category: str) -> str:
    if not text:
        return text

    raw_trimmed = text.strip()
    if not raw_trimmed:
        return text

    cleaned = _RE_CARRIAGE.sub("", text)

    if "```" in cleaned:
        lines = cleaned.split("\n")
        inside = False
        extracted = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("```") and not inside:
                inside = True
                continue
            elif stripped_line == "```" and inside:
                inside = False
                continue
            extracted.append(line)
        cleaned = "\n".join(extracted)

    cleaned = cleaned.strip()
    if not cleaned:
        return raw_trimmed
    cleaned = _RE_TRAILING_LINES.sub("\n", cleaned)

    return cleaned


# ---------------------------------------------------------------------------
# Main Execution Entrypoint
# ---------------------------------------------------------------------------

def main():
    global _current_task_id
    input_path = "/input/tasks.json"
    output_path = "/output/results.json"

    # If directories don't exist, fallback to local directory paths for development
    if not os.path.exists("/input"):
        input_path = "tasks.json"
    if not os.path.exists("/output"):
        output_path = "results.json"

    # Verify input task list exists
    if not os.path.exists(input_path):
        print(f"[Q-Route] Input task list not found at {input_path}")
        sys.exit(1)

    try:
        with open(input_path, "r") as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"[Q-Route] Failed to parse input JSON: {e}")
        sys.exit(1)

    print(f"[Q-Route] Initializing router. Processing {len(tasks)} queries...")
    extractor = QueryFeatureExtractor()
    router = BinaryQuantumRouter(shots=1024)
    
    results = []

    for task in tasks:
        task_id = task.get("task_id")
        prompt = task.get("prompt", "")
        _current_task_id = task_id

        answer = process_task(prompt, router, extractor)

        results.append({
            "task_id": task_id,
            "answer": answer
        })

    _print_stats()

    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[Q-Route] Successfully wrote {len(results)} results to {output_path}")
        sys.exit(0)
    except Exception as e:
        print(f"[Q-Route] Failed to write results JSON: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
