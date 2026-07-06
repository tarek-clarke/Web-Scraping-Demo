"""
agent.py — Track 1: Hybrid Token-Efficient Routing Agent (Q-Route Agent).

A quantum-accelerated (VQC) model routing agent that autonomously decides
whether to serve each incoming task using a local model (cost = $0 tokens)
or the remote Fireworks AI API (cost = remote tokens).

Usage:
    # Interactive stdin mode
    python agent.py

    # Process a JSON tasks file
    python agent.py --input tasks.json

    # Self-test mode
    python agent.py --test

    # Set models via environment variables
    LOCAL_MODEL_ID=Qwen/Qwen2.5-7B-Instruct python agent.py
    FIREWORKS_MODEL_ID=accounts/fireworks/models/llama-v3-70b-instruct python agent.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add parent directory to path so we can import src.routing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from query_feature_extractor import QueryFeatureExtractor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOCAL_MODEL_ID = os.environ.get("LOCAL_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
FIREWORKS_MODEL_ID = os.environ.get(
    "FIREWORKS_MODEL_ID",
    "accounts/fireworks/models/llama-v3-70b-instruct",
)
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")

# Confidence threshold: if VQC confidence for "local" is below this,
# escalate to remote regardless of VQC class decision.
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.55"))

# Quality threshold: if local model's self-eval score is below this,
# re-route to remote.
QUALITY_THRESHOLD = float(os.environ.get("QUALITY_THRESHOLD", "0.6"))


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
            print("[Q-Route] Qiskit not installed. Using classical fallback.")
            self._backend = None

    def route(self, features: np.ndarray) -> Tuple[str, float]:
        """Route a query based on its feature vector.

        Parameters
        ----------
        features : np.ndarray
            Shape ``(10,)`` array in ``[0, π]``.

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
        except Exception as e:
            print(f"[Q-Route] Quantum circuit error: {e}. Using classical fallback.")
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
        # Initialize trainable params to 0 (untrained baseline)
        for p in trainable_params:
            param_dict[p] = 0.0

        bound = qc.assign_parameters(param_dict)
        transpiled = transpile(bound, self._backend)
        job = self._backend.run(transpiled, shots=self.shots)
        counts = job.result().get_counts()

        # Count votes for each class
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
        """Heuristic fallback when quantum backend is unavailable.

        Uses feature thresholds to determine query complexity:
        - Simple queries (short, no code, low complexity) -> local
        - Complex queries (long, code, high complexity) -> remote
        """
        import math

        # Denormalize key features from [0, π] back to [0, 1]
        char_length = features[0] / math.pi
        token_estimate = features[1] / math.pi
        has_code = features[4] / math.pi
        has_json = features[5] / math.pi
        complexity = features[6] / math.pi

        # Weighted complexity score
        score = (
            0.25 * token_estimate
            + 0.30 * has_code
            + 0.15 * has_json
            + 0.20 * complexity
            + 0.10 * char_length
        )

        if score > 0.45:
            return "remote", 0.7 + 0.3 * min(score, 1.0)
        else:
            return "local", 0.7 + 0.3 * (1.0 - score)


# ---------------------------------------------------------------------------
# Local Model Inference
# ---------------------------------------------------------------------------

_local_model = None
_local_tokenizer = None


def _init_local_model():
    """Lazy-load the local model using HuggingFace transformers."""
    global _local_model, _local_tokenizer
    if _local_model is not None:
        return

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        print(f"[Q-Route] Loading local model: {LOCAL_MODEL_ID}...")
        _local_tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_ID)
        _local_model = AutoModelForCausalLM.from_pretrained(
            LOCAL_MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        print(f"[Q-Route] Local model loaded successfully.")
    except Exception as e:
        print(f"[Q-Route] Failed to load local model: {e}")
        _local_model = None
        _local_tokenizer = None


def run_local_model(query: str) -> Dict:
    """Run inference on the local model. Cost = $0 tokens."""
    _init_local_model()

    if _local_model is None or _local_tokenizer is None:
        return {
            "answer": "[LOCAL MODEL UNAVAILABLE] " + query[:100],
            "tokens_used": 0,
            "latency_ms": 0.0,
            "source": "local_fallback",
        }

    t_start = time.perf_counter()

    messages = [{"role": "user", "content": query}]
    input_ids = _local_tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True
    ).to(_local_model.device)

    import torch
    with torch.no_grad():
        output = _local_model.generate(
            input_ids,
            max_new_tokens=512,
            temperature=0.1,
            do_sample=True,
        )

    response_ids = output[0][input_ids.shape[1]:]
    answer = _local_tokenizer.decode(response_ids, skip_special_tokens=True)
    latency = (time.perf_counter() - t_start) * 1000

    return {
        "answer": answer.strip(),
        "tokens_used": 0,  # Local tokens are FREE
        "latency_ms": latency,
        "source": "local",
    }


# ---------------------------------------------------------------------------
# Remote Model Inference (Fireworks AI)
# ---------------------------------------------------------------------------

def run_remote_model(query: str) -> Dict:
    """Run inference on Fireworks AI API. Cost = remote tokens."""
    if not FIREWORKS_API_KEY:
        return {
            "answer": "[NO FIREWORKS API KEY] " + query[:100],
            "tokens_used": 0,
            "latency_ms": 0.0,
            "source": "remote_fallback",
        }

    try:
        import openai

        client = openai.OpenAI(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=FIREWORKS_API_KEY,
        )

        t_start = time.perf_counter()
        response = client.chat.completions.create(
            model=FIREWORKS_MODEL_ID,
            messages=[{"role": "user", "content": query}],
            temperature=0.1,
            max_tokens=512,
        )
        latency = (time.perf_counter() - t_start) * 1000

        answer = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens if response.usage else 0

        return {
            "answer": answer,
            "tokens_used": tokens_used,
            "latency_ms": latency,
            "source": "remote",
        }
    except Exception as e:
        print(f"[Q-Route] Fireworks API error: {e}")
        return {
            "answer": f"[FIREWORKS ERROR] {e}",
            "tokens_used": 0,
            "latency_ms": 0.0,
            "source": "remote_error",
        }


# ---------------------------------------------------------------------------
# Local Quality Evaluation (Free)
# ---------------------------------------------------------------------------

def local_eval(query: str, answer: str) -> float:
    """Evaluate the quality of an answer locally. Cost = $0.

    Returns a confidence score between 0.0 and 1.0.
    This is a lightweight heuristic evaluation:
    - Checks answer is non-empty and substantive
    - Checks answer addresses key terms from the query
    - Checks answer length is proportional to query complexity
    """
    if not answer or len(answer.strip()) < 10:
        return 0.0

    score = 0.5  # Base score for non-empty answer

    # Check if answer contains key terms from the query
    query_words = set(query.lower().split())
    answer_words = set(answer.lower().split())
    overlap = len(query_words & answer_words)
    if overlap > 0:
        score += min(0.2, overlap * 0.02)

    # Check answer length is reasonable relative to query
    ratio = len(answer) / max(len(query), 1)
    if 0.5 < ratio < 10.0:
        score += 0.15

    # Check for structured content (lists, code blocks, etc.)
    if any(marker in answer for marker in ["- ", "1.", "```", "* "]):
        score += 0.1

    # Penalize very short or repetitive answers
    if len(answer) < 50:
        score -= 0.1
    if len(set(answer.split())) < len(answer.split()) * 0.3:
        score -= 0.2

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Main Agent Loop
# ---------------------------------------------------------------------------

def process_query(query: str, router: BinaryQuantumRouter,
                  extractor: QueryFeatureExtractor) -> Dict:
    """Process a single query through the Q-Route agent pipeline.

    Pipeline:
    1. Extract query features (cost = $0)
    2. Run VQC binary router (cost = $0)
    3. If routed local: run local model (cost = $0), then local eval (cost = $0)
       - If eval score < threshold: escalate to remote
    4. If routed remote: run Fireworks AI (cost = remote tokens)
    5. Return answer + metrics
    """
    # Step 1: Feature extraction (FREE)
    t_total_start = time.perf_counter()
    features = extractor.extract(query)

    # Step 2: VQC routing decision (FREE)
    t_route_start = time.perf_counter()
    route_decision, confidence = router.route(features)
    route_latency = (time.perf_counter() - t_route_start) * 1000

    escalated = False
    result = None

    if route_decision == "local" and confidence >= CONFIDENCE_THRESHOLD:
        # Step 3a: Local model (FREE)
        result = run_local_model(query)

        # Step 3b: Local eval (FREE)
        eval_score = local_eval(query, result["answer"])

        if eval_score < QUALITY_THRESHOLD:
            # Escalate to remote — local answer wasn't good enough
            escalated = True
            result = run_remote_model(query)
    else:
        # Step 4: Remote model (costs tokens)
        result = run_remote_model(query)

    total_latency = (time.perf_counter() - t_total_start) * 1000

    return {
        "query": query[:200] + ("..." if len(query) > 200 else ""),
        "answer": result["answer"],
        "route_decision": route_decision,
        "route_confidence": round(confidence, 4),
        "route_latency_ms": round(route_latency, 3),
        "escalated_to_remote": escalated,
        "final_source": result["source"],
        "remote_tokens_used": result["tokens_used"],
        "total_latency_ms": round(total_latency, 3),
    }


# ---------------------------------------------------------------------------
# Self-Test
# ---------------------------------------------------------------------------

def run_self_test():
    """Run a self-test with sample queries to validate the pipeline."""
    test_queries = [
        # Simple queries — should route LOCAL (cost = $0)
        "What is 2 + 2?",
        "Name the capital of France.",
        "What color is the sky?",
        # Complex queries — should route REMOTE (costs tokens)
        "Explain how the Variational Quantum Eigensolver (VQE) algorithm "
        "works, including the role of the ansatz, the classical optimizer "
        "loop, and how it compares to the Quantum Phase Estimation algorithm "
        "for finding ground state energies of molecular Hamiltonians.",
        'Given the following JSON schema:\n```json\n{"user": {"name": "str", '
        '"address": {"street": "str", "city": "str"}}}\n```\n'
        "Write a Python function that validates and transforms nested "
        "dictionaries to match this schema, handling missing keys and "
        "type mismatches gracefully.",
    ]

    extractor = QueryFeatureExtractor()
    router = BinaryQuantumRouter(shots=512)

    print("=" * 72)
    print("Q-ROUTE AGENT — SELF-TEST")
    print("=" * 72)

    total_remote_tokens = 0

    for i, query in enumerate(test_queries):
        print(f"\n--- Query {i + 1} ---")
        print(f"  Input: {query[:120]}{'...' if len(query) > 120 else ''}")

        # Extract features and route (no actual model call in test mode)
        features = extractor.extract(query)
        decision, confidence = router.route(features)

        print(f"  VQC Decision: {decision}")
        print(f"  Confidence:   {confidence:.4f}")
        print(f"  Features:     [{', '.join(f'{f:.3f}' for f in features)}]")

        if decision == "remote":
            est_tokens = max(50, int(len(query) / 4) + 100)
            total_remote_tokens += est_tokens
            print(f"  Est. Tokens:  ~{est_tokens} (REMOTE — COSTS TOKENS)")
        else:
            print(f"  Est. Tokens:  0 (LOCAL — FREE)")

    print(f"\n{'=' * 72}")
    print(f"TOTAL ESTIMATED REMOTE TOKENS: {total_remote_tokens}")
    print(f"{'=' * 72}")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Q-Route Agent: Hybrid Token-Efficient Routing Agent"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Path to a JSON file with tasks (list of query strings).",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to write results JSON.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-test with sample queries.",
    )
    args = parser.parse_args()

    if args.test:
        run_self_test()
        return

    extractor = QueryFeatureExtractor()
    router = BinaryQuantumRouter(shots=1024)

    results = []
    total_remote_tokens = 0

    if args.input:
        # Batch mode: read queries from JSON file
        with open(args.input, "r") as f:
            tasks = json.load(f)

        if isinstance(tasks, list):
            queries = tasks
        elif isinstance(tasks, dict) and "tasks" in tasks:
            queries = [t.get("query", t.get("prompt", str(t))) for t in tasks["tasks"]]
        else:
            queries = [str(tasks)]

        for i, query in enumerate(queries):
            print(f"[Q-Route] Processing task {i + 1}/{len(queries)}...")
            result = process_query(query, router, extractor)
            results.append(result)
            total_remote_tokens += result["remote_tokens_used"]
            print(
                f"  -> {result['final_source']} | "
                f"tokens={result['remote_tokens_used']} | "
                f"latency={result['total_latency_ms']:.1f}ms"
            )

    else:
        # Interactive stdin mode
        print("[Q-Route Agent] Enter queries (one per line, Ctrl+D to exit):")
        try:
            for line in sys.stdin:
                query = line.strip()
                if not query:
                    continue
                result = process_query(query, router, extractor)
                results.append(result)
                total_remote_tokens += result["remote_tokens_used"]
                print(json.dumps(result, indent=2))
        except (EOFError, KeyboardInterrupt):
            pass

    # Summary
    print(f"\n[Q-Route] Total queries processed: {len(results)}")
    print(f"[Q-Route] Total remote tokens used: {total_remote_tokens}")

    local_count = sum(1 for r in results if r["final_source"] == "local")
    remote_count = len(results) - local_count
    print(f"[Q-Route] Routed local (FREE): {local_count}")
    print(f"[Q-Route] Routed remote (PAID): {remote_count}")

    # Write output
    if args.output:
        output_data = {
            "results": results,
            "summary": {
                "total_queries": len(results),
                "total_remote_tokens": total_remote_tokens,
                "local_count": local_count,
                "remote_count": remote_count,
            },
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"[Q-Route] Results written to {args.output}")


if __name__ == "__main__":
    main()
