#!/bin/bash
#SBATCH --job-name=vqc-qpu-replay
#SBATCH --account=project_465002996
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:10:00
#SBATCH --output=qpu_replay_%j.out
#SBATCH --error=qpu_replay_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

# Load standard LUMI Python module
module load LUMI/25.09
module load partition/C
module load cray-python/3.10.10

# Activate virtual environment
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Execute QPU shadow replayer
export PYTHONPATH=.
python3 scripts/submit_shadow_qpu.py --log "${1}" --backend "${2:-aer_simulator}"
