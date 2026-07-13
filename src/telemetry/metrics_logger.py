import os
import sys
import time
import csv
import logging
from typing import Optional

# Setup lightweight logger
logging.basicConfig(level=logging.INFO, format="[EnergyTracker] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("EnergyTracker")

# Try to import CodeCarbon (localized carbon intensity tracking)
try:
    from codecarbon import EmissionsTracker
    HAS_CODECARBON = True
except ImportError:
    HAS_CODECARBON = False
    logger.warning("CodeCarbon not installed. Carbon tracking will use offline estimations.")

# Try to import pynvml (NVIDIA Management Library)
try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

class EnergyTracker:
    """
    Unified, hardware-agnostic energy and carbon tracker for containerized HPC runs.
    Automatically detects NVIDIA GPUs (via NVML), AMD GPUs (via sysfs/rocm-smi),
    and falls back to CPU telemetry (RAPL/sysfs) if no accelerator is discovered.
    """
    def __init__(self, output_path: str = "/workspace/metrics/energy_profile.csv"):
        self.output_path = output_path
        self.hardware_type = "CPU"
        self.gpu_device_id = 0
        self.nvml_handle = None
        self._cc_tracker = None
        self._start_time = 0.0
        self._start_energy_kwh = 0.0
        
        # Detected AMD file paths (sysfs interfaces)
        self.amd_power_file: Optional[str] = None
        self.amd_temp_file: Optional[str] = None

        # Grid intensity default: 300 gCO2/kWh (European average)
        self.grid_intensity_g = 300.0

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if exc_type:
            logger.error(f"Execution completed with error: {exc_val}")
        return False  # Do not suppress exceptions

    def start(self):
        """Detect hardware, initialize tracking libraries and files."""
        self._start_time = time.perf_counter()
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        # Initialize output CSV structure if it doesn't exist
        if not os.path.exists(self.output_path):
            with open(self.output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "elapsed_seconds", "hardware_tier", 
                    "power_draw_w", "temperature_c", "cumulative_kwh", "estimated_gCO2e"
                ])

        # 1. Detect NVIDIA GPU
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    self.hardware_type = "NVIDIA"
                    self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_device_id)
                    name = pynvml.nvmlDeviceGetName(self.nvml_handle)
                    logger.info(f"Detected NVIDIA GPU: {name} via NVML.")
            except Exception as e:
                logger.debug(f"NVIDIA check failed or library uninitialized: {e}")

        # 2. Detect AMD GPU (Sysfs fallback for unprivileged containers)
        if self.hardware_type == "CPU":
            # Search common sysfs device targets for ROCm Instinct cards
            for card_idx in range(4):
                base_path = f"/sys/class/drm/card{card_idx}/device"
                hwmon_path = f"{base_path}/hwmon"
                if os.path.exists(base_path):
                    # Check for power and temperature attributes
                    power_check = f"{base_path}/hwmon/hwmon0/power1_average"
                    temp_check = f"{base_path}/hwmon/hwmon0/temp1_input"
                    # Handle varying subfolders
                    if os.path.exists(hwmon_path):
                        for sub in os.listdir(hwmon_path):
                            p_path = f"{hwmon_path}/{sub}/power1_average"
                            t_path = f"{hwmon_path}/{sub}/temp1_input"
                            if os.path.exists(p_path):
                                self.amd_power_file = p_path
                                self.amd_temp_file = t_path if os.path.exists(t_path) else None
                                self.hardware_type = "AMD"
                                logger.info(f"Detected AMD GPU via sysfs: {p_path}")
                                break
                if self.hardware_type == "AMD":
                    break

        if self.hardware_type == "CPU":
            logger.info("No accelerators detected. Operating in CPU telemetry fallback.")

        # 3. Launch CodeCarbon Tracker if available
        if HAS_CODECARBON:
            try:
                self._cc_tracker = EmissionsTracker(
                    output_dir=os.path.dirname(self.output_path),
                    save_to_file=False,
                    log_level="warning"
                )
                self._cc_tracker.start()
            except Exception as e:
                logger.warning(f"Could not start CodeCarbon: {e}. Falling back to inline carbon estimation.")

    def get_metrics(self) -> dict:
        """Query native hardware interfaces for power and temp measurements."""
        power_w = 0.0
        temp_c = 0.0

        try:
            if self.hardware_type == "NVIDIA" and self.nvml_handle:
                # NVML returns milliwatts, convert to Watts
                power_w = pynvml.nvmlDeviceGetPowerManagementLimit(self.nvml_handle) / 1000.0
                try:
                    power_w = pynvml.nvmlDeviceGetPowerUsage(self.nvml_handle) / 1000.0
                except Exception:
                    pass
                temp_c = pynvml.nvmlDeviceGetTemperature(self.nvml_handle, pynvml.NVML_TEMPERATURE_GPU)

            elif self.hardware_type == "AMD" and self.amd_power_file:
                # Sysfs outputs microwatts or milliwatts. Most AMD drivers output microwatts.
                with open(self.amd_power_file, "r") as f:
                    raw_val = float(f.read().strip())
                    power_w = raw_val / 1000000.0 if raw_val > 10000 else raw_val / 1000.0
                
                if self.amd_temp_file:
                    with open(self.amd_temp_file, "r") as f:
                        temp_c = float(f.read().strip()) / 1000.0  # millidegrees C

            else:  # CPU Telemetry RAPL fallback
                rapl_power_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
                if os.path.exists(rapl_power_path):
                    with open(rapl_power_path, "r") as f:
                        e1 = float(f.read().strip())
                    time.sleep(0.1)
                    with open(rapl_power_path, "r") as f:
                        e2 = float(f.read().strip())
                    power_w = ((e2 - e1) / 1000000.0) / 0.1  # dJoules / dt = Watts
                else:
                    # Generic CPU default estimation
                    power_w = 95.0  # Default TDP assumption
                temp_c = 45.0
        except Exception as e:
            logger.warning(f"Telemetry read failure (degrading gracefully): {e}")

        # Compute elapsed time
        elapsed = time.perf_counter() - self._start_time
        
        # Calculate cumulative kWh
        kwh = (power_w * (elapsed / 3600.0)) / 1000.0
        
        # Estimate emissions (gCO2e)
        if HAS_CODECARBON and self._cc_tracker:
            try:
                # Extract runtime emission estimations from CodeCarbon if possible
                emissions_g = self._cc_tracker._total_emissions * 1000.0
            except Exception:
                emissions_g = kwh * self.grid_intensity_g
        else:
            emissions_g = kwh * self.grid_intensity_g

        return {
            "elapsed_seconds": round(elapsed, 2),
            "hardware_tier": self.hardware_type,
            "power_draw_w": round(power_w, 2),
            "temperature_c": round(temp_c, 1),
            "cumulative_kwh": round(kwh, 6),
            "estimated_gCO2e": round(emissions_g, 4)
        }

    def log_epoch(self):
        """Sample current power and flush record to profile file."""
        metrics = self.get_metrics()
        try:
            with open(self.output_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    metrics["elapsed_seconds"],
                    metrics["hardware_tier"],
                    metrics["power_draw_w"],
                    metrics["temperature_c"],
                    metrics["cumulative_kwh"],
                    metrics["estimated_gCO2e"]
                ])
        except Exception as e:
            logger.error(f"Failed to write to energy CSV: {e}")

    def stop(self):
        """Clean teardown of measurement drivers and wrappers."""
        if HAS_CODECARBON and self._cc_tracker:
            try:
                self._cc_tracker.stop()
            except Exception:
                pass
        if HAS_PYNVML and self.hardware_type == "NVIDIA":
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
        logger.info("Energy tracking telemetry shutdown complete.")

# --- Context Manager Integration Hook Example ---
if __name__ == "__main__":
    print("Testing energy logger context wrapper...")
    with EnergyTracker(output_path="./metrics/test_profile.csv") as tracker:
        for epoch in range(1, 11):
            time.sleep(0.5)
            tracker.log_epoch()
            print(f"Processed Epoch {epoch}/10...")
    print("Test profile output written to ./metrics/test_profile.csv")
