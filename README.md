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

## Offline Local Quickstart

Use this when you want the fastest local run with offline Gemma and BERT.
Bootstrap downloads Gemma 4 E4B from `google/gemma-4-E4B` into your local Hugging Face cache automatically, and Gemma auto-detects that cached checkpoint on later runs. Set `GEMMA_LOCAL_PATH` only if you want to pin a specific location.

### macOS / Linux

```bash
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
python3 -m venv venv
source venv/bin/activate
python3 bootstrap.py --bootstrap
python3 run_all.py
```

### Ubuntu / AMD 7900XT

Use this on Ubuntu instances with an AMD Radeon RX 7900 XT GPU and ROCm installed.

```bash
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
python3 -m venv venv
source venv/bin/activate
python3 bootstrap.py --bootstrap
python3 run_all.py
```

If ROCm is already installed, bootstrap will detect the AMD ROCm backend automatically and use the GPU path during model setup.

### Windows PowerShell

```powershell
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git
Set-Location resilient-rap-framework
py -3 -m venv venv
. .\venv\Scripts\Activate.ps1
py -3 bootstrap.py --bootstrap
py -3 run_all.py
```

### Windows Command Prompt

```bat
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
py -3 -m venv venv
venv\Scripts\activate.bat
py -3 bootstrap.py --bootstrap
py -3 run_all.py
```

### Existing Workspace

If you already cloned the repo and have your `.venv`, the quick path is:

```bash
source .venv/bin/activate
python3 bootstrap.py --bootstrap
python3 run_all.py
```

### Cloud VM / SSH Shell

If you are already inside a cloud VM or remote shell, paste this:

```bash
cd /path/to/resilient-rap-framework
source .venv/bin/activate
python3 bootstrap.py --bootstrap
python3 run_all.py
```

### Notebook / Web Terminal

If the environment gives you a notebook cell or browser terminal, use:

```bash
%cd /path/to/resilient-rap-framework
source .venv/bin/activate
python3 bootstrap.py --bootstrap
python3 run_all.py
```

### What Happens

- Gemma loads from your local checkpoint only.
- Bootstrap fetches Gemma 4 E4B from `google/gemma-4-E4B` into the local cache, and Gemma auto-detects the cached checkpoint when `GEMMA_LOCAL_PATH` is unset.
- BERT loads from the local Hugging Face cache only.
- Bootstrap validates local model artifacts and compiles the C++ extension.
- `run_all.py` resumes completed work automatically, so reruns are safe.

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
