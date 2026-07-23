#!/bin/bash
# Rebuild Aer for AMD MI250X/ROCm and prove execution with a one-circuit probe.
#SBATCH --job-name=rap-aer-rocm-build
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --gpus-per-node=1
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=aer_rocm_build_%j.out
#SBATCH --error=aer_rocm_build_%j.err

set -euo pipefail
: "${PROJECT_DIR:?PROJECT_DIR must point to the staged repository}"

module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.11.7
# Avoid linking Aer against the Cray compiler/libsci runtime.  The previous
# build imported successfully but failed at runtime on __cray_sset_HSW.
module swap PrgEnv-cray PrgEnv-gnu
source /scratch/project_465002996/clarketa/vlq-env/bin/activate

cleanup() {
    python3 -m pip uninstall -y conan >/dev/null 2>&1 || true
    python3 -m pip install "urllib3>=2.2.3,<3" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Conan must exist before we can bootstrap its settings cache.
python3 -m pip install "conan<2"

# Keep Conan's cache local to this benchmark checkout so we do not mutate the
# shared VLQ environment while patching in Clang 18 support for ROCm 6.3.4.
export CONAN_USER_HOME="$PROJECT_DIR/.conan-aer"
mkdir -p "$CONAN_USER_HOME"

# Conan 1.x keeps its cache under $CONAN_USER_HOME/.conan and only creates
# settings.yml when its config cache is initialized.
conan config init --force >/dev/null

python3 - <<'PY'
from pathlib import Path
import os

home = Path(os.environ["CONAN_USER_HOME"]) / ".conan"
settings = home / "settings.yml"

if not settings.exists():
    raise SystemExit("Conan config init did not create settings.yml")

lines = settings.read_text().splitlines()
clang_block = False
version_start = None
version_end = None

for idx, line in enumerate(lines):
    stripped = line.strip()
    if line.startswith("    ") and stripped == "clang:":
        clang_block = True
        continue
    if clang_block and line.startswith("    ") and not line.startswith("        "):
        break
    if clang_block and stripped.startswith("version:"):
        version_start = idx
        if "]" in line:
            version_end = idx
            break
        continue
    if version_start is not None:
        if "]" in line:
            version_end = idx
            break

if version_start is None or version_end is None:
    raise SystemExit("Could not locate the clang version list in Conan settings.yml")

version_slice = "\n".join(lines[version_start:version_end + 1])
if '"18"' not in version_slice and "18" not in version_slice:
    lines[version_end] = lines[version_end].rstrip()
    if lines[version_end].endswith("]"):
        lines[version_end] = lines[version_end][:-1] + ', "18"]'
    else:
        raise SystemExit("Unexpected clang version list formatting in Conan settings.yml")

settings.write_text("\n".join(lines) + "\n")
PY

# CMake's FindBLAS path needs a BLAS/LAPACK name it can probe.  Use the system
# OpenBLAS shared library instead of LUMI's Cray libsci, whose runtime symbols
# are not available to the Python extension at import time.
export BLA_VENDOR=OpenBLAS
export BLAS_SHIM_DIR="$PROJECT_DIR/.conan-aer/blas-shim"
mkdir -p "$BLAS_SHIM_DIR"
for shim in libblas.so libcblas.so liblapack.so; do
    ln -sf /usr/lib64/libopenblas.so.0 "$BLAS_SHIM_DIR/$shim"
done
export LIBRARY_PATH="$BLAS_SHIM_DIR:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="$BLAS_SHIM_DIR:${LD_LIBRARY_PATH:-}"
export CMAKE_LIBRARY_PATH="$BLAS_SHIM_DIR:${CMAKE_LIBRARY_PATH:-}"
export CMAKE_ARGS="${CMAKE_ARGS:-} -DBLAS_LIBRARIES=${BLAS_SHIM_DIR}/libblas.so -DLAPACK_LIBRARIES=${BLAS_SHIM_DIR}/liblapack.so -DBLA_STATIC=OFF"

# The repository-local installer is the project's known ROCm/gfx90a build recipe.
# Remove the CPU wheel first; otherwise its import-only guard skips the build.
python3 -m pip uninstall -y qiskit-aer qiskit-aer-gpu qiskit-aer-gpu-rocm || true
bash "$PROJECT_DIR/scripts/install_qiskit_aer.sh"

cd "$PROJECT_DIR"
python3 -c 'import importlib.util; spec = importlib.util.spec_from_file_location("rap_quantum_router", "src/routing/quantum_router.py"); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.QuantumRouter(backend="aer_gpu")._init_backend(); print("AER_GPU_ROCM_BUILD_AND_PREFLIGHT_OK")'
