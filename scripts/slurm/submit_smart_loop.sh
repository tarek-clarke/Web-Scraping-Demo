#!/bin/bash
#SBATCH --job-name=RAP_L40_Force
#SBATCH --partition=gpu
#SBATCH --gres=gpu:L40:1       
#SBATCH --cpus-per-task=8      
#SBATCH --mem=32G              
#SBATCH --time=02:00:00        
#SBATCH --output=smart_loop_%j.log

# 1. Load GCC 10.3.0
module load gcc/10.3.0
export CC=gcc
export CXX=g++

# 2. Setup Micromamba
export MAMBA_EXE='/gpfs/mariana/home/tarekc/bin/micromamba'
export MAMBA_ROOT_PREFIX='/gpfs/mariana/home/tarekc/micromamba'
eval "$($MAMBA_EXE shell hook --shell bash)"

# 3. Activate Environment
export RAP_ENV="/gpfs/mariana/home/tarekc/.local/share/mamba/envs/rap-env"
micromamba activate $RAP_ENV

# 4. EXTREME FORCE (Bypasses the "No GPU backend detected" warning)
export FORCE_CUDA="1"
export FORCE_CUDA_EXT="1"
export TORCH_CUDA_ARCH_LIST="8.9"
export CUDA_HOME="$RAP_ENV"
export CUDA_PATH="$RAP_ENV"

# 5. Fix the missing crt/host_defines.h (Manual Path Injection)
export CPATH="$RAP_ENV/include:$RAP_ENV/targets/x86_64-linux/include:$CPATH"
export PATH="$RAP_ENV/bin:$PATH"
export LD_LIBRARY_PATH="$RAP_ENV/lib:$RAP_ENV/lib64:$LD_LIBRARY_PATH"

# 6. Clear failed artifacts
rm -rf build/

# 7. Run with explicit environment variables for the sub-process
chmod +x ./tools/run_smart_loop.sh
env FORCE_CUDA=1 TORCH_CUDA_ARCH_LIST="8.9" ./tools/run_smart_loop.sh
