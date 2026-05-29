import time
import os
from typing import ClassVar, Dict, List, Tuple
from models.device_selector import get_device_info
from models.torch_compat import ensure_transformers_import_compatibility

# Keep BLAS thread count conservative to avoid OpenBLAS allocation spikes on Windows.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

class BERTModel:
    _instance_cache: ClassVar[Dict[Tuple[bool], "BERTModel"]] = {}

    def __new__(cls, allow_internet: bool = True):
        cache_key = (bool(allow_internet),)
        instance = cls._instance_cache.get(cache_key)
        if instance is None:
            instance = super().__new__(cls)
            cls._instance_cache[cache_key] = instance
            instance._initialized = False
        return instance

    def __init__(self, allow_internet: bool = True):
        if getattr(self, "_initialized", False):
            return

        self.device_info = get_device_info()
        self.device = self.device_info["device"]
        if self.device in ["cuda", "rocm"]:
            self.torch_device = "cuda"
        elif self.device == "mps":
            self.torch_device = "mps"
        else:
            self.torch_device = "cpu"

        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.tokenizer = None
        self.model = None
        self.is_loaded = False
        self.model_source = "unknown"
        self.allow_internet = allow_internet
        self._compiled_encode_active = False
        self._embedding_cache: Dict[str, List[float]] = {}
        self._initialize()
        self._initialized = True

    def _initialize(self):
        try:
            ensure_transformers_import_compatibility()
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            # Prefer local cache first.
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
                self.model = AutoModel.from_pretrained(self.model_name, local_files_only=True)
                self.model_source = "local"
            except Exception as local_error:
                if not self.allow_internet:
                    raise local_error

                print(f"[BERT] Local cache missing; downloading {self.model_name} once so it can be reused locally.")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=False)
                self.model = AutoModel.from_pretrained(self.model_name, local_files_only=False)
                self.model_source = "downloaded"

            # Cast model parameters and move them to GPU/target device.
            # Using float16 enables highly optimized, functional GPU kernel paths on Windows ROCm.
            if self.torch_device == "cuda":
                dtype = torch.float16  # Force float16 for maximum kernel compatibility on AMD ROCm Windows
                print(f"\n[*] Mapping BERT model to {self.torch_device} in {dtype} format...")
                self.model = self.model.to(dtype=dtype, device=self.torch_device)
            else:
                self.model = self.model.to(self.torch_device)
            
            self.model.eval()
            self.is_loaded = True

            # Keep an eager reference so we can recover if compilation fails at runtime.
            self._encode_eager = self._encode

            # torch.compile — enable only when explicitly requested.
            import torch
            enable_compile = (
                hasattr(torch, 'compile') and
                os.getenv('RAP_ENABLE_TORCH_COMPILE', '').strip().lower() in ('1', 'true', 'yes')
            )
            if enable_compile:
                try:
                    self._encode = torch.compile(self._encode, mode="reduce-overhead")
                    self._compiled_encode_active = True
                except Exception as e:
                    print(f"[BERT] Warning: torch.compile disabled ({e}). Using eager mode.")
                    self._encode = self._encode_eager
                    self._compiled_encode_active = False

        except Exception as local_error:
            mode = "internet fallback disabled" if not self.allow_internet else "internet fallback exhausted"
            print(f"[BERT] Warning: Failed to load BERT model ({local_error}). {mode}; using mock/fallback embedding generator.")
            self.is_loaded = False
            self.model_source = "unavailable"

    def clear_caches(self) -> None:
        self._embedding_cache.clear()

    def _encode(self, texts: List[str]):
        """Mean‑pooled, normalized embeddings for a batch of texts."""
        import torch
        import torch.nn.functional as F

        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
        
        # Map inputs to GPU, converting 64-bit integers to 32-bit integers to avoid AMD ROCm embedding kernel crashes
        inputs = {
            k: v.to(device=self.torch_device, dtype=torch.int32 if v.dtype == torch.int64 else v.dtype) 
            for k, v in inputs.items()
        }
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            token_embeddings = outputs[0]  # last hidden state
            attention_mask = inputs["attention_mask"]
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).to(token_embeddings.dtype)
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embeddings = sum_embeddings / sum_mask
            # L2 normalise
            embeddings = F.normalize(embeddings, p=2, dim=1)
        return embeddings.cpu().float().numpy().tolist()

    def get_embedding(self, text: str):
        """
        Generates embedding for a single text string.
        """
        text = str(text)

        cached_embedding = self._embedding_cache.get(text)
        if cached_embedding is not None:
            return cached_embedding

        if not self.is_loaded:
            import math
            mock_emb = [0.0] * 384
            for i, char in enumerate(text):
                mock_emb[ord(char) % 384] += 1.0 + math.sin(i)
            norm = sum(x**2 for x in mock_emb) ** 0.5
            if norm > 0:
                mock_emb = [x / norm for x in mock_emb]
            self._embedding_cache[text] = mock_emb
            return mock_emb

        try:
            embedding = self._encode([text])[0]
            self._embedding_cache[text] = embedding
            return embedding
        except Exception as e:
            # If a compiled graph fails at runtime, transparently fall back to eager mode.
            if getattr(self, '_compiled_encode_active', False):
                print(f"[BERT] Warning: compiled encode failed ({e}); falling back to eager mode.")
                self._encode = self._encode_eager
                self._compiled_encode_active = False
                embedding = self._encode([text])[0]
                self._embedding_cache[text] = embedding
                return embedding
            raise

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embedding generation – essential for MPS throughput.
        """
        normalized_texts = [str(t) for t in texts]
        if not normalized_texts:
            return []

        cached_embeddings = [self._embedding_cache.get(text) for text in normalized_texts]
        missing_texts = []
        missing_indices = []
        for index, (text, cached) in enumerate(zip(normalized_texts, cached_embeddings)):
            if cached is None:
                missing_texts.append(text)
                missing_indices.append(index)

        if missing_texts:
            if not self.is_loaded:
                computed_embeddings = [self.get_embedding(text) for text in missing_texts]
            else:
                try:
                    computed_embeddings = self._encode(missing_texts)
                except Exception as e:
                    if getattr(self, '_compiled_encode_active', False):
                        print(f"[BERT] Warning: compiled batch encode failed ({e}); falling back to eager mode.")
                        self._encode = self._encode_eager
                        self._compiled_encode_active = False
                        computed_embeddings = self._encode(missing_texts)
                    else:
                        raise

            for text, embedding in zip(missing_texts, computed_embeddings):
                self._embedding_cache[text] = embedding

        return [self._embedding_cache[text] for text in normalized_texts]

    def cosine_similarity(self, text1: str, text2: str) -> float:
        """
        Computes cosine similarity between two texts and normalizes it to [0, 1].
        """
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        # Since L2 normalised, dot product is cosine similarity in [-1, 1]
        normalized_sim = (dot_product + 1.0) / 2.0
        return min(max(normalized_sim, 0.0), 1.0)
