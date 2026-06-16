#!/bin/bash
#SBATCH --job-name=quantum-routing
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=14
#SBATCH --mem=120G
#SBATCH --time=03:00:00
#SBATCH --output=job_%j.out
#SBATCH --error=job_%j.err

echo "=== Quantum Routing Benchmark Started ==="
echo "Node: $SLURM_NODENAME"
echo "Allocated GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source .venv-lumi/bin/activate

# Install base quantum dependencies
pip install -r requirements-quantum.txt --quiet 2>/dev/null || true

# Dynamically build/install qiskit-aer based on GPU environment (ROCm/CUDA/CPU)
./install_qiskit_aer.sh

# Environment variables
export HF_TOKEN=${HF_TOKEN}
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:1

# Check GPUs
rocm-smi

# Step 1: Train quantum router on existing MI250X benchmark data
echo ""
echo "=== Step 1: Training Quantum Router ==="
python3 -m src.routing.training --data data/reports/MI250X/ --output configs/trained_router_params.json

# Step 2: Run full benchmark matrix with quantum phase
echo ""
echo "=== Step 2: Running Quantum-Routed Benchmark ==="
python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --repetitions 1 --phases quantum

echo ""
echo "=== Quantum Routing Benchmark Finished ==="
echo "End time: $(date)"
