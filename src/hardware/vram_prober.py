import psutil
from typing import Dict

class VRAMProber:
    def __init__(self, hardware_type: str):
        self.hardware_type = hardware_type
    
    def _calculate_batch_size(self, free_gb: float) -> int:
        if free_gb >= 200:
            return 64
        elif free_gb >= 80:
            return 32
        elif free_gb >= 32:
            return 16
        elif free_gb >= 16:
            return 8
        else:
            return 4

    def probe(self) -> Dict:
        if self.hardware_type == "cuda":
            return self._probe_cuda()
        elif self.hardware_type == "rocm":
            return self._probe_rocm()
        elif self.hardware_type == "silicon":
            return self._probe_silicon()
        else:
            return self._probe_cpu()

    def _probe_cuda(self) -> Dict:
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            free_gb = mem_info.free / (1024**3)
            total_gb = mem_info.total / (1024**3)
            pynvml.nvmlShutdown()
            
            concurrent_runs = max(1, int(free_gb / 8))
            batch_size = self._calculate_batch_size(free_gb)
            
            return {
                "free_gb": free_gb,
                "total_gb": total_gb,
                "concurrent_runs": concurrent_runs,
                "batch_size": batch_size
            }
        except:
            return {"free_gb": 0, "total_gb": 0, "concurrent_runs": 1, "batch_size": 1}

    def _probe_rocm(self) -> Dict:
        try:
            import subprocess
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.split('\n')
            free_gb = 0
            total_gb = 0
            for line in lines:
                if "VRAM" in line and "Total" in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if "MB" in p:
                            total_gb = int(parts[i-1]) / 1024
                if "VRAM" in line and "Free" in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if "MB" in p:
                            free_gb = int(parts[i-1]) / 1024
                if "Used Memory" in line:
                    parts = line.split()
                    used_mb = int(parts[-2])
                    total_mb = int(parts[-1].rstrip(')'))
                    free_gb = (total_mb - used_mb) / 1024
                    total_gb = total_mb / 1024
            if free_gb > 0 and total_gb > 0:
                concurrent_runs = max(1, int(free_gb / 8))
                batch_size = self._calculate_batch_size(free_gb)
                return {
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "concurrent_runs": concurrent_runs,
                    "batch_size": batch_size
                }
        except:
            pass

        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                total_gb = props.total_memory / (1024**3)
                free_gb = total_gb * 0.85
                concurrent_runs = max(1, int(free_gb / 8))
                batch_size = self._calculate_batch_size(free_gb)
                return {
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "concurrent_runs": concurrent_runs,
                    "batch_size": batch_size
                }
        except:
            pass

        mem = psutil.virtual_memory()
        free_gb = mem.available / (1024**3)
        total_gb = mem.total / (1024**3)
        concurrent_runs = max(1, int(free_gb / 2))
        batch_size = self._calculate_batch_size(free_gb)
        return {
            "free_gb": free_gb,
            "total_gb": total_gb,
            "concurrent_runs": concurrent_runs,
            "batch_size": batch_size
        }

    def _probe_silicon(self) -> Dict:
        mem = psutil.virtual_memory()
        free_gb = mem.available / (1024**3)
        total_gb = mem.total / (1024**3)
        concurrent_runs = max(1, int(free_gb / 4))
        batch_size = self._calculate_batch_size(free_gb)
        return {
            "free_gb": free_gb,
            "total_gb": total_gb,
            "concurrent_runs": concurrent_runs,
            "batch_size": batch_size
        }

    def _probe_cpu(self) -> Dict:
        mem = psutil.virtual_memory()
        free_gb = mem.available / (1024**3)
        total_gb = mem.total / (1024**3)
        concurrent_runs = max(1, int(free_gb / 2))
        batch_size = self._calculate_batch_size(free_gb)
        return {
            "free_gb": free_gb,
            "total_gb": total_gb,
            "concurrent_runs": concurrent_runs,
            "batch_size": batch_size
        }
