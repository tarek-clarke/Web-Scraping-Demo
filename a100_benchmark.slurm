#!/bin/bash
#SBATCH --job-name=rap-triple-header
#SBATCH --partition=gpu
#SBATCH --gres=gpu:A100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=benchmark_output_%j.txt
#SBATCH --error=benchmark_error_%j.txt

echo "🚀 Starting RAP Framework Benchmark on $HOSTNAME"

# 1. Load the updated TalTech modules and our compilers
module load rocky8/all
module load rocky8-spack/master
module load gcc/10.3.0-gcc-8.5.0-abqv
module load gcc/12.4.0-gcc-10.3.0-ujfh

# 2. Activate Micromamba silently
export MAMBA_EXE='/gpfs/mariana/home/tarekc/bin/micromamba'
export MAMBA_ROOT_PREFIX='/gpfs/mariana/home/tarekc/micromamba'
eval "$($MAMBA_EXE shell hook --shell bash)"
micromamba activate rap-env

# 3. Force the A100 Hardware Links
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
export CUDA_VISIBLE_DEVICES=0

# 4. Run the benchmark
cd /gpfs/mariana/home/tarekc/resilient-rap-framework
./tools/run_smart_loop.sh

echo "✅ Benchmark completed."
