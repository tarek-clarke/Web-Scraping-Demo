# Resilient RAP Framework (Semantic Only)

A high-performance semantic drift evaluation and reconciliation framework for robust APIs. The framework simulates high-frequency ingestion streams (up to 100Hz), injects realistic JSON and schema mutations, and benchmarks four distinct structural reconciliation strategies using a native C++ pybind11 acceleration layer.

---

## Performance Evaluation Results (Mean Values)

The framework has been benchmarked on Apple Silicon (MPS backend) using the optimized 216-run matrix under the C++ acceleration layer. Below is the summary of the evaluated mean performance metrics and a comparison of the reconciliation algorithms.

### 1. Unified Performance Metrics (Mean Results)
| Metric | Mean Evaluated Value | Description |
|---|---|---|
| **Drift Detection Rate** | **30.74%** | Percentage of mutated packets correctly flagged as semantic drift |
| **Recovery Score** | **100.00%** | Percentage of detected drift cases successfully reconciled back to canonical schema |
| **P95 Reconciliation Latency** | **139.58 ms** | The 95th percentile latency across all active reconciliation models |
| **Resilience Score (P)** | **0.6412** | Core API resilience score balancing throughput stability and detection rates |
| **Resilience Score (P2)** | **0.6530** | Advanced score integrating recovery rates and normalized P95 latencies |
| **Average Run Ingestion Runtime** | **15.55 s** | Ingestion runtime per 30,000-packet stream under simulated chaos |

### 2. Reconciler Algorithmic Performance Breakdown
| Reconciler Algorithm | Mean Latency | Mean Confidence | Strategy / Integration Details |
|---|---|---|---|
| **Levenshtein (C++ SIMD)** | **0.0011 ms** *(1.1 μs)* | **1.8004** | Bit-parallel Myers' edit distance utilizing hardware compiler auto-vectorization |
| **Regex Matcher (Python)** | **0.0208 ms** *(20.8 μs)* | **0.0041** | Pre-compiled regex patterns to identify common renamed/misplaced fields |
| **BERT Embeddings (Offline)** | **131.53 ms** | **0.6058** | sentence-transformers/all-MiniLM-L6-v2 vector space cosine similarity mapping |
| **Gemma-4 Local LLM** | **8.12 ms** | **0.9314** | Local GGUF/vLLM backend performing generative semantic inference and predictions |

---

## High-Performance C++ Acceleration Architecture

To achieve massive speedups (over **100×** relative to pure Python loops), the framework relies on a hybrid C++/Python architecture:
1. **Myers' Bit-Parallel Levenshtein**: Exposes ultra-fast SIMD-optimized edit distance calculation directly inside `cpp/cpp_accel.cpp`.
2. **Native C++ Packet Ingestion Loop**: Exposes `cpp_accel.run_packet_loop` which performs packet parsing, random chaos selection, and schema structural mutations directly in C++.
3. **GIL Releasing**: The C++ packet loop releases Python's Global Interpreter Lock (`py::gil_scoped_release`), allowing concurrent execution and freeing the CPython runtime. The GIL is only re-acquired briefly when performing deep learning inference calls.
4. **Memory-Buffered Logging**: The logger uses an in-memory batch buffer which flushes to disk in bulk at the end of each stream run. This completely bypasses the catastrophic disk I/O bottleneck of parsing/writing files on every single packet event.

---

## Quickstart

This quickstart covers local and cloud setups. `bootstrap.py` auto-detects the hardware backend (CUDA, ROCm, Apple MPS, or CPU) and installs appropriate PyTorch builds and dependencies. To override detection use the CLI flags `--force-cuda`, `--force-rocm`, `--force-mps`, or `--force-cpu`, or set the `FORCE_HARDWARE` environment variable to `cuda`, `rocm`, `mps`, or `cpu`.

Common steps (Linux/macOS):

```bash
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
python3 -m venv venv
source venv/bin/activate
python3 bootstrap.py --bootstrap
python3 run_all.py
```

Windows PowerShell:

```powershell
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git
Set-Location resilient-rap-framework
py -3 -m venv venv
. .\venv\Scripts\Activate.ps1
py -3 bootstrap.py --bootstrap
py -3 run_all.py
```

Quick smoke tests (faster than running full matrix):

Run a single experiment stream:

```bash
python3 - <<'PY'
from tests.run_experiments import ExperimentRunner
r = ExperimentRunner()
res = r.run_single_stream(
	api_name="finnhub",
	packet_profile="short",
	frequency_profile="100hz",
	chaos_strategy="json",
	chaos_level="low",
	run_number=1,
	concurrency=1
)
print(res)
PY
```

Run a single Gemma inference to verify model load and latency:

```bash
python3 - <<'PY'
from models.gemma_offline import GemmaModel
import time, json
g = GemmaModel()
t0 = time.time()
out = g.predict_semantic_match(["timestamp","value","id"], "ts")
print(json.dumps(out, indent=2))
print("elapsed:", time.time()-t0)
PY
```

Notes:
- For Ubuntu + AMD 7900XT install ROCm before running bootstrap so the script can detect and select ROCm-compatible PyTorch wheels.
- For NVIDIA GPUs install CUDA drivers and ensure `nvidia-smi` is available; `bootstrap.py` will pick an appropriate CUDA wheel.
- On Apple Silicon, MPS is used automatically when available.
- If you want to pin a specific local Gemma checkpoint, set the `GEMMA_LOCAL_PATH` environment variable.

What happens during `--bootstrap`:
- Gemma is downloaded into your local Hugging Face cache (google/gemma-4-E4B) and validated if not already present.
- `sentence-transformers/all-MiniLM-L6-v2` is cached locally.
- The C++ acceleration layer is built in-place.
- Required Python dependencies are installed into the active virtual environment.

### Step-by-Step Setup

Ensure you have Python 3.10+ and a standard C++ compiler (`g++`, `clang++`, or `MSVC`) installed.

```bash
# Create and activate a clean virtual environment
python3 -m venv venv
source venv/bin/activate
```

Run bootstrap to validate the local models and compile the C++ extension:

```bash
python3 bootstrap.py --bootstrap
```

Run the suite:

```bash
python3 run_all.py
```

### Output Directories

- **Drift Logs**: Individual packet mutations are logged in `logs/drift_events.json` and `logs/drift_events.csv`.
- **Execution Metrics**: Detailed metrics per run are stored under `results/<Hardware_Backend>/<Platform>/`.
