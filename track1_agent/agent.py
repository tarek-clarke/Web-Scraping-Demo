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

# Local model identifier (cost = $0 tokens)
LOCAL_MODEL_ID = os.environ.get("LOCAL_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
LOCAL_MODEL_PATH = os.environ.get("LOCAL_MODEL_PATH", "/app/hf_cache/models--Qwen--Qwen2.5-1.5B-Instruct/snapshots/latest")

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
# Local Model Inference (Cost = 0 Tokens)
# ---------------------------------------------------------------------------

_local_model = None
_local_tokenizer = None


def _init_local_model():
    global _local_model, _local_tokenizer
    if _local_model is not None:
        return

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        _local_tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH)

        if torch.cuda.is_available() or hasattr(torch, 'hip'):
            print("[Q-Route] GPU detected, loading with bfloat16")
            _local_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_MODEL_PATH,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
        else:
            print("[Q-Route] No GPU, loading with float32 on CPU")
            _local_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_MODEL_PATH,
                torch_dtype=torch.float32,
                device_map="cpu",
            )
        _local_model.eval()
    except Exception as e:
        print(f"[Q-Route] Local model load failed: {e}")
        _local_model = None
        _local_tokenizer = None


def run_local_model(query: str) -> str:
    """Run inference on local model. Cost = $0 tokens."""
    _init_local_model()

    if _local_model is None or _local_tokenizer is None:
        return f"[Local model fallback for query: '{query[:50]}']"

    try:
        import torch
        messages = [{"role": "user", "content": query}]
        input_ids = _local_tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True
        ).to(_local_model.device)

        with torch.no_grad():
            output = _local_model.generate(
                input_ids,
                max_new_tokens=256,
                temperature=0.1,
                do_sample=True,
            )

        response_ids = output[0][input_ids.shape[1]:]
        answer = _local_tokenizer.decode(response_ids, skip_special_tokens=True)
        return answer.strip()
    except Exception as e:
        print(f"[Q-Route] Local inference error: {type(e).__name__}: {e}")
        return f"[Local inference error: {e}]"


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


def run_remote_model(query: str) -> str:
    """Run inference on Fireworks AI API using injected variables."""
    if not FIREWORKS_API_KEY:
        _record_usage(_current_task_id or "?", "remote")
        return "[FIREWORKS_API_KEY environment variable missing]"

    try:
        import openai

        client = openai.OpenAI(
            base_url=FIREWORKS_BASE_URL,
            api_key=FIREWORKS_API_KEY,
        )

        model = ALLOWED_MODELS[0]

        system_prompt = (
            "Output ONLY the final answer. NO reasoning, NO 'We are given', NO 'Let me', NO explanations. "
            "Code tasks: only code block. Logic: only solution like 'Pos1=Alice, Pos2=Bob...'. Math: only answer."
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.1,
            max_tokens=256,
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
    if re.search(r"bug|debug|fix.*code|error.*in.*code|what'?s wrong", q):
        return "code_debug"
    if re.search(r"def\s+\w+|function|write.*(?:code|program|script)|implement", q):
        return "code_gen"
    if re.search(r"```|import\s+\w+|class\s+\w+", q):
        return "code_debug"
    if re.search(r"solve|calculat|arithmet|percent|equation|\d+\s*[\+\-\*\/]\s*\d+|if.*then.*how", q):
        return "math"
    if re.search(r"logic|puzzle|constraint|deduc|who.*lives|arrangement", q):
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

def process_task(prompt: str, router: BinaryQuantumRouter,
                 extractor: QueryFeatureExtractor) -> str:
    global _current_task_id
    features = extractor.extract(prompt)
    route_decision, confidence = router.route(features)

    print(f"[Q-Route] Task {_current_task_id}: VQC={route_decision} (conf={confidence:.2f})")

    if route_decision == "local" and confidence >= CONFIDENCE_THRESHOLD:
        draft = run_local_model(prompt)
        eval_score = local_eval(prompt, draft)
        print(f"[Q-Route] Task {_current_task_id}: local_eval={eval_score:.2f}, draft={draft[:120]!r}")

        if eval_score >= QUALITY_THRESHOLD and len(draft.strip()) > 10:
            return run_fireworks_confirm(prompt, draft)
        else:
            return run_remote_model(prompt)
    else:
        return run_remote_model(prompt)


def run_fireworks_confirm(prompt: str, draft: str) -> str:
    if not FIREWORKS_API_KEY:
        _record_usage(_current_task_id or "?", "local")
        return draft

    try:
        import openai

        client = openai.OpenAI(
            base_url=FIREWORKS_BASE_URL,
            api_key=FIREWORKS_API_KEY,
        )

        model = ALLOWED_MODELS[0]

        system_prompt = (
            "You are a verification layer for an LLM-Judge evaluation harness. "
            "Your goal: maximize accuracy with minimum tokens.\n\n"
            "DOMAINS: Factual, Math, Sentiment, Summarization, NER, Code Debug, Logic, Code Gen.\n\n"
            "RULES:\n"
            "1. If the draft is correct, output it EXACTLY as-is. No filler, no preambles.\n"
            "2. If the draft is wrong/incomplete, output ONLY the corrected answer.\n"
            "3. For code tasks: output only the code block, no explanations.\n"
            "4. For math: output only the final numeric answer and brief steps.\n"
            "5. For logic: output only the final solution.\n"
            "6. Never output reasoning, meta-commentary, or phrases like 'We are asked' or 'Let me'.\n"
            "7. If JSON is required, output only valid JSON.\n"
        )

        user_content = (
            f"[TASK PROMPT]:\n{prompt[:500]}\n\n"
            f"[LOCAL DRAFT ANSWER]:\n{draft[:800]}\n\n"
            f"Final High-Accuracy Solution:"
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=256,
        )
        _record_usage(_current_task_id or "?", "remote", response.usage)
        return response.choices[0].message.content.strip()
    except Exception:
        _record_usage(_current_task_id or "?", "local")
        return draft


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
