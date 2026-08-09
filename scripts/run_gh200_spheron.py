#!/usr/bin/env python3
"""Measured v8 CUDA benchmark entry point for NVIDIA GH200 Grace Hopper."""
import sys
from run_nvidia_v8_benchmark import main

if __name__ == "__main__":
    sys.argv[0] = "run_nvidia_v8_benchmark.py"
    main()
