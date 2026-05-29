#!/usr/bin/env python3
"""
scripts/check_models_cached.py

Simple smoke-test to verify required model weights are cached locally.
Exits 0 when both BERT MiniLM and Gemma are loadable with local_files_only=True,
otherwise exits non-zero and prints diagnostics.
"""
import sys

def check_bert():
    try:
        from transformers import AutoTokenizer, AutoModel
        AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
        AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
        print("[OK] BERT MiniLM cached locally")
        return True
    except Exception as e:
        print(f"[MISSING] BERT MiniLM not cached: {e}")
        return False

def check_gemma():
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        repo_id = "google/gemma-4-E4B"
        AutoTokenizer.from_pretrained(repo_id, local_files_only=True)
        AutoModelForCausalLM.from_pretrained(repo_id, local_files_only=True)
        print("[OK] Gemma model cached locally")
        return True
    except Exception as e:
        print(f"[MISSING] Gemma model not cached: {e}")
        return False


def main():
    ok = True
    if not check_bert():
        ok = False
    if not check_gemma():
        ok = False
    if ok:
        print("All required models are present in the local cache.")
        sys.exit(0)
    else:
        print("One or more required models are missing from the local cache.")
        sys.exit(2)


if __name__ == '__main__':
    main()
