import os
import sys
import time
import glob
import threading
import subprocess

class GPUPowerProfiler:
    """Scientific GPU Power and Energy consumption profiler.
    
    Supports AMD ROCm (LUMI) via /sys/class/drm/ sysfs paths and
    NVIDIA CUDA via PyNVML/nvidia-smi.
    """
    
    def __init__(self, interval_sec=0.05):
        self.interval_sec = interval_sec
        self.power_samples = []
        self.time_samples = []
        self.running = False
        self._thread = None
        self.sysfs_path = self._detect_rocm_sysfs()
        
    def _detect_rocm_sysfs(self):
        # Search for AMD GPU hwmon power directories (microwatts)
        paths = glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/power1_average")
        if paths:
            # Return the first active path
            return paths[0]
        return None
        
    def _get_gpu_power_watts(self):
        # 1. Try AMD ROCm sysfs (micro-watts -> Watts)
        if self.sysfs_path:
            try:
                with open(self.sysfs_path, "r") as f:
                    val = f.read().strip()
                    return float(val) / 1000000.0
            except Exception:
                pass
                
        # 2. Try nvidia-smi fallback
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL
            )
            return float(out.decode().strip())
        except Exception:
            pass
            
        # 3. Try rocm-smi fallback
        try:
            out = subprocess.check_output(["rocm-smi", "-P"], stderr=subprocess.DEVNULL)
            # Parse power string (e.g. "Average Power: 120 W")
            for line in out.decode().split("\n"):
                if "Power" in line and "W" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        return float(parts[1].replace("W", "").strip())
        except Exception:
            pass
            
        return 0.0

    def _loop(self):
        start_time = time.perf_counter()
        while self.running:
            power = self._get_gpu_power_watts()
            t = time.perf_counter() - start_time
            self.power_samples.append(power)
            self.time_samples.append(t)
            time.sleep(self.interval_sec)

    def start(self):
        """Start the background power profiling thread."""
        self.power_samples = []
        self.time_samples = []
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the profiling thread and compute cumulative metrics."""
        self.running = False
        if self._thread:
            self._thread.join()
            
        return self.compute_metrics()

    def compute_metrics(self):
        """Computes cumulative Energy (Joules) using numerical integration."""
        if not self.power_samples or len(self.power_samples) < 2:
            return {"total_joules": 0.0, "avg_watts": 0.0, "duration_sec": 0.0}
            
        duration = self.time_samples[-1] - self.time_samples[0]
        
        # Trapezoidal rule for E = \int P(t) dt
        joules = 0.0
        for i in range(len(self.power_samples) - 1):
            dt = self.time_samples[i+1] - self.time_samples[i]
            avg_p = (self.power_samples[i+1] + self.power_samples[i]) / 2.0
            joules += avg_p * dt
            
        avg_watts = joules / duration if duration > 0 else 0.0
        
        return {
            "total_joules": round(joules, 2),
            "avg_watts": round(avg_watts, 2),
            "duration_sec": round(duration, 2),
            "samples_count": len(self.power_samples)
        }
