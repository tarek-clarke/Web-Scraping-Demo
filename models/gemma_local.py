"""Offline Gemma 4 E4B loader for macOS Apple Silicon (MPS).

This module provides a small production-oriented wrapper around a locally
cached Gemma checkpoint. It never performs network calls and only loads from
files available on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class ModelArtifacts:
    """Resolved model artifacts for a local Hugging Face checkpoint."""

    model_dir: Path
    missing: List[str]


class GemmaLocal:
    """Load and run a local Gemma checkpoint entirely offline.

    Parameters
    ----------
    local_path:
        Path to a Hugging Face cache folder, snapshot directory, or model
        directory containing a Gemma 4 E4B checkpoint.

    Notes
    -----
    * The loader never contacts external services.
    * MPS is preferred when available on Apple Silicon.
    * A clear exception is raised when the model directory is missing or
      incomplete.
    """

    REQUIRED_TOKENIZER_MARKERS = (
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
    )
    REQUIRED_CONFIG_FILE = "config.json"
    REQUIRED_WEIGHT_MARKERS = (
        "model.safetensors",
        "pytorch_model.bin",
        "model.safetensors.index.json",
        "pytorch_model.bin.index.json",
    )

    def __init__(self, local_path: str | Path):
        self.local_path = Path(local_path).expanduser().resolve()
        self.model_dir: Optional[Path] = None
        self.tokenizer = None
        self.model = None
        self.device = None
        self.torch_dtype = None

        artifacts = self._resolve_model_artifacts(self.local_path)
        if not artifacts.model_dir.exists():
            raise FileNotFoundError(
                f"Gemma model folder does not exist: {artifacts.model_dir}"
            )
        if artifacts.missing:
            missing_list = ", ".join(artifacts.missing)
            raise RuntimeError(
                "Gemma model folder is incomplete. "
                f"Missing required artifacts in {artifacts.model_dir}: {missing_list}"
            )

        self.model_dir = artifacts.model_dir
        self._load_model()

    def _resolve_model_artifacts(self, root: Path) -> ModelArtifacts:
        """Resolve a usable model directory from the provided path.

        The path may point directly at a snapshot directory, a model folder, or
        a Hugging Face cache root that contains snapshot subdirectories.
        """

        if not root.exists():
            raise FileNotFoundError(f"Gemma local_path does not exist: {root}")

        if root.is_file():
            root = root.parent

        candidates: List[Path] = []

        if self._is_complete_model_directory(root):
            candidates.append(root)

        snapshots_dir = root / "snapshots"
        if snapshots_dir.is_dir():
            snapshot_dirs = [p for p in snapshots_dir.iterdir() if p.is_dir()]
            snapshot_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            candidates.extend(snapshot_dirs)

        # Fall back to any nested directory that looks like a checkpoint.
        # This supports Hugging Face cache roots such as models--org--name/.
        for config_path in root.rglob(self.REQUIRED_CONFIG_FILE):
            candidate = config_path.parent
            if candidate not in candidates and self._is_complete_model_directory(candidate):
                candidates.append(candidate)

        if not candidates:
            return ModelArtifacts(
                model_dir=root,
                missing=[
                    self.REQUIRED_CONFIG_FILE,
                    "tokenizer artifact (tokenizer.json or tokenizer.model)",
                    "model weights (.safetensors or .bin)",
                ],
            )

        for candidate in candidates:
            missing = self._missing_artifacts(candidate)
            if not missing:
                return ModelArtifacts(model_dir=candidate, missing=[])

        # No candidate was fully complete; report the best (first) candidate.
        best = candidates[0]
        return ModelArtifacts(model_dir=best, missing=self._missing_artifacts(best))

    def _is_complete_model_directory(self, model_dir: Path) -> bool:
        """Quick check for the presence of the expected model artifacts."""

        return not self._missing_artifacts(model_dir)

    def _missing_artifacts(self, model_dir: Path) -> List[str]:
        """Return a list of missing required files for the checkpoint."""

        missing: List[str] = []

        if not (model_dir / self.REQUIRED_CONFIG_FILE).is_file():
            missing.append(self.REQUIRED_CONFIG_FILE)

        if not any((model_dir / marker).is_file() for marker in self.REQUIRED_TOKENIZER_MARKERS):
            missing.append("tokenizer artifact (tokenizer.json or tokenizer.model)")

        if not self._has_weights(model_dir):
            missing.append("model weights (.safetensors or .bin)")

        return missing

    def _has_weights(self, model_dir: Path) -> bool:
        """Check for a full or sharded weight set in the model directory."""

        if any((model_dir / marker).is_file() for marker in self.REQUIRED_WEIGHT_MARKERS[:2]):
            return True

        # Sharded checkpoints use an index file plus shard files.
        if (model_dir / "model.safetensors.index.json").is_file():
            return any(model_dir.glob("model-*.safetensors"))
        if (model_dir / "pytorch_model.bin.index.json").is_file():
            return any(model_dir.glob("pytorch_model-*.bin"))

        return False

    def _select_device(self):
        """Prefer MPS on Apple Silicon, then CUDA, then CPU."""

        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps"), torch.float16
        if torch.cuda.is_available():
            return torch.device("cuda"), torch.float16
        return torch.device("cpu"), torch.float32

    def _load_model(self) -> None:
        """Load tokenizer and causal language model from the local checkpoint."""

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.device, self.torch_dtype = self._select_device()

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
            torch_dtype=self.torch_dtype,
        )
        self.model.to(self.device)
        self.model.eval()

        # Ensure generation works even if the tokenizer has no pad token.
        if self.tokenizer.pad_token is None and self.tokenizer.eos_token is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def generate(
        self,
        text: str,
        max_new_tokens: int = 128,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> str:
        """Generate text from the loaded Gemma checkpoint.

        Parameters
        ----------
        text:
            Prompt to send to the model.
        max_new_tokens:
            Maximum number of tokens to generate.
        temperature:
            Sampling temperature. Use 0.0 for greedy decoding.
        top_p:
            Nucleus sampling parameter used when temperature is greater than 0.

        Returns
        -------
        str
            The generated completion, stripped of the original prompt.
        """

        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")

        import torch

        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        generation_kwargs = {
            "max_new_tokens": int(max_new_tokens),
            "do_sample": temperature > 0.0,
        }
        if temperature > 0.0:
            generation_kwargs["temperature"] = float(temperature)
            generation_kwargs["top_p"] = float(top_p)

        with torch.no_grad():
            output_ids = self.model.generate(**inputs, **generation_kwargs)

        prompt_length = inputs["input_ids"].shape[1]
        generated_tokens = output_ids[0][prompt_length:]
        return self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

    def __repr__(self) -> str:
        return f"GemmaLocal(model_dir={self.model_dir!s}, device={self.device!s})"


__all__ = ["GemmaLocal"]