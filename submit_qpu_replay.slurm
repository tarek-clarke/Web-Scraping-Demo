#!/bin/bash
#SBATCH --job-name=qpu-shadow-replay
#SBATCH --account=project_465002996
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=qpu_replay_%j.out
#SBATCH --error=qpu_replay_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Running Offline QPU Shadow Replay on Compute Node ==="
echo "Node: $SLURM_NODENAME"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load cray-python/3.10.10

# Activate venv
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Use Qiskit IBM Cloud credentials saved in ~/.qiskit/qiskit-ibm.json
export PYTHONPATH="$PROJECT_ROOT"

# Run the replayer script on the full 119-packet shadow log
python3 -u scripts/submit_shadow_qpu.py --log data/reports/live_f1/shadow_log_20260703_192536.json --backend ibm_quantum

echo "=== QPU Replay Job Complete ==="
echo "End time: $(date)"
