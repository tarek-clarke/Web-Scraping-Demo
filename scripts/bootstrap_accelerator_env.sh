#!/bin/bash
set -euo pipefail

PYTHON_BIN="${RAP_BOOTSTRAP_PYTHON:-python3}"
ENV_DIR="${RAP_ENV_DIR:-.venv-accelerator}"

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11) or sys.version_info >= (3, 14):
    raise SystemExit(f"ERROR: Python 3.11-3.13 is required; found {sys.version.split()[0]}")
try:
    import torch
except ImportError as exc:
    raise SystemExit(
        "ERROR: start inside a vendor GPU PyTorch environment first "
        "(LUMI multitorch or NVIDIA NGC PyTorch); torch is intentionally not guessed"
    ) from exc
if not torch.cuda.is_available():
    raise SystemExit("ERROR: the vendor PyTorch build cannot see a GPU")
print("Vendor torch:", torch.__version__)
print("Runtime:", "ROCm " + str(torch.version.hip) if torch.version.hip else "CUDA " + str(torch.version.cuda))
print("Devices:", [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
PY

"$PYTHON_BIN" -m venv --system-site-packages "$ENV_DIR"
VENV_PYTHON="$ENV_DIR/bin/python"
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import torch
raise SystemExit(0 if torch.version.hip else 1)
PY
then
    "$VENV_PYTHON" -m pip install -r requirements-lumi.txt
else
    "$VENV_PYTHON" -m pip install -r requirements-nvidia.txt
fi

RAP_PYTHON_BIN="$VENV_PYTHON" bash scripts/install_qiskit_aer.sh
"$VENV_PYTHON" -m pip check
DEVICE_COUNT="$($VENV_PYTHON -c 'import torch; print(torch.cuda.device_count())')"
PREFLIGHT_ARGS=(--expected-devices "$DEVICE_COUNT" --require-aer --require-router-qnn)
PREFLIGHT_ARGS+=(--require-power-telemetry)
if [ -n "${COHERE_API_KEY:-}" ]; then
    PREFLIGHT_ARGS+=(--require-cohere)
fi
"$VENV_PYTHON" scripts/preflight_accelerator.py "${PREFLIGHT_ARGS[@]}" \
    --profile full \
    --json-output data/training/preflight_environment.json

echo "Environment ready: $ENV_DIR"
echo "Activate with: source $ENV_DIR/bin/activate"
