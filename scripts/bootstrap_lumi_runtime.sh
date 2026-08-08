#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings

LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
TARGET="$PROJECT_ROOT/.runtime/lumi/site-packages"
mkdir -p "$TARGET"

# Keep the vendor ROCm stack immutable. Only packages absent from the
# container are installed into the scratch-resident import layer.
singularity run "$LUMI_SIF" python -m pip install \
    --upgrade --target "$TARGET" \
    "python-Levenshtein>=0.23.0,<1.0.0"

PYTHONPATH="$TARGET${PYTHONPATH:+:$PYTHONPATH}" \
SINGULARITYENV_PYTHONPATH="$TARGET${PYTHONPATH:+:$PYTHONPATH}" \
singularity run "$LUMI_SIF" python - <<'PY'
import Levenshtein
print("LUMI scratch dependency layer ready:", Levenshtein.__version__)
PY
