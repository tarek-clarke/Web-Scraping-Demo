#!/usr/bin/env python3
"""
Example usage of ModelManager across different platforms.
"""

import os
from src.inference import ModelManager, generate_response


def example_basic():
    """Basic usage - auto-detects platform and loads model."""
    print("\n=== Basic Usage ===")
    
    # Initialize (auto-detects hardware)
    manager = ModelManager()
    
    # Generate response
    prompt = "Explain quantum computing in one sentence."
    response = manager.generate_response(prompt, max_new_tokens=100)
    
    print(f"Prompt: {prompt}")
    print(f"Response: {response}")


def example_spheron():
    """Spheron cloud usage with HF mirror."""
    print("\n=== Spheron Cloud Usage ===")
    
    # Set environment for Spheron (if HF is blocked)
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # Example mirror
    os.environ["HF_MODEL_ID"] = "google/gemma-4-12B-it"  # Larger model for cloud
    
    manager = ModelManager()
    response = manager.generate_response(
        "What is the capital of France?",
        max_new_tokens=50,
        temperature=0.7
    )
    
    print(f"Response: {response}")


def example_lumi():
    """LUMI HPC usage with AMD ROCm."""
    print("\n=== LUMI HPC Usage ===")
    
    # LUMI-specific configuration
    os.environ["IS_LUMI"] = "1"
    os.environ["HF_MODEL_ID"] = "google/gemma-4-12B-it"
    
    manager = ModelManager()
    
    # Batch processing example
    prompts = [
        "What is machine learning?",
        "Explain neural networks.",
        "What is deep learning?"
    ]
    
    for prompt in prompts:
        response = manager.generate_response(prompt, max_new_tokens=100)
        print(f"Q: {prompt}")
        print(f"A: {response}\n")


def example_local_with_fallback():
    """Local usage with local model fallback."""
    print("\n=== Local with Fallback ===")
    
    # Try local model first, fall back to HF
    os.environ["HF_LOCAL_MODEL_PATH"] = "./models/gemma-4-E4B-it"
    os.environ["HF_MODEL_ID"] = "google/gemma-4-E4B-it"
    
    manager = ModelManager()
    response = manager.generate_response("Hello, world!")
    
    print(f"Response: {response}")


def example_offline_mode():
    """Offline mode - use cached models only."""
    print("\n=== Offline Mode ===")
    
    os.environ["HF_HUB_OFFLINE"] = "1"  # Only use cached models
    os.environ["HF_MODEL_ID"] = "google/gemma-4-E4B-it"
    
    manager = ModelManager()
    response = manager.generate_response("Test offline mode")
    
    print(f"Response: {response}")


def example_streaming():
    """Streaming generation example."""
    print("\n=== Streaming Generation ===")
    
    manager = ModelManager()
    
    prompt = "Write a short story about a robot:"
    print(f"Prompt: {prompt}")
    print("Response: ", end="", flush=True)
    
    # Stream tokens as they're generated
    for token in manager.generate_stream(prompt, max_new_tokens=200):
        print(token, end="", flush=True)
    
    print("\n")


def example_simple_function():
    """Simple function-based usage (no manager instance)."""
    print("\n=== Simple Function Usage ===")
    
    # One-liner generation
    response = generate_response(
        "What is 2 + 2?",
        max_new_tokens=20,
        temperature=0.1  # Low temperature for deterministic output
    )
    
    print(f"Response: {response}")


if __name__ == "__main__":
    # Run the example that matches your platform
    # Uncomment the one you want to test
    
    example_basic()
    # example_spheron()
    # example_lumi()
    # example_local_with_fallback()
    # example_offline_mode()
    # example_streaming()
    # example_simple_function()
