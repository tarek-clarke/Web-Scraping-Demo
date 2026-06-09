#!/bin/bash
#SBATCH --job-name=rap-validation
#SBATCH --partition=gpu
#SBATCH --gres=gpu:A100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=12:00:00
#SBATCH --output=validation_%j.out
#SBATCH --error=validation_%j.err

echo "🚀 Starting RAP Framework Validation on $HOSTNAME"

# 1. Load your HPC modules
module load rocky8/all
module load rocky8-spack/master
module load gcc/10.3.0-gcc-8.5.0-abqv
module load gcc/12.4.0-gcc-10.3.0-ujfh
module load cuda/11.8
module load cudnn/8.6

# 2. Activate environment
export MAMBA_EXE='/gpfs/mariana/home/tarekc/bin/micromamba'
export MAMBA_ROOT_PREFIX='/gpfs/mariana/home/tarekc/micromamba'
eval "$($MAMBA_EXE shell hook --shell bash)"
micromamba activate rap-env

# 3. Enter directory and setup dependencies
cd $SLURM_SUBMIT_DIR
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"

echo "📦 Installing Dependencies & PyTorch (CUDA 11.8)..."
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
python3 setup.py build_ext --inplace

# 4. Detect GPU/CPU hardware dynamically
GPU_HARDWARE=$(python3 -c "
import torch
from tools.telemetry_gpu_stress_test import get_gpu_device, gpu_info_dict, _detect_hardware_suffix
device = get_gpu_device()
gpu_info = gpu_info_dict(device)
hw_suffix = _detect_hardware_suffix(gpu_info)
print(hw_suffix)
" 2>/dev/null || echo "unknown")

echo "Detected hardware: $GPU_HARDWARE"

# 5. Run the validation profiles (skip if output already exists)
for i in {1..3}; do
  echo "========== RUN $i =========="
  
  # Profile 1 (Baseline)
  echo "Profile 1: Sprint Baseline"
  if [ ! -f "data/reports/$GPU_HARDWARE/solo/sprint/standard/100hz/telemetry_gpu_stress_test_results_sprint_standard_100hz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --output-suffix _sprint_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  echo "Profile 1: Weekend Baseline"
  if [ ! -f "data/reports/$GPU_HARDWARE/solo/weekend/standard/100hz/telemetry_gpu_stress_test_results_weekend_standard_100hz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --output-suffix _weekend_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  # Profile 2 (Team)
  echo "Profile 2: Team Sprint"
  if [ ! -f "data/reports/$GPU_HARDWARE/team/sprint/standard/100hz/telemetry_gpu_stress_test_results_sprint_standard_100hz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --team --output-suffix _sprint_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  echo "Profile 2: Team Weekend"
  if [ ! -f "data/reports/$GPU_HARDWARE/team/weekend/standard/100hz/telemetry_gpu_stress_test_results_weekend_standard_100hz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --team --output-suffix _weekend_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  # Profile 3 (High-Frequency)
  echo "Profile 3: Sprint 1kHz"
  if [ ! -f "data/reports/$GPU_HARDWARE/solo/sprint/standard/1000hz/telemetry_gpu_stress_test_results_sprint_standard_1000hz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000 --packets 2000 --chaos 0.05 --output-suffix _sprint_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  echo "Profile 3: Sprint 1MHz"
  if [ ! -f "data/reports/$GPU_HARDWARE/solo/sprint/standard/1mhz/telemetry_gpu_stress_test_results_sprint_standard_1mhz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000000 --packets 2000 --chaos 0.05 --output-suffix _sprint_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  echo "Profile 3: Weekend 1kHz"
  if [ ! -f "data/reports/$GPU_HARDWARE/solo/weekend/standard/1000hz/telemetry_gpu_stress_test_results_weekend_standard_1000hz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000 --packets 240000 --chaos 0.05 --output-suffix _weekend_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
  
  echo "Profile 3: Weekend 1MHz"
  if [ ! -f "data/reports/$GPU_HARDWARE/solo/weekend/standard/1mhz/telemetry_gpu_stress_test_results_weekend_standard_1mhz_run${i}_${GPU_HARDWARE}.csv" ]; then
    PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000000 --packets 240000 --chaos 0.05 --output-suffix _weekend_run${i}
  else
    echo "✓ Skip (already exists)"
  fi
done

echo "✅ Validation loop completed."
