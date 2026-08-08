#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
ENV_DIR="${RAP_VLQ_ENV:-.venv-vlq}"
RUN_SMOKE_TEST=1

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap_vlq_env.sh [--python /path/to/python3.11] [--skip-smoke-test]

Bootstraps the local VLQ environment in the repo root:
  - creates .venv-vlq with Python 3.11
  - installs py4lexis
  - installs the QaaS 0.3.2 dependency set, including its Qiskit 1.4 pin
  - writes .env.vlq with the VLQ project/resource IDs
  - optionally runs the VLQ smoke test so lexis_token.txt can be cached
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --python requires a path to Python 3.11" >&2
        exit 1
      fi
      PYTHON_BIN="$2"
      shift 2
      ;;
    --skip-smoke-test)
      RUN_SMOKE_TEST=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python interpreter not found: $PYTHON_BIN" >&2
  echo "Install Python 3.11 or pass --python /path/to/python3.11" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit(
        f"ERROR: QaaS 0.3.2 must use its isolated Python 3.11 environment; "
        f"found {sys.version.split()[0]}"
    )
PY

if [[ -d "$ENV_DIR" ]]; then
  echo "Using existing VLQ environment at $ROOT_DIR/$ENV_DIR"
else
  echo "Creating $ENV_DIR with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv "$ENV_DIR"
fi

# shellcheck disable=SC1091
source "$ENV_DIR/bin/activate"
python - <<'PY'
import sys
if sys.version_info[:2] != (3, 11):
    raise SystemExit(
        f"ERROR: {sys.prefix} is not a Python 3.11 VLQ environment; "
        "remove it or choose a new RAP_VLQ_ENV path"
    )
PY

python -m pip install --upgrade pip setuptools wheel
python -m pip install --index-url https://opencode.it4i.eu/api/v4/projects/107/packages/pypi/simple py4lexis
python -m pip install qaas==v0.3.2
python -m pip check

cat > .env.vlq <<'EOF'
VLQ_PROJECT=EU-26-79
VLQ_RESOURCE=VLQ-EU
EOF

echo "Wrote .env.vlq with the VLQ project and resource identifiers."

if [[ "$RUN_SMOKE_TEST" -eq 1 ]]; then
  echo "Running VLQ smoke test so the OAuth2 token can be cached into lexis_token.txt."
  python scripts/smoke_test_vlq_qpu.py
else
  echo "Skipping smoke test. Run it later with: python scripts/smoke_test_vlq_qpu.py"
fi
