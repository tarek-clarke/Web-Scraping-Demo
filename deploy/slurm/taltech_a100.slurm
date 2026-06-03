#!/bin/bash
#SBATCH --job-name=rap_a100
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:a100:1
#SBATCH --time=24:00:00
#SBATCH --output=rap_a100_%j.out
#SBATCH --error=rap_a100_%j.err

module load python/3.11
module load cuda/12.3
module load go/1.21

cd $SLURM_SUBMIT_DIR

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cd go/ingestion && go mod download && cd ../..

python3 run_matrix.py
