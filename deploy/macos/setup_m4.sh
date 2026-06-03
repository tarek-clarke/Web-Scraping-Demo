#!/bin/bash

echo "=== Mac M4 Setup for Resilient RAP Framework ==="

brew install python@3.11 go git

python3.11 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

cd go/ingestion && go mod download && cd ../..

echo "Setup complete. Run: python3 run_matrix.py"
