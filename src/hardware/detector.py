import platform
import subprocess
import json
from typing import Dict

class HardwareDetector:
    HARDWARE_PROFILES = {
        "12600K": {"vram_gb": 0, "type": "cpu", "os": ["windows"]},
        "7900XT": {"vram_gb": 20, "type": "rocm", "os": ["windows", "linux"]},
        "M4": {"vram_gb": 16, "type": "silicon", "os": ["darwin"]},
        "H100": {"vram_gb": 80, "type": "cuda", "os": ["linux"]},
        "A100": {"vram_gb": 80, "type": "cuda", "os": ["linux"]},
        "RTX5090": {"vram_gb": 32, "type": "cuda", "os": ["windows", "linux"]},
        "RTX6000": {"vram_gb": 48, "type": "cuda", "os": ["windows", "linux"]},
        "GH200": {"vram_gb": 96, "type": "cuda", "os": ["linux"]},
        "B300": {"vram_gb": 288, "type": "cuda", "os": ["linux"]},
        "MI250X": {"vram_gb": 128, "type": "rocm", "os": ["linux"]}
    }

    def detect(self) -> Dict:
        system = platform.system().lower()
        profile = self._detect_gpu(system)
        profile["os"] = system
        return profile

    def _detect_gpu(self, system: str) -> Dict:
        if system == "darwin":
            return self._detect_apple_silicon()
        
        nvidia = self._detect_nvidia()
        if nvidia["type"] != "cpu":
            return nvidia
        
        amd = self._detect_amd()
        if amd["type"] != "cpu":
            return amd
        
        return {"type": "cpu", "vram_gb": 0, "model": "CPU"}

    def _detect_apple_silicon(self) -> Dict:
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True
            )
            cpu = result.stdout.strip()
            if "M4" in cpu or "M3" in cpu or "M2" in cpu or "M1" in cpu:
                mem_result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True
                )
                mem_gb = int(mem_result.stdout.strip()) // (1024**3)
                return {"type": "silicon", "vram_gb": mem_gb, "model": cpu}
        except:
            pass
        return {"type": "cpu", "vram_gb": 0, "model": "CPU"}

    def _detect_nvidia(self) -> Dict:
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_gb = mem_info.total // (1024**3)
            pynvml.nvmlShutdown()
            
            for model, profile in self.HARDWARE_PROFILES.items():
                if model.lower() in name.lower():
                    return {"type": "cuda", "vram_gb": vram_gb, "model": name}
            
            return {"type": "cuda", "vram_gb": vram_gb, "model": name}
        except:
            return {"type": "cpu", "vram_gb": 0, "model": "CPU"}

    def _detect_amd(self) -> Dict:
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True, text=True
            )
            output = result.stdout
            if "MI250X" in output:
                return {"type": "rocm", "vram_gb": 128, "model": "MI250X"}
            elif "7900XT" in output or "RX 7900" in output:
                return {"type": "rocm", "vram_gb": 20, "model": "7900XT"}
        except:
            pass
        return {"type": "cpu", "vram_gb": 0, "model": "CPU"}
