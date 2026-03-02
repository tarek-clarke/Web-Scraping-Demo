#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.
"""
modules/translator.py — Semantic field-name resolver + zero-copy telemetry ingestor.

Two classes are exported:

  SemanticTranslator
      BERT-based fuzzy matcher that maps messy / drifted sensor field names
      (e.g. "engine_temp_v2", "RPM_raw") to the canonical Cadillac F1 schema.
      Unchanged from the original design; operates on string inputs.

  TelemetryIngestor
      Numeric telemetry ingestion pipeline.  When the `fast_ingest` C++
      extension is available (built via `python setup.py build_ext --inplace`),
      it uses zero-copy pinned-memory tensors and async HIP/CUDA streams to
      achieve a deterministic ≤13 µs ingestion window, bypassing the Python GIL.

      Falls back to pure-PyTorch `torch.tensor()` transparently so the module
      is always importable even before the extension is compiled.

Building the C++ extension
--------------------------
    cd /root/resilient-rap-framework
    python setup.py build_ext --inplace

After the build, `import fast_ingest` will succeed and TelemetryIngestor will
automatically switch to the accelerated path.
"""

from __future__ import annotations

import warnings
from typing import List, Optional, Sequence, Tuple

from sentence_transformers import SentenceTransformer, util
import torch

# ---------------------------------------------------------------------------
# Optional C++ extension: fast_ingest
# ---------------------------------------------------------------------------
# The extension is compiled from fast_ingest.cpp via setup.py.  When present
# it bypasses the Python GIL and uses hipHostMalloc / cudaMallocHost pinned
# memory with a non-default HIP/CUDA stream for async H→D transfers.
#
# Graceful fallback: if the .so has not been built yet, every TelemetryIngestor
# call silently falls back to the pure-Python torch.tensor() path so nothing
# breaks during development before the extension is compiled.
# ---------------------------------------------------------------------------

try:
    import fast_ingest as _fast_ingest       # type: ignore[import]
    _FAST_INGEST_AVAILABLE: bool = True
except ImportError:
    _fast_ingest = None                      # type: ignore[assignment]
    _FAST_INGEST_AVAILABLE = False
    warnings.warn(
        "fast_ingest C++ extension not found. "
        "Run `python setup.py build_ext --inplace` to enable zero-copy "
        "pinned-memory ingestion and the ≤13 µs latency target. "
        "Falling back to torch.tensor() (adds ~30–60 µs Python overhead).",
        RuntimeWarning,
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Sector sensor layout — matches SENSORS in cadillac_gpu_stress_test.py
# ---------------------------------------------------------------------------
# Order   Sensor            lo        hi
# ──────  ────────────────  ────────  ────────
#  0      speed              80.0     360.0
#  1      rpm              4000.0   15500.0
#  2      throttle            0.0     100.0
#  3      brake_temp        100.0    1100.0
#  4      engine_temp        70.0     130.0
#  5      aero_load         150.0    2800.0
#  6      tyre_pressure      19.0      28.0
#  7      ecu_canbus          0.0   65535.0
#  8      heart_rate         55.0     200.0
#  9      g_force_lateral    -6.0       6.0

CANONICAL_SENSORS: List[str] = [
    "speed", "rpm", "throttle", "brake_temp", "engine_temp",
    "aero_load", "tyre_pressure", "ecu_canbus", "heart_rate", "g_force_lateral",
]

SENSOR_LO: List[float] = [80.0, 4000.0,  0.0, 100.0, 70.0,
                           150.0,   19.0,  0.0,  55.0,  -6.0]

SENSOR_HI: List[float] = [360.0, 15500.0, 100.0, 1100.0,  130.0,
                           2800.0,    28.0, 65535.0,  200.0,    6.0]


# ---------------------------------------------------------------------------
# TelemetryIngestor
# ---------------------------------------------------------------------------

class TelemetryIngestor:
    """
    High-performance numeric telemetry ingestion for Cadillac F1 sensors.

    Uses the ``fast_ingest`` C++ extension when available to achieve:
      • Zero redundant memcpy  — ``torch::from_blob`` wraps hipHostMalloc buffer.
      • GIL bypass             — heavy copies run in C++ without the GIL.
      • Async H→D transfer     — issued on a non-default high-priority HIP stream
                                 so ingestion of packet N+1 overlaps GPU work on N.
      • ≤13 µs ingestion window after the extension is built (vs ~35 µs Python).

    Falls back to ``torch.tensor()`` transparently when the extension is absent.

    Parameters
    ----------
    device : torch.device or str, optional
        Target device for tensors.  Defaults to ``cuda`` if available.
    lo : list[float], optional
        Per-channel physical minimum for normalization.
        Defaults to :data:`SENSOR_LO` (Cadillac F1 10-sensor layout).
    hi : list[float], optional
        Per-channel physical maximum for normalization.
        Defaults to :data:`SENSOR_HI`.
    """

    def __init__(
        self,
        device: Optional[torch.device | str] = None,
        lo: Sequence[float] = SENSOR_LO,
        hi: Sequence[float] = SENSOR_HI,
    ) -> None:
        if device is None:
            import os
            # Allow env var override for debugging/forcing (gpu/cuda/cpu)
            force_device = os.environ.get("FORCE_DEVICE", "").strip().lower()
            if force_device == "gpu":
                try:
                    device = torch.device("cuda", 0)
                    # Verify device works
                    torch.cuda.get_device_name(0)
                except Exception:
                    device = torch.device("cpu")
            elif force_device == "cpu":
                device = torch.device("cpu")
            else:
                # Auto-detect: works with CUDA, ROCm/HIP, or any torch.cuda backend
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.device: torch.device = torch.device(device)
        self.lo: List[float] = list(lo)
        self.hi: List[float] = list(hi)
        self.accelerated: bool = _FAST_INGEST_AVAILABLE

    # ------------------------------------------------------------------
    # Single-packet interface
    # ------------------------------------------------------------------

    def ingest(self, packet: Sequence[float | None]) -> torch.Tensor:
        """
        Ingest a raw telemetry packet and return a **pinned CPU tensor** {N}.

        ``None`` values (corrupt / dropped sensors) are replaced with ``NaN``
        before ingestion so the anomaly detector can identify them via
        ``torch.isnan()``.

        Parameters
        ----------
        packet : sequence of float | None
            Raw sensor readings in canonical order (see :data:`CANONICAL_SENSORS`).

        Returns
        -------
        torch.Tensor
            1-D float32 tensor of shape ``{N}`` on CPU pinned memory.
        """
        clean = [v if isinstance(v, (int, float)) else float("nan")
                 for v in packet]

        if self.accelerated:
            # Zero-copy path: hipHostMalloc + torch::from_blob in C++.
            # GIL is released inside _fast_ingest.ingest().
            return _fast_ingest.ingest(clean)  # type: ignore[union-attr]

        # Fallback: pure PyTorch (adds ~30 µs Python-GIL overhead)
        return torch.tensor(clean, dtype=torch.float32)

    def normalize(self, packet: Sequence[float | None]) -> torch.Tensor:
        """
        Ingest + min–max normalize one packet to **[−1, 1]** on the GPU.

        The H→D transfer and normalization run on a high-priority non-default
        HIP/CUDA stream (fast_ingest path) so the next packet can be ingested
        while the GPU is still processing this one.

        Parameters
        ----------
        packet : sequence of float | None
            Raw sensor readings.

        Returns
        -------
        torch.Tensor
            1-D float32 device tensor ``{N}``, values in ``[−1, 1]``.
        """
        clean = [v if isinstance(v, (int, float)) else float("nan")
                 for v in packet]

        if self.accelerated and self.device.type == "cuda":
            # Async pipeline: pinned alloc → memcpy (GIL-free) →
            #                 non-blocking H→D copy → GPU normalization.
            return _fast_ingest.normalize(clean, self.lo, self.hi)  # type: ignore[union-attr]

        # Fallback: torch.tensor() on CPU then move; no async overlap.
        t = torch.tensor(clean, dtype=torch.float32)
        lo_t = torch.tensor(self.lo, dtype=torch.float32)
        hi_t = torch.tensor(self.hi, dtype=torch.float32)
        range_t = (hi_t - lo_t).clamp_min_(1e-6)
        normalized = ((t - lo_t) / range_t) * 2.0 - 1.0
        return normalized.to(self.device)

    # ------------------------------------------------------------------
    # Batch interface (used by GPUAnomalyDetector)
    # ------------------------------------------------------------------

    def ingest_batch(
        self, packets: Sequence[Sequence[float | None]]
    ) -> torch.Tensor:
        """
        Batch-ingest multiple telemetry packets → **device Tensor {B, N}**.

        In the accelerated path a single ``hipHostMalloc`` slab covers all
        ``B`` packets, the GIL is released for the entire copy + H→D transfer,
        and normalization runs on a high-priority stream.

        This replaces the ``torch.tensor(clean, ...)`` call inside
        ``GPUAnomalyDetector.detect_batch()`` with a zero-copy pipeline.

        Parameters
        ----------
        packets : sequence of sequence of float | None
            Shape ``(B, N)`` — a batch of ``B`` raw telemetry packets.

        Returns
        -------
        torch.Tensor
            Float32 tensor of shape ``{B, N}`` on the target device,
            values normalized to ``[−1, 1]``.
        """
        cleaned: List[List[float]] = [
            [v if isinstance(v, (int, float)) else float("nan") for v in pkt]
            for pkt in packets
        ]

        if self.accelerated and self.device.type == "cuda":
            return _fast_ingest.ingest_batch(cleaned, self.lo, self.hi)  # type: ignore[union-attr]

        # Fallback: stack individual tensors (allocates B intermediate tensors).
        stacked = torch.tensor(
            [[float("nan") if v != v else v for v in row] for row in cleaned],
            dtype=torch.float32,
        )
        lo_t = torch.tensor(self.lo, dtype=torch.float32)
        hi_t = torch.tensor(self.hi, dtype=torch.float32)
        range_t = (hi_t - lo_t).clamp_min_(1e-6)
        return (((stacked - lo_t) / range_t) * 2.0 - 1.0).to(self.device)

    def sync(self) -> None:
        """Block until all queued ingest-stream work is complete (accelerated path only)."""
        if self.accelerated:
            _fast_ingest.sync()  # type: ignore[union-attr]

    @staticmethod
    def is_accelerated() -> bool:
        """Return ``True`` if the fast_ingest C++ extension is loaded."""
        return _FAST_INGEST_AVAILABLE


# ---------------------------------------------------------------------------
# TelemetryStreamer — F1-grade persistent-state streaming ingestor
# ---------------------------------------------------------------------------

class TelemetryStreamer:
    """
    Real-time streaming ingestor with pre-allocated pinned ring buffer.

    Wraps the C++ ``StreamingIngestor`` class to eliminate **all** per-batch
    allocation overhead:

    ==================  ==============  ==============
    Overhead source     ``ingest_batch``  ``TelemetryStreamer``
    ==================  ==============  ==============
    hipHostMalloc       ~500 µs/batch   **0** (pre-allocated)
    lo/hi tensors       ~ 50 µs/batch   **0** (cached on GPU)
    Stream acquisition  ~ 10 µs/batch   **0** (persistent stream)
    ==================  ==============  ==============

    Architecture mirrors an F1 ECU's DMA ring buffer: a fixed-size slab of
    page-locked host memory is continuously filled by :meth:`push`, with an
    automatic flush to the GPU when the buffer reaches ``batch_size`` packets.

    Falls back to :class:`TelemetryIngestor` batch mode when the C++ extension
    is not available.

    Parameters
    ----------
    batch_size : int
        Number of packets per GPU flush (default 128).
    lo : list[float], optional
        Per-channel physical minimum.  Defaults to :data:`SENSOR_LO`.
    hi : list[float], optional
        Per-channel physical maximum.  Defaults to :data:`SENSOR_HI`.

    Example
    -------
    >>> streamer = TelemetryStreamer(batch_size=128)
    >>> for packet in telemetry_stream:
    ...     flushed = streamer.push(packet)
    ...     if flushed:
    ...         normalized = streamer.last_result()  # {128, 10} GPU tensor
    ...         # run anomaly detection, BERT reconciliation, etc.
    >>> if streamer.pending > 0:
    ...     final = streamer.flush()  # drain remaining packets
    >>> streamer.sync()
    """

    def __init__(
        self,
        batch_size: int = 128,
        lo: Sequence[float] = SENSOR_LO,
        hi: Sequence[float] = SENSOR_HI,
    ) -> None:
        self._lo = list(lo)
        self._hi = list(hi)
        self._batch_size = batch_size
        self._accelerated = _FAST_INGEST_AVAILABLE

        if self._accelerated:
            self._streamer = _fast_ingest.StreamingIngestor(  # type: ignore[union-attr]
                self._lo, self._hi, batch_size
            )
        else:
            # Fallback: accumulate in Python, flush via TelemetryIngestor
            self._fallback = TelemetryIngestor(lo=lo, hi=hi)
            self._buffer: List[List[float]] = []
            self._last: Optional[torch.Tensor] = None

    # ------------------------------------------------------------------
    # Push API
    # ------------------------------------------------------------------

    def push(self, packet: Sequence[float | None]) -> bool:
        """
        Push one telemetry packet.  Returns ``True`` if an auto-flush occurred.

        ``None`` values (corrupt sensors) are replaced with ``NaN``.
        """
        clean = [v if isinstance(v, (int, float)) else float("nan")
                 for v in packet]

        if self._accelerated:
            return self._streamer.push(clean)

        # Fallback path
        self._buffer.append(clean)
        if len(self._buffer) >= self._batch_size:
            self._last = self._fallback.ingest_batch(self._buffer)
            self._buffer.clear()
            return True
        return False

    def push_many(self, packets: Sequence[Sequence[float | None]]) -> int:
        """
        Push multiple packets.  Returns the number of auto-flushes.

        The C++ path runs the entire loop with the GIL released.
        """
        cleaned: List[List[float]] = [
            [v if isinstance(v, (int, float)) else float("nan") for v in pkt]
            for pkt in packets
        ]

        if self._accelerated:
            return self._streamer.push_many(cleaned)

        # Fallback
        flushes = 0
        for pkt in cleaned:
            if self.push(pkt):
                flushes += 1
        return flushes

    # ------------------------------------------------------------------
    # Flush / result API
    # ------------------------------------------------------------------

    def flush(self) -> torch.Tensor:
        """Flush pending packets to GPU.  Returns ``{count, N}`` device tensor."""
        if self._accelerated:
            return self._streamer.flush()

        if not self._buffer:
            return torch.empty(
                0, len(self._lo),
                dtype=torch.float32,
                device=self._fallback.device,
            )
        result = self._fallback.ingest_batch(self._buffer)
        self._buffer.clear()
        self._last = result
        return result

    def last_result(self) -> Optional[torch.Tensor]:
        """Get the most recent auto-flushed tensor, or ``None``."""
        if self._accelerated:
            r = self._streamer.last_result()
            return r if r is not None and r.numel() > 0 else None
        return self._last

    def sync(self) -> None:
        """Block until all GPU work is complete."""
        if self._accelerated:
            self._streamer.sync()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pending(self) -> int:
        """Number of packets in the buffer awaiting flush."""
        if self._accelerated:
            return self._streamer.pending
        return len(self._buffer)

    @property
    def capacity(self) -> int:
        """Batch size (ring-buffer capacity)."""
        return self._batch_size

    @property
    def is_accelerated(self) -> bool:
        """``True`` if the C++ StreamingIngestor is active."""
        return self._accelerated


# ---------------------------------------------------------------------------
# SemanticTranslator
# ---------------------------------------------------------------------------

class SemanticTranslator:
    def __init__(self, standard_schema):
        self.standard_schema = standard_schema
        # Lazy-load: model is loaded on first access via the property
        self._model = None
        self._schema_embeddings = None

    @property
    def model(self):
        if self._model is None:
            # Using a reliable, lightweight model (all-MiniLM-L6-v2)
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            # Pre-calculate embeddings for the target schema
            self._schema_embeddings = self._model.encode(
                self.standard_schema, convert_to_tensor=True
            )
        return self._model

    @property
    def schema_embeddings(self):
        """Lazily computed schema embeddings."""
        if self._schema_embeddings is None:
            # Accessing self.model triggers model load + embedding computation
            _ = self.model
        return self._schema_embeddings

    @schema_embeddings.setter
    def schema_embeddings(self, value):
        self._schema_embeddings = value

    def resolve(self, messy_field, threshold=0.45):
        """
        Calibrated threshold at 0.45 to balance resilience with accuracy.
        """
        # Convert incoming field name to a vector
        input_embedding = self.model.encode(messy_field, convert_to_tensor=True)
        
        # Calculate Cosine Similarity
        scores = util.cos_sim(input_embedding, self.schema_embeddings)[0]
        
        # Find the best match
        best_match_idx = torch.argmax(scores).item()
        confidence = scores[best_match_idx].item()
        
        if confidence >= threshold:
            return self.standard_schema[best_match_idx], confidence
        return None, confidence

    def resolve_batch(self, messy_fields, threshold=0.45):
        """
        Resolve multiple field names in a single batched call.

        Encodes all *messy_fields* in one ``model.encode()`` invocation,
        eliminating the per-field tokenisation/kernel-launch overhead
        (~5-15 ms each).  Returns a list of ``(match, confidence)`` tuples
        in the same order as *messy_fields*.
        """
        if not messy_fields:
            return []

        embeddings = self.model.encode(messy_fields, convert_to_tensor=True)
        scores = util.cos_sim(embeddings, self.schema_embeddings)  # (N, S)
        best_indices = torch.argmax(scores, dim=1)
        confidences = scores[torch.arange(len(messy_fields)), best_indices]

        results = []
        for idx, conf in zip(best_indices.tolist(), confidences.tolist()):
            if conf >= threshold:
                results.append((self.standard_schema[idx], conf))
            else:
                results.append((None, conf))
        return results