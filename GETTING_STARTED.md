# Getting Started with Resilient RAP

Welcome! This guide helps you quickly get up and running with the Resilient RAP Framework for your PhD research.

##  Quick Links

- **[README.md](README.md)** - Project overview and installation
- **[PRODUCTION.md](PRODUCTION.md)** - Production deployment checklist and guidelines
- **[docs/LEARN.md](docs/LEARN.md)** - Deep dive into architecture
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - Common operations
- **[docs/HITL_RETRAINING_GUIDE.md](docs/HITL_RETRAINING_GUIDE.md)** - Human-in-the-loop workflow
- **[LICENSE](LICENSE)** - PolyForm Noncommercial 1.0.0

##  30-Second Start

```bash
# Ubuntu/Debian only (one-time):
# sudo apt update && sudo apt install -y python3-venv

# 1. Install
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 2. Run
PYTHONPATH="." python3 main.py --adapter openf1 --session 9158 --driver 1 --export-audit

# 3. Check audit trail
cat data/audit.json | python3 -m json.tool
```

##  GPU Support (Backend-Agnostic)

The framework automatically detects and uses any available GPU:
- **NVIDIA CUDA** (NVIDIA GPUs)
- **AMD ROCm/HIP** (AMD Radeon GPUs)
- **CPU** (fallback if no GPU available)

### Auto-Detection (Default)
```bash
# Uses GPU if available, CPU otherwise
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.15
```

### Force Specific Backend
```bash
# Force GPU (CUDA/ROCm)
FORCE_DEVICE=gpu PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py

# Force CPU only
FORCE_DEVICE=cpu PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py
```

### Install for Specific Backend

**For NVIDIA CUDA:**
```bash
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**For AMD ROCm (5.7+):**
```bash
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

**For CPU-only (smaller download):**
```bash
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Check GPU Availability
```bash
python3 -c "import torch; print('GPU:', torch.cuda.is_available(), 'Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

##  Common Tasks

### Run a Production Pipeline
```bash
python3 main.py --adapter [openf1|nhl|clinical] [adapter-specific-args] --export-audit
```

### Review Audit Trail
```python
import json
with open('data/audit.json') as f:
    audit = json.load(f)
    print(f"Records processed: {len(audit.get('records', []))}")
```

### Test Everything
```bash
python3 -m pytest tests/ -v
```

### Build Benchmark Report
```bash
PYTHONPATH="." python3 tools/benchmark_semantic_layer.py
```

##  Project Structure

```
resilient-rap-framework/
 README.md              # Start here!
 PRODUCTION.md          # For production deployment
 main.py               # Entry point
 requirements.txt      # Dependencies

 adapters/             # Data connectors (F1, NHL, Clinical)
 modules/              # Core framework code
 src/                  # Utilities and provenance tracking
 tools/                # Production utilities
 examples/             # Demo scripts and notebooks
 tests/                # Test suite

 data/                 # Output: audit logs, reports
 reporting/            # PDF generation
 docs/                 # Detailed documentation
```

##  Running Examples

### Example 1: F1 Telemetry (Formula 1 Data)
```bash
python3 main.py --adapter openf1 --session 9158 --driver 1 --export-audit --audit-path data/f1_audit.json
```

### Example 2: Clinical Streams (Hospital Data)
```bash
python3 main.py --adapter clinical --vendor GE --batch-size 50 --export-audit --audit-path data/clinical_audit.json
```

### Example 3: NHL Play-by-Play
```bash
python3 main.py --adapter nhl --game 2024020001 --export-audit --audit-path data/nhl_audit.json
```

##  Key Concepts

### Schema Drift
The framework automatically detects when data fields change, disappear, or appear.

### Semantic Reconciliation
Uses BERT embeddings to map old field names to new ones intelligently.

### Audit Trails
Every transformation is logged with input/output hashes for reproducibility.

### Reproducibility
Re-run any pipeline with the same parameters to get identical results.

##  Next Steps

1. **Read [README.md](README.md)** - Understand the project vision
2. **Review [PRODUCTION.md](PRODUCTION.md)** - Deployment best practices
3. **Explore [examples/](examples/)** - See working code
4. **Run tests** - `pytest tests/ -v`
5. **Integrate into your research** - Use adapters for your data sources

##  Troubleshooting

**Import errors?**
```bash
python3 -m pip install --upgrade -r requirements.txt
```

**Tests failing?**
```bash
python3 -m pytest tests/ -v --tb=short
```

**Need help?**
- Check [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
- Contact: tclarke91@proton.me

##  For Your Dissertation

This framework provides:
- [x] Reproducible data pipelines
- [x] Automatic audit trails
- [x] Schema evolution handling
- [x] Publication-ready provenance

Use it to demonstrate trustworthy analytics in your research!

---

**License**: PolyForm Noncommercial 1.0.0 (Academic use permitted)  
**Author**: Tarek Clarke  
**Version**: 1.0 (Production)
