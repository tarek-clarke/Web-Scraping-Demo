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
        "GH300": {"vram_gb": 288, "type": "cuda", "os": ["linux"]},
        "GB300": {"vram_gb": 288, "type": "cuda", "os": ["linux"]},
        "B300": {"vram_gb": 288, "type": "cuda", "os": ["linux"]},
        "MI250X": {"vram_gb": 128, "type": "rocm", "os": ["linux"]}
    }

    def detect(self) -> Dict:
        system = platform.system().lower()
        profile = self._detect_gpu(system)
        profile["os"] = system
        profile["driver"] = self._detect_driver(profile["type"])
        profile["python_version"] = platform.python_version()
        profile["cpu"] = self._detect_cpu()
        profile["motherboard"] = self._detect_motherboard(system)
        return profile

    def _detect_cpu(self) -> str:
        try:
            if platform.system().lower() == "darwin":
                r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
                return r.stdout.strip()
            elif platform.system().lower() == "linux":
                r = subprocess.run(["lscpu"], capture_output=True, text=True)
                for line in r.stdout.split("\n"):
                    if "Model name" in line:
                        return line.split(":")[-1].strip()
                return platform.processor()
            elif platform.system().lower() == "windows":
                r = subprocess.run(["wmic", "cpu", "get", "name"], capture_output=True, text=True)
                lines = r.stdout.strip().split("\n")
                return lines[1].strip() if len(lines) > 1 else platform.processor()
            return platform.processor()
        except:
            return platform.processor()

    def _detect_motherboard(self, system: str) -> str:
        try:
            if system == "linux":
                r = subprocess.run(["cat", "/sys/devices/virtual/dmi/id/board_vendor", "/sys/devices/virtual/dmi/id/board_name"], capture_output=True, text=True)
                parts = r.stdout.strip().split("\n")
                return " ".join(parts) if parts[0] else "unknown"
            elif system == "windows":
                r = subprocess.run(["wmic", "baseboard", "get", "manufacturer,product"], capture_output=True, text=True)
                lines = r.stdout.strip().split("\n")
                return lines[1].strip() if len(lines) > 1 else "unknown"
            return "unknown"
        except:
            return "unknown"

    def _detect_driver(self, hw_type: str) -> str:
        try:
            if hw_type == "cuda":
                import pynvml
                pynvml.nvmlInit()
                ver = pynvml.nvmlSystemGetDriverVersion()
                pynvml.nvmlShutdown()
                return f"CUDA (driver {ver.decode() if isinstance(ver, bytes) else ver})"
            elif hw_type == "rocm":
                result = subprocess.run(["rocm-smi", "--version"], capture_output=True, text=True)
                return f"ROCm {result.stdout.strip()}"
            elif hw_type == "silicon":
                result = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True)
                return f"macOS {result.stdout.strip()}"
            else:
                return f"{platform.system()} {platform.release()}"
        except:
            return "unknown"

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
            gpu_count = 1
            try:
                import torch
                if hasattr(torch, "cuda") and torch.cuda.is_available():
                    gpu_count = torch.cuda.device_count()
                elif hasattr(torch, "hip") and torch.hip.is_available():
                    gpu_count = torch.cuda.device_count()
            except Exception:
                pass

            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True, text=True
            )
            output = result.stdout
            if "MI250X" in output or "MI200" in output:
                vram_per_gpu = 64
                total_vram = vram_per_gpu * max(1, gpu_count)
                return {
                    "type": "rocm",
                    "vram_gb": total_vram,
                    "vram_per_gpu_gb": vram_per_gpu,
                    "gpu_count": max(1, gpu_count),
                    "model": f"{max(1, gpu_count)}x AMD Instinct MI250X" if gpu_count > 1 else "AMD Instinct MI250X (1x GCD)"
                }
            elif "7900XT" in output or "RX 7900" in output:
                return {
                    "type": "rocm",
                    "vram_gb": 20 * max(1, gpu_count),
                    "vram_per_gpu_gb": 20,
                    "gpu_count": max(1, gpu_count),
                    "model": f"{max(1, gpu_count)}x Radeon RX 7900XT" if gpu_count > 1 else "Radeon RX 7900XT"
                }
        except Exception:
            pass
        return {"type": "cpu", "vram_gb": 0, "gpu_count": 0, "model": "CPU"}
