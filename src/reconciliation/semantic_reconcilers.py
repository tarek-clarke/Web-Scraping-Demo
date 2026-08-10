"""Versioned semantic and schema-aware reconcilers for the v3 router.

All semantic reconcilers expose the same packet-level contract.  Their scores
are semantic mapping scores; the oracle also records the mappings and coverage
so they are not misreported as exact packet accuracy.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Dict, List, Tuple

import numpy as np


def _coerce(value):
    if isinstance(value, list):
        return {str(i): item for i, item in enumerate(value)}
    return value if isinstance(value, dict) else {}


def _result(mapped, unmapped, score, elapsed_ms, batch_size):
    denominator = max(1, len(mapped) + len(unmapped))
    return {
        "accuracy": float(score / denominator),
        "semantic_similarity": float(score / denominator),
        "mapping_coverage": float(len(mapped) / denominator),
        "latency_ms": float(elapsed_ms),
        "mapped_fields": mapped,
        "unmapped_fields": unmapped,
        "batch_size": batch_size,
    }


class SchemaRegistryReconciler:
    """Deterministic CPU reconciler for aliases and structural migrations."""

    def __init__(self):
        self.aliases = {
            "temperature": {"temp", "temperature", "temp_c", "temperature_c"},
            "speed": {"speed", "velocity", "speed_ms", "velocity_ms"},
            "timestamp": {"timestamp", "time", "ts", "datetime"},
            "id": {"id", "identifier", "uid", "uuid"},
            "latitude": {"lat", "latitude"},
            "longitude": {"lon", "lng", "longitude"},
        }
        self.lookup = {alias: canonical for canonical, aliases in self.aliases.items() for alias in aliases}

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        start = time.perf_counter()
        original, drifted = _coerce(original), _coerce(drifted)
        mapped, unmapped, used = [], [], set()
        for source_key in original:
            source_norm = str(source_key).lower().replace("-", "_")
            source_canonical = self.lookup.get(source_norm, source_norm)
            match = next(
                (candidate for candidate in drifted if candidate not in used and self.lookup.get(str(candidate).lower().replace("-", "_"), str(candidate).lower()) == source_canonical),
                None,
            )
            if match is None and source_key in drifted and source_key not in used:
                match = source_key
            if match is None:
                unmapped.append(source_key)
            else:
                mapped.append((source_key, match))
                used.add(match)
        elapsed = (time.perf_counter() - start) * 1000
        return _result(mapped, unmapped, len(mapped), elapsed, 1)

    def reconcile_batch(self, pairs):
        return [self.reconcile(original, drifted) for original, drifted in pairs]


class SentenceTransformerSemanticReconciler:
    model_id = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, hardware_profile="cpu", batch_size=32):
        self.batch_size = batch_size
        self.hardware_profile = hardware_profile
        self.device = "cuda" if hardware_profile in {"cuda", "rocm"} else "cpu"
        from ..inference.huggingface_compat import install_hub_compat
        install_hub_compat()
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(os.environ.get(self.env_name, self.model_id), device=self.device)
        if hardware_profile in {"cuda", "rocm"}:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError(f"{self.name} requires an accelerator; CPU fallback is disabled")

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def env_name(self):
        return "MODEL_ID"

    def _encode(self, texts):
        return np.asarray(self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False))

    def reconcile_batch(self, pairs):
        started = time.perf_counter()
        coerced = [(_coerce(original), _coerce(drifted)) for original, drifted in pairs]
        all_keys = sorted({str(key) for original, drifted in coerced for key in list(original) + list(drifted)})
        if not all_keys:
            return [_result([], [], 0.0, 0.0, self.batch_size) for _ in pairs]
        embeddings = self._encode(all_keys)
        vectors = dict(zip(all_keys, embeddings))
        elapsed = (time.perf_counter() - started) * 1000 / max(1, len(pairs))
        results = []
        for original, drifted in coerced:
            original_keys, drifted_keys = list(original), list(drifted)
            mapped, unmapped, score = [], [], 0.0
            used = set()
            for key in original_keys:
                candidates = [candidate for candidate in drifted_keys if candidate not in used]
                if not candidates:
                    unmapped.append(key)
                    continue
                similarities = [float(np.dot(vectors[str(key)], vectors[str(candidate)])) for candidate in candidates]
                index = int(np.argmax(similarities))
                if similarities[index] >= 0.40:
                    mapped.append((key, candidates[index]))
                    used.add(candidates[index])
                    score += max(0.0, similarities[index])
                else:
                    unmapped.append(key)
            results.append(_result(mapped, unmapped, score, elapsed, self.batch_size))
        return results

    def reconcile(self, original, drifted):
        return self.reconcile_batch([(original, drifted)])[0]


class BGEReconciler(SentenceTransformerSemanticReconciler):
    model_id = "BAAI/bge-base-en-v1.5"
    env_name = "BGE_MODEL_ID"


class CrossEncoderReconciler(SentenceTransformerSemanticReconciler):
    model_id = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    env_name = "CROSS_ENCODER_MODEL_ID"

    def __init__(self, hardware_profile="cpu", batch_size=32):
        self.batch_size = batch_size
        self.hardware_profile = hardware_profile
        self.device = "cuda" if hardware_profile in {"cuda", "rocm"} else "cpu"
        from ..inference.huggingface_compat import install_hub_compat
        install_hub_compat()
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(os.environ.get(self.env_name, self.model_id), device=self.device)
        if hardware_profile in {"cuda", "rocm"}:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError("cross_encoder requires an accelerator; CPU fallback is disabled")

    def reconcile_batch(self, pairs):
        started = time.perf_counter()
        results = []
        for original, drifted in pairs:
            original, drifted = _coerce(original), _coerce(drifted)
            candidates = [(str(source), str(target)) for source in original for target in drifted]
            scores = self.model.predict(candidates, batch_size=self.batch_size, show_progress_bar=False) if candidates else []
            mapped, unmapped, score, used = [], [], 0.0, set()
            for source in original:
                options = [(float(scores[i]), target) for i, (left, target) in enumerate(candidates) if left == str(source) and target not in used]
                if not options:
                    unmapped.append(source)
                    continue
                best, target = max(options)
                confidence = 1.0 / (1.0 + np.exp(-best))
                if confidence >= 0.50:
                    mapped.append((source, target)); used.add(target); score += float(confidence)
                else:
                    unmapped.append(source)
            results.append(_result(mapped, unmapped, score, (time.perf_counter() - started) * 1000 / max(1, len(pairs)), self.batch_size))
        return results


class CohereEmbedV4Reconciler:
    """Cloud embedding baseline; server-side energy is intentionally unavailable."""

    model_id = "embed-v4.0"
    url = "https://api.cohere.com/v2/embed"

    def __init__(self, hardware_profile="cpu", batch_size=96):
        self.batch_size = min(96, batch_size)
        self.api_key = os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise RuntimeError("Cohere Embed v4 requested but COHERE_API_KEY is not set")
        self.cache = {}
        self.cache_enabled = os.environ.get("RAP_COHERE_EMBED_CACHE", "1").lower() not in {
            "0", "false", "no"
        }

    def _encode(self, texts):
        # A no-cache mode is required for honest end-to-end stream latency.
        # Deduplication remains local to one request batch, but no embedding is
        # reused across packet batches.
        target_cache = self.cache if self.cache_enabled else {}
        missing = list(dict.fromkeys(text for text in texts if text not in target_cache))
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start:start + self.batch_size]
            payload = json.dumps({"model": self.model_id, "input_type": "classification", "embedding_types": ["float"], "output_dimension": 1024, "texts": batch}).encode()
            request = urllib.request.Request(self.url, data=payload, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=120) as response:
                values = json.loads(response.read().decode())["embeddings"]["float"]
            target_cache.update(dict(zip(batch, np.asarray(values))))
        return np.asarray([target_cache[text] for text in texts])

    def reconcile_batch(self, pairs):
        helper = SentenceTransformerSemanticReconciler.__new__(SentenceTransformerSemanticReconciler)
        helper._encode = self._encode
        helper.batch_size = self.batch_size
        return SentenceTransformerSemanticReconciler.reconcile_batch(helper, pairs)

    def reconcile(self, original, drifted):
        return self.reconcile_batch([(original, drifted)])[0]
