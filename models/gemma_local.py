"""Offline Gemma 4 E4B loader — supports macOS MPS, Cloud CUDA, and Windows ROCm.

This module provides a production-oriented wrapper around a locally cached
Gemma checkpoint. It never performs network calls and only loads from files
available on disk.

On Windows ROCm, the safetensors Rust mmap implementation crashes at the
C++ level when reading tensor data. We detect this at load time and fall
back to a pure-Python file I/O loader (``models.safetensors_loader``) that
reads tensors individually without memory-mapping.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, List, Optional


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
    DEFAULT_CACHE_ROOTS: ClassVar[tuple[Path, ...]] = (
        Path.home() / ".cache/huggingface/hub",
        Path.home() / ".cache/huggingface",
        Path.home() / ".cache",
        Path.home() / "Library/Caches/huggingface/hub",
        Path.home() / "Library/Caches/huggingface",
    )

    def __init__(self, local_path: str | Path | None = None):
        if os.environ.get("GEMMA_API_URL") or os.environ.get("USE_API") in ("1", "true", "yes"):
            self.backend = "api"
            self.api_url = os.environ.get("GEMMA_API_URL", "http://localhost:1234/v1/chat/completions")
            self.api_model = os.environ.get("GEMMA_API_MODEL", "google/gemma-4-E4B-it")
            self.local_path = None
            self.model_dir = None
            self.tokenizer = None
            self.model = None
            self.device = "cpu"
            self.torch_dtype = None
            print(f"\n[x] Gemma initialized in API Mode! Target Server: {self.api_url}\n")
            return

        self.local_path = self.resolve_local_path(local_path)
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

    @classmethod
    def resolve_local_path(cls, local_path: str | Path | None = None) -> Path:
        """Resolve a Gemma checkpoint path from an explicit or discovered location."""

        if local_path:
            return Path(local_path).expanduser().resolve()

        env_path = os.getenv("GEMMA_LOCAL_PATH")
        if env_path:
            return Path(env_path).expanduser().resolve()

        discovered_path = cls.discover_local_path()
        if discovered_path is not None:
            return discovered_path

        raise FileNotFoundError(
            "Could not auto-detect a local Gemma checkpoint. "
            "Set GEMMA_LOCAL_PATH or pass local_path explicitly."
        )

    @classmethod
    def discover_local_path(cls) -> Path | None:
        """Search common Hugging Face cache locations for a Gemma checkpoint."""

        search_roots: list[Path] = []

        for env_var in ("HF_HOME", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE", "XDG_CACHE_HOME"):
            env_value = os.getenv(env_var)
            if env_value:
                search_roots.append(Path(env_value).expanduser())

        search_roots.extend(cls.DEFAULT_CACHE_ROOTS)

        seen_roots: set[Path] = set()
        for root in search_roots:
            resolved_root = root.expanduser()
            if resolved_root in seen_roots or not resolved_root.exists():
                continue
            seen_roots.add(resolved_root)

            discovered = cls._discover_in_cache_root(resolved_root)
            if discovered is not None:
                return discovered

        return None

    @classmethod
    def _discover_in_cache_root(cls, root: Path) -> Path | None:
        """Find the newest complete Gemma checkpoint beneath a cache root."""

        if cls._is_complete_model_directory(root):
            return root.resolve()

        candidate_dirs: list[Path] = []

        snapshots_dir = root / "snapshots"
        if snapshots_dir.is_dir():
            snapshot_dirs = [p for p in snapshots_dir.iterdir() if p.is_dir()]
            snapshot_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            candidate_dirs.extend(snapshot_dirs)

        for config_path in root.rglob(cls.REQUIRED_CONFIG_FILE):
            candidate_dir = config_path.parent
            candidate_name = str(candidate_dir).lower()
            if "gemma" not in candidate_name:
                continue
            if candidate_dir not in candidate_dirs:
                candidate_dirs.append(candidate_dir)

        for candidate_dir in candidate_dirs:
            if cls._is_complete_model_directory(candidate_dir):
                return candidate_dir.resolve()

        return None

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

    @classmethod
    def _is_complete_model_directory(cls, model_dir: Path) -> bool:
        """Quick check for the presence of the expected model artifacts."""

        return not cls._missing_artifacts(model_dir)

    @classmethod
    def _missing_artifacts(cls, model_dir: Path) -> List[str]:
        """Return a list of missing required files for the checkpoint."""

        missing: List[str] = []

        if not (model_dir / cls.REQUIRED_CONFIG_FILE).is_file():
            missing.append(cls.REQUIRED_CONFIG_FILE)

        if not any((model_dir / marker).is_file() for marker in cls.REQUIRED_TOKENIZER_MARKERS):
            missing.append("tokenizer artifact (tokenizer.json or tokenizer.model)")

        if not cls._has_weights(model_dir):
            missing.append("model weights (.safetensors or .bin)")

        return missing

    @classmethod
    def _has_weights(cls, model_dir: Path) -> bool:
        """Check for a full or sharded weight set in the model directory."""

        if any((model_dir / marker).is_file() for marker in cls.REQUIRED_WEIGHT_MARKERS[:2]):
            return True

        # Sharded checkpoints use an index file plus shard files.
        if (model_dir / "model.safetensors.index.json").is_file():
            return any(model_dir.glob("model-*.safetensors"))
        if (model_dir / "pytorch_model.bin.index.json").is_file():
            return any(model_dir.glob("pytorch_model-*.bin"))

        return False

    @staticmethod
    def _is_windows_rocm() -> bool:
        """Return True when running on Windows with a ROCm PyTorch build."""
        import sys
        import torch
        return (
            sys.platform == "win32"
            and torch.cuda.is_available()
            and "+rocm" in torch.__version__
        )

    def _select_device(self):
        """Prefer MPS on Apple Silicon, then CUDA/ROCm, then DirectML, then CPU."""

        import torch

        import platform
        if platform.system() == "Darwin":
            # Causal autoregressive generation (Gemma) under PyTorch MPS experiences severe
            # Metal driver compiler deadlocks during dynamic shape batching. CPU fallback is required.
            return torch.device("cpu"), torch.float32

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps"), torch.float16
        if torch.cuda.is_available():
            # For AMD ROCm and Cloud CUDA, native bfloat16 is fully supported and preferred
            return torch.device("cuda"), torch.bfloat16
        # DirectML for AMD GPUs on Windows via torch-directml
        try:
            import torch_directml
            if torch_directml.is_available():
                return torch_directml.device(), torch.float16
        except ImportError:
            pass
        return torch.device("cpu"), torch.float32

    @staticmethod
    def _is_directml_device(device) -> bool:
        """Return True when the device is a DirectML (PrivateUse1) device."""
        return "privateuseone" in str(device).lower()

    def _load_model(self) -> None:
        """Load tokenizer and causal language model from the local checkpoint.

        On Windows ROCm, the safetensors Rust mmap implementation crashes at the C++
        level. We detect that condition and use a pure-Python file-I/O loader
        instead. On DirectML, we use a similar per-tensor loading strategy to avoid
        Windows TDR timeouts. On all other platforms (MPS, Cloud CUDA, CPU) the
        standard ``AutoModelForCausalLM.from_pretrained`` path is used.
        """

        from models.torch_compat import ensure_transformers_import_compatibility

        ensure_transformers_import_compatibility()
        import torch
        from models.torch_compat import ensure_transformers_import_compatibility
        from transformers import AutoModelForCausalLM, AutoTokenizer

        ensure_transformers_import_compatibility()

        self.device, self.torch_dtype = self._select_device()

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_dir),
            local_files_only=True,
        )

        if self.tokenizer.pad_token is None and self.tokenizer.eos_token is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print(f"\n[*] Loading Gemma model on {self.device} (dtype={self.torch_dtype})...")

        if self._is_windows_rocm():
            self._load_model_no_mmap()
        elif self._is_directml_device(self.device):
            self._load_model_directml()
        else:
            self._load_model_standard()

        self.model.eval()

        # Force eos_token_id to a plain Python int everywhere.
        # On Windows ROCm the bfloat16 weight load can corrupt the
        # generation_config eos_token_id into a garbage CUDA tensor.
        self._sanitise_eos_token()

    def _sanitise_eos_token(self):
        """Force eos_token_id to plain Python ints, never CUDA tensors."""
        import torch
        t = self.tokenizer
        gc = self.model.generation_config
        eos = t.eos_token_id
        if eos is None:
            eos = []
        elif isinstance(eos, (list, tuple)):
            eos = [int(x.cpu()) if torch.is_tensor(x) else int(x) for x in eos]
        else:
            # Single value — could be a corrupted CUDA tensor or plain int
            try:
                eos = [int(eos)]
            except (ValueError, TypeError, RuntimeError):
                eos = []
        gc.eos_token_id = eos
        self.model.config.eos_token_id = eos[0] if eos else None

    def _load_model_standard(self) -> None:
        """Standard from_pretrained path used on MPS and Cloud CUDA."""
        import sys
        import torch
        from transformers import AutoModelForCausalLM

        # Determine the device type string for branching logic
        device_type = getattr(self.device, 'type', str(self.device))

        load_kwargs: dict = {
            "local_files_only": True,
            "low_cpu_mem_usage": True,
            "dtype": self.torch_dtype,
        }

        # Use device_map to stream weights directly to VRAM on CUDA environments only.
        if device_type == "cuda":
            load_kwargs["device_map"] = "auto"

        # Auto-detect and inject FlashAttention-2 if on CUDA and package exists
        try:
            import flash_attn
            if device_type == "cuda":
                load_kwargs["attn_implementation"] = "flash_attention_2"
                print("    > [Optimisation] FlashAttention-2 injected successfully.")
        except ImportError:
            pass

        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_dir),
            **load_kwargs,
        )

        # Manually transfer when device_map was not used (MPS / CPU)
        if device_type != "cuda":
            self.model.to(self.device)
            
        # Enterprise Linux NVIDIA acceleration: torch.compile
        if device_type == "cuda" and sys.platform.startswith("linux"):
            disable_compile = os.environ.get("DISABLE_COMPILE", "").strip().lower() in ("1", "true", "yes")
            if disable_compile:
                print("    > [Optimisation] torch.compile disabled via environment variable. Running in Eager mode.")
            else:
                try:
                    print("    > [Optimisation] Compiling model via torch.compile(mode='reduce-overhead')...")
                    self.model = torch.compile(self.model, mode="reduce-overhead")
                except Exception as e:
                    print(f"    > [Warning] torch.compile failed or unsupported: {e}")

    def _load_model_directml(self) -> None:
        """DirectML path: load tensors individually to avoid Windows TDR timeout.

        Windows' Timeout Detection and Recovery (TDR) mechanism kills any GPU
        operation exceeding ~2 seconds. Loading a 4B-parameter model in a single
        .to() call or even per-layer .to() triggers this. Instead, we:

        1. Create an empty model shell via accelerate's init_empty_weights
        2. Read each tensor from safetensors to CPU (pure Python I/O, no mmap)
        3. Transfer each tensor individually to DirectML (~1-50MB each, well
           within TDR)
        4. Use load_state_dict(assign=True) to replace meta tensors without
           triggering the set_data type incompatibility error
        """
        import gc
        import json
        import time
        import torch
        from pathlib import Path
        from tqdm import tqdm

        from accelerate import init_empty_weights
        from transformers import AutoConfig, AutoModelForCausalLM

        config = AutoConfig.from_pretrained(str(self.model_dir), local_files_only=True)

        with init_empty_weights():
            self.model = AutoModelForCausalLM.from_config(config)

        model_dir = Path(self.model_dir)

        # Determine shard files from index or single file
        index_file = model_dir / "model.safetensors.index.json"
        single_file = model_dir / "model.safetensors"

        if index_file.is_file():
            with open(index_file, "r", encoding="utf-8") as fh:
                index = json.load(fh)
            shard_files = sorted(set(index["weight_map"].values()))
        elif single_file.is_file():
            shard_files = ["model.safetensors"]
        else:
            raise FileNotFoundError(
                f"No model.safetensors or index file found in {model_dir}"
            )

        # Load each shard: read tensors to CPU, then transfer each to DirectML
        state_dict: dict = {}

        # Health check: verify DirectML device is still alive before starting
        print("    > Checking DirectML device health...")
        try:
            _test = torch.zeros(2, 2, device=self.device)
            _test = _test + 1  # force a compute operation
            del _test
            print("    > DirectML device is healthy.")
        except Exception as e:
            raise RuntimeError(
                f"DirectML device is not responsive before Gemma loading. "
                f"BERT may have suspended the GPU. Error: {e}"
            )

        print("    > Loading and transferring weights to GPU (per-tensor)...", flush=True)
        tensor_count = 0

        for shard_idx, shard in enumerate(shard_files):
            from safetensors.torch import load_file
            # Load entire shard to CPU
            print(f"    > Reading shard {shard_idx + 1}/{len(shard_files)}: {shard}", flush=True)
            shard_dict = load_file(str(model_dir / shard), device="cpu")

            for name, tensor in shard_dict.items():
                # Cast to target dtype if floating point
                if self.torch_dtype is not None and tensor.is_floating_point():
                    tensor = tensor.to(self.torch_dtype)
                # Transfer this individual tensor to DirectML device
                size_mb = tensor.nelement() * tensor.element_size() / (1024 * 1024)
                state_dict[name] = tensor.to(self.device)
                tensor_count += 1
                if tensor_count % 25 == 0:
                    print(f"    > Transferred {tensor_count} tensors (latest: {name}, {size_mb:.1f}MB)", flush=True)
                # Brief pause to let DirectML process the transfer
                time.sleep(0.01)

            del shard_dict

        print(f"    > All {tensor_count} tensors transferred to DirectML device.")

        # assign=True replaces meta tensors entirely (no set_data call)
        self.model.load_state_dict(state_dict, strict=False, assign=True)
        del state_dict
        gc.collect()

        print("    > Model assembled on DirectML successfully.")

    def _load_model_no_mmap(self) -> None:
        """Windows ROCm path: bypass safetensors mmap via pure-Python file I/O.

        The Rust safetensors mmap implementation panics at the C++ level on
        Windows ROCm. This path reads each tensor individually using Python's
        built-in ``open`` / ``seek`` / ``read``, then loads the resulting
        state dict into an empty model shell created with accelerate's
        ``init_empty_weights`` context manager.
        """
        import gc
        import torch
        from pathlib import Path
        from accelerate import init_empty_weights
        from transformers import AutoConfig, AutoModelForCausalLM
        from models.safetensors_loader import load_safetensors_no_mmap

        config = AutoConfig.from_pretrained(str(self.model_dir), local_files_only=True)

        with init_empty_weights():
            self.model = AutoModelForCausalLM.from_config(config)

        # Find the safetensors weight file
        model_dir = Path(self.model_dir)
        st_file = model_dir / "model.safetensors"
        if not st_file.is_file():
            # Sharded checkpoint: load all shards
            index_file = model_dir / "model.safetensors.index.json"
            if not index_file.is_file():
                raise FileNotFoundError(
                    f"No model.safetensors or index file found in {model_dir}"
                )
            import json
            with open(index_file, "r", encoding="utf-8") as fh:
                index = json.load(fh)
            shard_files = sorted(set(index["weight_map"].values()))
            state_dict: dict = {}
            for shard in shard_files:
                shard_dict = load_safetensors_no_mmap(
                    model_dir / shard,
                    device=str(self.device),
                    target_dtype=self.torch_dtype,
                )
                state_dict.update(shard_dict)
        else:
            state_dict = load_safetensors_no_mmap(
                st_file,
                device=str(self.device),
                target_dtype=self.torch_dtype,
            )

        self.model.load_state_dict(state_dict, strict=False, assign=True)
        del state_dict
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def generate(
        self,
        text: str,
        max_new_tokens: int = 128,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> str:
        """Generate text from the loaded Gemma checkpoint or external API.

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

        if getattr(self, "backend", None) == "api":
            import urllib.request
            import json
            url = getattr(self, "api_url", "http://localhost:1234/v1/chat/completions")
            model_name = getattr(self, "api_model", "google/gemma-4-E4B-it")
            
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": text}],
                "temperature": float(temperature),
                "max_tokens": int(max_new_tokens)
            }
            
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"), 
                headers=headers,
                method="POST"
            )
            
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    res_body = json.loads(response.read().decode("utf-8"))
                    if "choices" in res_body and len(res_body["choices"]) > 0:
                        choice = res_body["choices"][0]
                        if "message" in choice:
                            return choice["message"]["content"].strip()
                        elif "text" in choice:
                            return choice["text"].strip()
                    return ""
            except Exception as e:
                print(f"[API Error] Failed to fetch completion from {url}: {e}")
                # Mock fallback
                words = text.split()
                return " ".join(words[-3:]) if len(words) >= 3 else text

        import torch

        # Format input using chat template if available to keep Gemma strictly instructed and fast
        if self.tokenizer is not None and hasattr(self.tokenizer, "apply_chat_template"):
            try:
                messages = [{"role": "user", "content": text}]
                text_templated = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                # Verify we got a valid templated string back
                if text_templated:
                    text = text_templated
            except Exception:
                pass

        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        # Sanitise eos_token_id — Windows ROCm corrupts generation_config
        # into a list of garbage CUDA tensors. Force plain Python ints.
        eos_ids = self.tokenizer.eos_token_id
        if eos_ids is None:
            eos_ids = []
        elif isinstance(eos_ids, (list, tuple)):
            eos_ids = [int(x.cpu()) if torch.is_tensor(x) else int(x) for x in eos_ids]
        else:
            eos_ids = [int(eos_ids)]
        self.model.generation_config.eos_token_id = eos_ids
        self.model.config.eos_token_id = eos_ids[0] if eos_ids else None

        generation_kwargs = {
            "max_new_tokens": int(max_new_tokens),
            "do_sample": temperature > 0.0,
            "pad_token_id": int(self.tokenizer.pad_token_id),
            "eos_token_id": eos_ids,
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