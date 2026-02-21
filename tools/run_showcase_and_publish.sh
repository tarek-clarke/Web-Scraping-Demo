#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

PYTHONPATH="." python tools/demo_openf1.py --session 9158 --driver 1
PYTHONPATH="." python tools/demo_nhl.py --game 2024020001
PYTHONPATH="." python main.py --adapter clinical --export-audit --audit-path data/clinical_audit.json
PYTHONPATH="." python tools/stress_test_engine_temp.py
PYTHONPATH="." python tools/demo_hitl_retraining.py
PYTHONPATH="." python tools/benchmark_semantic_layer.py
PYTHONPATH="." python tools/demo_pdf_report.py

# Stage generated outputs (reports/findings + CSVs)
while IFS= read -r -d '' file; do
  git add -f "$file"
done < <(
  find data -type f \( \
    -name "*.csv" -o \
    -name "*.pdf" -o \
    -name "*_report*.json" -o \
    -name "*_audit.json" \
  \) -print0
)

if ! git diff --cached --quiet; then
  git commit -m "chore: publish showcase reports"
  git push
else
  echo "No report artifacts to publish."
fi
