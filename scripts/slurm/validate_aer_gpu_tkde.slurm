#!/bin/bash
# Minimal execution probe for a ROCm-enabled Qiskit Aer build on LUMI.
# Submit with: sbatch --export=ALL,PROJECT_DIR=/scratch/.../run-dir scripts/slurm/validate_aer_gpu_tkde.slurm
#SBATCH --job-name=rap-aer-gpu-check
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --gpus-per-node=1
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --output=aer_gpu_preflight_%j.out
#SBATCH --error=aer_gpu_preflight_%j.err

set -euo pipefail
: "${PROJECT_DIR:?PROJECT_DIR must point to the staged repository}"

module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10
source /scratch/project_465002996/clarketa/vlq-env/bin/activate

cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR"
python3 -c 'import importlib.util; spec = importlib.util.spec_from_file_location("rap_quantum_router", "src/routing/quantum_router.py"); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.QuantumRouter(backend="aer_gpu")._init_backend(); print("AER_GPU_PREFLIGHT_OK")'
