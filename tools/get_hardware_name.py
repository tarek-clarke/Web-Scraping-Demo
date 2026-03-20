#!/usr/bin/env python3
try:
    import torch
except ImportError:
    torch = None
import re
import platform
import subprocess
import os
from typing import Optional, Dict, Any

def _sanitize_suffix_token(raw: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "", raw or "")
    return token[:40]

def _detect_cpu_suffix() -> str:
    brand = ""
    if platform.system() == "Darwin":
        try:
            brand = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
            m = re.search(r"Apple\s+(M\d+)", brand, flags=re.IGNORECASE)
            if m: return m.group(1).upper()
        except Exception: pass
    elif platform.system() == "Windows":
        try:
            out = subprocess.check_output(["wmic", "cpu", "get", "name"], text=True, stderr=subprocess.DEVNULL).strip()
            lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip().lower() != "name"]
            brand = lines[0] if lines else ""
        except Exception: pass
    else:
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line.lower():
                        brand = line.split(":", 1)[1].strip()
                        break
        except Exception: brand = platform.processor()

    if brand:
        m = re.search(r"(i[3579]-\d{4,5}[A-Z]*)", brand, re.IGNORECASE)
        if m: return _sanitize_suffix_token(m.group(1))
        m = re.search(r"Ryzen\s+\d+\s+(\d{4,5}[A-Z0-9]*)", brand, re.IGNORECASE)
        if m: return _sanitize_suffix_token(m.group(1))
        m = re.search(r"\b(\d{4,5}[A-Z]+)\b", brand)
        if m: return m.group(1)
        return _sanitize_suffix_token(brand)
    return "CPU"

def _detect_hardware_suffix() -> str:
    env_override = os.environ.get("RAP_OUTPUT_SUFFIX", "").strip()
    if env_override: return _sanitize_suffix_token(env_override)

    name = ""
    if torch is not None and torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
    
    if not name:
        return _detect_cpu_suffix()

    upper_name = name.upper()
    if "7900" in upper_name and "XT" in upper_name: return "7900XT"
    if "MI300" in upper_name: return "MI300"
    if "MI250" in upper_name: return "MI250"
    if "RTX" in upper_name:
        m = re.search(r"RTX\s*(\d{3,4})", upper_name)
        return f"RTX{m.group(1)}" if m else "RTX"
    if "A100" in upper_name: return "A100"
    if "H200" in upper_name: return "H200"
    if "H100" in upper_name: return "H100"

    return _sanitize_suffix_token(name.upper())

if __name__ == "__main__":
    print(_detect_hardware_suffix())
