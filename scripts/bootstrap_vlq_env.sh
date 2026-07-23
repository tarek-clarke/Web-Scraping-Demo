#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
RUN_SMOKE_TEST=1

usage() {
  cat <<'EOF'
Usage: scripts/bootstrap_vlq_env.sh [--python /path/to/python3.12] [--skip-smoke-test]

Bootstraps the local VLQ environment in the repo root:
  - creates .venv with Python 3.12
  - installs py4lexis
  - installs qaas==v0.3.2 with --ignore-requires-python
  - writes .env.vlq with the VLQ project/resource IDs
  - optionally runs the VLQ smoke test so lexis_token.txt can be cached
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --python requires a path to Python 3.12" >&2
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
  echo "Install Python 3.12 or pass --python /path/to/python3.12" >&2
  exit 1
fi

if [[ -d .venv ]]; then
  echo "Using existing .venv at $ROOT_DIR/.venv"
else
  echo "Creating .venv with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install --index-url https://opencode.it4i.eu/api/v4/projects/107/packages/pypi/simple py4lexis
python -m pip install --ignore-requires-python qaas==v0.3.2

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
