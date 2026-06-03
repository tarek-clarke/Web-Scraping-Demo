#!/bin/bash
#SBATCH --job-name=rap_mi250x
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --gres=gpu:mi250x:1
#SBATCH --time=24:00:00
#SBATCH --output=rap_mi250x_%j.out
#SBATCH --error=rap_mi250x_%j.err
#SBATCH --partition=dev-g

module load LUMI/23.09
module load PyTorch/2.2.0-rocm6.0.2

cd $SLURM_SUBMIT_DIR

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cd go/ingestion && go mod download && cd ../..

python3 run_matrix.py
