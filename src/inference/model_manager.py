"""
Multi-platform model manager for Hugging Face transformers.
Supports Apple Silicon (MPS), NVIDIA CUDA, and AMD ROCm (LUMI), Spheron Cloud.
"""

import os
import sys
import time
import torch
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class BackendConfig:
    """Configuration for a specific hardware backend."""
    device: str
    dtype: torch.dtype
    attn_implementation: str
    use_bitsandbytes: bool
    device_map: str
    description: str
    platform: str  # "local", "vast", "lumi", "spheron"


def detect_platform() -> str:
    """Detect cloud platform from environment variables."""
    if os.environ.get("IS_LUMI", "").lower() in ("1", "true", "yes"):
        return "lumi"
    if os.environ.get("SPHERON_INSTANCE_ID") or os.environ.get("SPHERON"):
        return "spheron"
    if os.environ.get("VAST_AI_APIKEY") or os.environ.get("VAST"):
        return "vast"
    return "local"


def detect_backend() -> BackendConfig:
    """
    Auto-detect hardware backend and return optimal configuration.
    
    Detection hierarchy:
    1. NVIDIA CUDA (torch.cuda + NVIDIA device)
    2. AMD ROCm (torch.cuda + AMD/HIP device or IS_LUMI env)
    3. Apple Silicon MPS (torch.backends.mps)
    4. CPU fallback
    """
    
    platform = detect_platform()
    
    # Check for explicit LUMI override
    is_lumi = platform == "lumi"
    
    # Check CUDA availability
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0).lower()
        
        # AMD ROCm (LUMI MI250X or other AMD GPUs)
        if is_lumi or "amd" in device_name or "hip" in device_name or "mi250" in device_name:
            return BackendConfig(
                device="cuda",
                dtype=torch.bfloat16,
                attn_implementation="sdpa",  # AMD-compatible attention
                use_bitsandbytes=False,  # bitsandbytes not supported on ROCm
                device_map="auto",
                description="AMD ROCm (LUMI)",
                platform=platform
            )
        
        # NVIDIA CUDA
        if "nvidia" in device_name:
            return BackendConfig(
                device="cuda",
                dtype=torch.bfloat16,
                attn_implementation="flash_attention_2",
                use_bitsandbytes=True,
                device_map="auto",
                description="NVIDIA CUDA",
                platform=platform
            )
    
    # Apple Silicon MPS
    if torch.backends.mps.is_available() and sys.platform == "darwin":
        return BackendConfig(
            device="mps",
            dtype=torch.float16,
            attn_implementation="sdpa",
            use_bitsandbytes=True,  # Optional for MPS
            device_map="auto",
            description="Apple Silicon (MPS)",
            platform=platform
        )
    
    # CPU fallback
    return BackendConfig(
        device="cpu",
        dtype=torch.float32,
        attn_implementation="eager",
        use_bitsandbytes=False,
        device_map="cpu",
        description="CPU",
        platform=platform
    )


class ModelManager:
    """
    Multi-platform model manager with automatic hardware detection.
    
    Environment variables:
        HF_MODEL_ID: Model identifier (default: google/gemma-4-E4B-it)
        HF_TOKEN: Hugging Face API token
        HF_ENDPOINT: Custom Hugging Face endpoint (for mirrors/proxies)
        HF_HUB_OFFLINE: Use cached models only (1/true/yes)
        HF_LOCAL_MODEL_PATH: Local path to model (fallback if HF unavailable)
        LLM_MAX_REASONING_TOKENS: Max tokens for generation (default: 2048)
        IS_LUMI: Explicit LUMI/ROCm flag (1/true/yes)
        SPHERON_INSTANCE_ID: Spheron instance ID (auto-detected)
        
    Platform-specific notes:
        - Spheron: Set HF_ENDPOINT to use mirror if direct HF access is blocked
        - LUMI: Set IS_LUMI=1 for AMD ROCm backend
        - Local: Models auto-cached to ~/.cache/huggingface/
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern - only one instance per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize model manager with auto-detected backend."""
        if self._initialized:
            return
        
        # Environment configuration
        self.model_id = os.environ.get("HF_MODEL_ID", "google/gemma-4-E4B-it")
        self.hf_token = os.environ.get("HF_TOKEN")
        self.hf_endpoint = os.environ.get("HF_ENDPOINT")
        self.hf_offline = os.environ.get("HF_HUB_OFFLINE", "").lower() in ("1", "true", "yes")
        self.local_model_path = os.environ.get("HF_LOCAL_MODEL_PATH")
        self.max_tokens = int(os.environ.get("LLM_MAX_REASONING_TOKENS", "2048"))
        
        # Hardware detection
        self.backend = detect_backend()
        
        # Model state
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        
        # Check if we're in a distributed context (Slurm/PyTorch DDP)
        self.is_distributed = torch.distributed.is_initialized() if hasattr(torch.distributed, 'is_initialized') else False
        self.is_rank_zero = not self.is_distributed or torch.distributed.get_rank() == 0
        
        self._initialized = True
        
        if self.is_rank_zero:
            print(f"[INFO] ModelManager initialized")
            print(f"[INFO]   Platform: {self.backend.platform}")
            print(f"[INFO]   Backend: {self.backend.description}")
            print(f"[INFO]   Device: {self.backend.device}")
            print(f"[INFO]   Dtype: {self.backend.dtype}")
            print(f"[INFO]   Attention: {self.backend.attn_implementation}")
            print(f"[INFO]   BitsAndBytes: {self.backend.use_bitsandbytes}")
            print(f"[INFO]   Model: {self.model_id}")
            if self.hf_endpoint:
                print(f"[INFO]   HF Endpoint: {self.hf_endpoint}")
            if self.hf_offline:
                print(f"[INFO]   HF Offline: enabled (using cached models only)")
            if self.local_model_path:
                print(f"[INFO]   Local model path: {self.local_model_path}")
            if self.is_distributed:
                print(f"[INFO]   Distributed: rank {torch.distributed.get_rank()}/{torch.distributed.get_world_size()}")
    
    def load(self, max_retries: int = 3, retry_delay: float = 5.0) -> bool:
        """
        Load model and tokenizer with backend-specific configuration.
        
        Args:
            max_retries: Maximum number of retry attempts for network failures
            retry_delay: Seconds to wait between retries
            
        Returns:
            True if successful, False otherwise
        """
        if self.is_loaded:
            return True
        
        # Try local path first if specified
        if self.local_model_path and Path(self.local_model_path).exists():
            if self.is_rank_zero:
                print(f"[INFO] Loading from local path: {self.local_model_path}")
            if self._load_from_path(self.local_model_path):
                return True
            if self.is_rank_zero:
                print(f"[WARN] Local path failed, trying Hugging Face...")
        
        # Try Hugging Face with retries
        last_error = None
        for attempt in range(max_retries):
            try:
                if self.is_rank_zero and attempt > 0:
                    print(f"[INFO] Retry attempt {attempt + 1}/{max_retries}...")
                
                if self._load_from_huggingface():
                    return True
                    
            except Exception as e:
                last_error = e
                if self.is_rank_zero:
                    print(f"[WARN] Load attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        # All retries failed
        if self.is_rank_zero:
            print(f"[ERROR] Failed to load model after {max_retries} attempts")
            if last_error:
                print(f"[ERROR] Last error: {last_error}")
                import traceback
                traceback.print_exc()
        return False
    
    def _load_from_huggingface(self) -> bool:
        """Load model from Hugging Face Hub (or custom endpoint)."""
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        # Configure HF endpoint if specified
        if self.hf_endpoint:
            os.environ["HF_ENDPOINT"] = self.hf_endpoint
        
        # Configure offline mode if specified
        if self.hf_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
        
        # Build model kwargs based on backend
        model_kwargs: Dict[str, Any] = {
            "dtype": self.backend.dtype,
            "device_map": self.backend.device_map,
            "attn_implementation": self.backend.attn_implementation,
        }
        
        # Add Hugging Face token if provided
        if self.hf_token:
            model_kwargs["token"] = self.hf_token
        
        # Add quantization if supported and requested
        if self.backend.use_bitsandbytes:
            try:
                from transformers import BitsAndBytesConfig
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=self.backend.dtype,
                    bnb_4bit_use_double_quant=True,
                )
                model_kwargs["quantization_config"] = quantization_config
                if self.is_rank_zero:
                    print(f"[INFO]   Quantization: 4-bit (NF4)")
            except ImportError:
                if self.is_rank_zero:
                    print("[WARN] bitsandbytes not available, loading full precision")
        
        # Load model
        if self.is_rank_zero:
            print(f"[INFO] Loading model: {self.model_id}")
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            **model_kwargs
        )
        
        # Load tokenizer
        tokenizer_kwargs = {}
        if self.hf_token:
            tokenizer_kwargs["token"] = self.hf_token
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            **tokenizer_kwargs
        )
        
        # Ensure tokenizer has pad token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        self.is_loaded = True
        
        if self.is_rank_zero:
            print(f"[INFO] Model loaded successfully")
            if hasattr(self.model, 'device'):
                print(f"[INFO]   Model device: {self.model.device}")
            if hasattr(self.model, 'hf_device_map'):
                print(f"[INFO]   Device map: {self.model.hf_device_map}")
        
        return True
    
    def _load_from_path(self, path: str) -> bool:
        """Load model from a local path."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            # Build model kwargs based on backend
            model_kwargs: Dict[str, Any] = {
                "dtype": self.backend.dtype,
                "device_map": self.backend.device_map,
                "attn_implementation": self.backend.attn_implementation,
            }
            
            # Add quantization if supported and requested
            if self.backend.use_bitsandbytes:
                try:
                    from transformers import BitsAndBytesConfig
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=self.backend.dtype,
                        bnb_4bit_use_double_quant=True,
                    )
                    model_kwargs["quantization_config"] = quantization_config
                except ImportError:
                    pass
            
            self.model = AutoModelForCausalLM.from_pretrained(path, **model_kwargs)
            self.tokenizer = AutoTokenizer.from_pretrained(path)
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.is_loaded = True
            
            if self.is_rank_zero:
                print(f"[INFO] Model loaded from local path: {path}")
            
            return True
            
        except Exception as e:
            if self.is_rank_zero:
                print(f"[ERROR] Failed to load from local path: {e}")
            return False
    
    def generate_response(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        do_sample: bool = True,
        stream: bool = False
    ) -> str:
        """
        Generate text response from prompt.
        
        Args:
            prompt: Input text prompt
            max_new_tokens: Maximum tokens to generate (default: from env)
            temperature: Sampling temperature (0.0 = greedy, 1.0 = default)
            top_p: Nucleus sampling probability
            do_sample: Whether to use sampling (False = greedy decoding)
            stream: Whether to stream output (not yet implemented)
        
        Returns:
            Generated text response
        """
        if not self.is_loaded:
            if not self.load():
                return "[ERROR] Model not loaded"
        
        # Apply chat template
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Tokenize
        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_tokens
        )
        
        # Move to device
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        # Generation kwargs
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "do_sample": do_sample,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                **gen_kwargs
            )
        
        # Decode response (skip input tokens)
        input_length = inputs["input_ids"].shape[1]
        response_ids = outputs[0][input_length:]
        response = self.tokenizer.decode(response_ids, skip_special_tokens=True)
        
        return response.strip()
    
    def generate_stream(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        do_sample: bool = True
    ):
        """
        Stream text generation token by token.
        
        Yields:
            Generated tokens as they are produced
        """
        if not self.is_loaded:
            if not self.load():
                yield "[ERROR] Model not loaded"
                return
        
        # Apply chat template
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Tokenize
        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_tokens
        )
        
        # Move to device
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        # Generation kwargs
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "do_sample": do_sample,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        
        # Stream generation
        from transformers import TextIteratorStreamer
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True
        )
        
        # Run generation in separate thread for streaming
        import threading
        generation_kwargs = {**inputs, **gen_kwargs, "streamer": streamer}
        thread = threading.Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()
        
        # Yield tokens as they're generated
        for text in streamer:
            yield text
        
        thread.join()
    
    def reset_kv_cache(self):
        """Clear KV cache to free memory."""
        if self.model and hasattr(self.model, 'reset_kv_cache'):
            self.model.reset_kv_cache()
    
    def unload(self):
        """Unload model and free memory."""
        if self.model is not None:
            del self.model
            self.model = None
        
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        
        self.is_loaded = False
        
        # Clear CUDA cache if applicable
        if self.backend.device == "cuda" and torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        if self.is_rank_zero:
            print("[INFO] Model unloaded")


# Convenience function for simple usage
def generate_response(
    prompt: str,
    max_new_tokens: Optional[int] = None,
    temperature: float = 0.7,
    top_p: float = 0.9,
    do_sample: bool = True
) -> str:
    """
    Simple function to generate a response.
    
    Args:
        prompt: Input text prompt
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        top_p: Nucleus sampling probability
        do_sample: Whether to use sampling
    
    Returns:
        Generated text response
    """
    manager = ModelManager()
    return manager.generate_response(
        prompt,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        do_sample=do_sample
    )
