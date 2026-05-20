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

## Quickstart Instructions for New Platforms

Follow these instructions when logging into a new platform (e.g. Vast.ai, RunPod, Lambda Labs, or a local server) to automatically detect hardware, compile dependencies, and run evaluation matrix sweeps.

### One-Command Quickstart
Copy and paste this single command to clone, initialize, and execute the entire suite in one go:

```bash
git clone -b semantic_only https://github.com/tarek-clarke/resilient-rap-framework.git && cd resilient-rap-framework && python3 -m venv venv && source venv/bin/activate && python3 bootstrap.py --bootstrap && python3 run_all.py
```

### Step-by-Step Instructions

### 1. Repository Setup & Virtual Environment
Ensure you have Python 3.10+ and a standard C++ compiler (`g++`, `clang++`, or `MSVC`) installed.

```bash
# Clone the repository and navigate to it
cd resilient-rap-framework

# Create and activate a clean virtual environment
python -o -m venv venv
source venv/bin/activate
```

### 2. Auto-Bootstrap Phase (First Launch)
The system is equipped with a cloud-optimized automated bootstrap script (`bootstrap.py`). 

Run the bootstrap to auto-detect hardware and compile the C++ extension in-place:
```bash
python bootstrap.py --bootstrap
```

#### What Bootstrap Automatically Accomplishes:
* **Cloud Detection**: Auto-detects the host platform (Vast.ai, RunPod, Lambda Labs, Spheron, Lumi, or Local).
* **Hardware Backend Mapping**: Queries and configures the optimized acceleration API:
  - **NVIDIA GPU**: CUDA backend setup
  - **AMD GPU**: ROCm backend setup
  - **Intel GPU**: Intel GPU execution mapping
  - **Apple Silicon**: Apple Silicon MPS backend mapping
  - **CPU**: Clean CPU-only fallback
* **Intelligent PyTorch Wheels**: Installs the precise pre-compiled PyTorch wheel match to avoid compiling PyTorch or ROCm/CUDA components from source.
* **C++ Module Compilation**: Compiles the native C++ pybind11 extension (`cpp_accel.so`) in-place via:
  ```bash
  python setup.py build_ext --inplace
  ```
* **Weights Pre-Caching**: Configures SentenceTransformers (`all-MiniLM-L6-v2`) in `local_files_only=True` mode, preventing network latency and timeouts on offline servers.

### 3. Running the Evaluation Suite
To execute the optimized 216-run execution matrix, run:
```bash
python run_all.py
```

* **Stunning Visual Estimates Chart**: On startup, the pipeline runner displays hardware metadata alongside a side-by-side projected completion chart (comparing C++ accelerated speeds to raw Python speeds).
* **Self-Healing Run Resumption**: The pipeline is fully incremental; if it is interrupted, running `python run_all.py` again will automatically detect completed runs and skip them.
* **Summary Metrics**: At the conclusion of the suite, the pipeline calculates unified execution times and dumps structured results to `summary.json` within your specific hardware directory.

### 4. Output Directories
* **Drift Logs**: All individual packet mutations are logged directly in `logs/drift_events.json` and `logs/drift_events.csv`.
* **Execution Metrics**: Detailed metrics per run are stored under `results/<Hardware_Backend>/<Platform>/`.
