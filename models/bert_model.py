import time
from models.device_selector import get_device_info
from models.torch_compat import ensure_transformers_import_compatibility

class BERTModel:
    def __init__(self):
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
        self._initialize()

    def _initialize(self):
        try:
            ensure_transformers_import_compatibility()
            import torch
            from transformers import AutoTokenizer, AutoModel
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
            self.model = AutoModel.from_pretrained(self.model_name, local_files_only=True)
            self.model.to(self.torch_device)
            self.model.eval()
            self.is_loaded = True
        except Exception as e:
            print(f"[BERT] Warning: Failed to load local BERT model ({e}). Using mock/fallback embedding generator.")
            self.is_loaded = False

    def get_embedding(self, text: str):
        """
        Generates embedding for a single text string.
        """
        if not self.is_loaded:
            # High-fidelity mock embedding based on character frequencies
            import math
            mock_emb = [0.0] * 384
            for i, char in enumerate(text):
                mock_emb[ord(char) % 384] += 1.0 + math.sin(i)
            # L2 normalize
            norm = sum(x**2 for x in mock_emb) ** 0.5
            if norm > 0:
                mock_emb = [x / norm for x in mock_emb]
            return mock_emb

        import torch
        import torch.nn.functional as F
        
        with torch.no_grad():
            inputs = self.tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt")
            inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            
            # Mean Pooling
            token_embeddings = outputs[0]
            attention_mask = inputs["attention_mask"]
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            embeddings = sum_embeddings / sum_mask
            
            # Normalize
            embeddings = F.normalize(embeddings, p=2, dim=1)
            return embeddings[0].cpu().numpy().tolist()

    def cosine_similarity(self, text1: str, text2: str) -> float:
        """
        Computes cosine similarity between two texts and normalizes it to [0, 1].
        """
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        
        # Since we L2 normalized the embeddings, cosine similarity is simply the dot product.
        # Normalize from [-1, 1] to [0, 1]
        normalized_sim = (dot_product + 1.0) / 2.0
        return min(max(normalized_sim, 0.0), 1.0)
