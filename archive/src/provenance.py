#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Tamper-Evident Provenance Logger.

Research justification: cryptographic hashing provides auditability and lineage
verification for schema repairs in regulated data pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json


@dataclass
class TamperEvidentLogger:
    """
    Logs transformations with linked hashes to create a verifiable chain.

    Uses a persistent, buffered file handle to avoid per-write open/close overhead.
    """

    log_path: Path = Path("data/provenance_log.jsonl")
    last_hash: Optional[str] = None
    _handle: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self.log_path, "a", encoding="utf-8", buffering=8192)

    def close(self) -> None:
        """Flush and close the persistent file handle."""
        if self._handle and not self._handle.closed:
            self._handle.flush()
            self._handle.close()

    def __del__(self) -> None:
        self.close()

    def _hash_payload(self, payload: Any) -> str:
        """
        Compute SHA-256 over a canonical JSON representation.
        """
        def _default(obj: Any) -> str:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_default)
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    def log_transformation(
        self,
        input_data: Any,
        output_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Log a transformation with input/output hashes and a lineage link.

        Args:
            input_data: Raw input before transformation.
            output_data: Output after transformation.
            metadata: Additional context such as source, model, or version.

        Returns:
            The log record persisted to disk.
        """

        input_hash = self._hash_payload(input_data)
        output_hash = self._hash_payload(output_data)
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "input_hash": input_hash,
            "output_hash": output_hash,
            "previous_hash": self.last_hash,
            "metadata": metadata or {},
        }
        record_hash = self._hash_payload(record)
        record["record_hash"] = record_hash

        self._handle.write(json.dumps(record) + "\n")

        self.last_hash = record_hash
        return record
