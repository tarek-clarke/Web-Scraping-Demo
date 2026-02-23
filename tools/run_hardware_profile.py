#!/usr/bin/env python3
"""
SRE Hardware Profiling Orchestrator for Cadillac F1 Telemetry Pipeline
------------------------------------------------------------------------
Benchmarks the resilient RAP pipeline on NVMe and HDD drives sequentially.
Compares latency, breaker trips, and generates an SRE profiling report.

Author: Tarek Clarke
Date: February 23, 2026
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================================
# CONFIGURATION (Edit these paths for your environment)
# ============================================================================

NVME_DB_DIR = "/tmp/data_nvme"  # Linux NVMe path
HDD_DB_DIR = "/tmp/data_hdd"   # Linux HDD path
STRESS_TEST_SCRIPT = "tools/cadillac_stress_test.py"
TEMP_REPORTS_DIR = Path("data/reports")
FINAL_REPORTS_DIR = Path("outputs/jsons")
NVME_OUTPUT_CSV = FINAL_REPORTS_DIR / "cadillac_stress_test_results_NVME.csv"
HDD_OUTPUT_CSV = FINAL_REPORTS_DIR / "cadillac_stress_test_results_HDD.csv"
TEMP_OUTPUT_CSV = TEMP_REPORTS_DIR / "cadillac_stress_test_results.csv"
REPORT_MD = FINAL_REPORTS_DIR / "hardware_profiling_report_comparison.md"
CHART_PNG = FINAL_REPORTS_DIR / "hardware_latency_comparison.png"

# ============================================================================
# UTILITIES
# ============================================================================


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_step(step_num, description):
    """Print a step indicator."""
    print(f"\n[STEP {step_num}] {description}")
    print("-" * 80)


def ensure_reports_dir():
    """Ensure output directories exist."""
    TEMP_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Temp reports directory: {TEMP_REPORTS_DIR.absolute()}")
    print(f"✓ Final reports directory: {FINAL_REPORTS_DIR.absolute()}")


def run_stress_test(drive_name, db_dir):
    """Run the stress test with a specific DB directory."""
    print(f"\n>>> Running stress test on {drive_name} drive...")
    print(f"    Database directory: {db_dir}")
    print(f"    This may take 3-5 minutes...")
    
    env = os.environ.copy()
    env["DB_DIR"] = db_dir
    
    try:
        result = subprocess.run(
            [sys.executable, STRESS_TEST_SCRIPT],
            env=env,
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per test
        )
        
        if result.returncode == 0:
            print(f"✓ {drive_name} stress test completed successfully")
            print(f"  Return code: {result.returncode}")
            return True
        else:
            print(f"✗ {drive_name} stress test failed")
            print(f"  Return code: {result.returncode}")
            if result.stdout:
                print(f"  Last stdout: {result.stdout[-1000:]}")
            if result.stderr:
                print(f"  Stderr: {result.stderr[-500:]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ {drive_name} stress test timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"✗ Error running {drive_name} stress test: {e}")
        return False


def copy_and_rename_output(drive_name, target_csv):
    """Copy temp output CSV to drive-specific name."""
    print(f"\n>>> Copying {drive_name} results...")
    
    if not TEMP_OUTPUT_CSV.exists():
        print(f"✗ Temp output CSV not found: {TEMP_OUTPUT_CSV}")
        print(f"  Expected at: {TEMP_OUTPUT_CSV.absolute()}")
        print(f"  Checking {TEMP_REPORTS_DIR}:")
        if TEMP_REPORTS_DIR.exists():
            import os
            for f in os.listdir(TEMP_REPORTS_DIR):
                print(f"    - {f}")
        return False
    
    try:
        shutil.copy(TEMP_OUTPUT_CSV, target_csv)
        print(f"✓ Copied: {TEMP_OUTPUT_CSV.name} → {target_csv.name}")
        print(f"  Size: {target_csv.stat().st_size / 1024:.1f} KB")
        return True
    except Exception as e:
        print(f"✗ Failed to copy output: {e}")
        return False


def load_and_analyze_results():
    """Load both CSVs and compute SRE metrics."""
    print_step(6, "Loading and Analyzing Results")
    
    if not NVME_OUTPUT_CSV.exists() or not HDD_OUTPUT_CSV.exists():
        print(f"✗ Missing output CSVs in {FINAL_REPORTS_DIR}")
        print(f"  NVME: {NVME_OUTPUT_CSV.name} ({'exists' if NVME_OUTPUT_CSV.exists() else 'NOT FOUND'})")
        print(f"  HDD: {HDD_OUTPUT_CSV.name} ({'exists' if HDD_OUTPUT_CSV.exists() else 'NOT FOUND'})")
        return None, None
    
    try:
        print(f"\n>>> Loading NVME results from {NVME_OUTPUT_CSV.name}...")
        nvme_df = pd.read_csv(NVME_OUTPUT_CSV)
        print(f"✓ Loaded {len(nvme_df)} rows from NVME CSV")
        
        print(f"\n>>> Loading HDD results from {HDD_OUTPUT_CSV.name}...")
        hdd_df = pd.read_csv(HDD_OUTPUT_CSV)
        print(f"✓ Loaded {len(hdd_df)} rows from HDD CSV")
        
        return nvme_df, hdd_df
        
    except Exception as e:
        print(f"✗ Failed to load CSVs: {e}")
        return None, None


def compute_sre_metrics(nvme_df, hdd_df):
    """Compute SRE metrics from both DataFrames."""
    print_step(7, "Computing SRE Metrics")
    
    metrics = {}
    
    # NVME metrics
    if "latency_p95_ms" in nvme_df.columns:
        metrics["nvme_latency_avg"] = nvme_df["latency_p95_ms"].mean()
        print(f"✓ NVME avg latency_p95_ms: {metrics['nvme_latency_avg']:.2f} ms")
    
    if "breaker_trips" in nvme_df.columns:
        metrics["nvme_breaker_trips"] = nvme_df["breaker_trips"].sum()
        print(f"✓ NVME total breaker_trips: {metrics['nvme_breaker_trips']}")
    
    # HDD metrics
    if "latency_p95_ms" in hdd_df.columns:
        metrics["hdd_latency_avg"] = hdd_df["latency_p95_ms"].mean()
        print(f"✓ HDD avg latency_p95_ms: {metrics['hdd_latency_avg']:.2f} ms")
    
    if "breaker_trips" in hdd_df.columns:
        metrics["hdd_breaker_trips"] = hdd_df["breaker_trips"].sum()
        print(f"✓ HDD total breaker_trips: {metrics['hdd_breaker_trips']}")
    
    # Calculate improvement (HDD vs NVME)
    if "nvme_latency_avg" in metrics and "hdd_latency_avg" in metrics:
        latency_improvement = (
            (metrics["hdd_latency_avg"] - metrics["nvme_latency_avg"]) 
            / metrics["hdd_latency_avg"] * 100
        )
        metrics["latency_improvement_pct"] = latency_improvement
        print(f"\n✓ Latency Improvement (HDD → NVME): {latency_improvement:.2f}%")
    
    return metrics


def generate_markdown_report(metrics, nvme_df, hdd_df):
    """Generate an SRE-style markdown profiling report."""
    print_step(8, "Generating Markdown Report")
    
    timestamp = datetime.utcnow().isoformat()
    
    report = f"""# Hardware Profiling Report — Cadillac F1 Telemetry Pipeline

**Generated:** {timestamp}  
**Author:** SRE Orchestrator  
**Purpose:** Benchmark resilient-rap pipeline on NVMe vs HDD storage

---

## Executive Summary

This benchmark compares telemetry pipeline performance across two storage tiers:
- **NVMe (Fast)**: {NVME_DB_DIR}
- **HDD (Slow)**: {HDD_DB_DIR}

---

## Key Findings

### Latency Performance (p95 latency in milliseconds)

| Metric | NVME | HDD | Improvement |
|--------|------|-----|-------------|
| Avg Latency (p95 ms) | {metrics.get('nvme_latency_avg', 'N/A'):.2f} ms | {metrics.get('hdd_latency_avg', 'N/A'):.2f} ms | {metrics.get('latency_improvement_pct', 0):.2f}% |
| Total Breaker Trips | {metrics.get('nvme_breaker_trips', 'N/A')} | {metrics.get('hdd_breaker_trips', 'N/A')} | - |

### Interpretation

- **Latency Improvement:** NVMe is **{metrics.get('latency_improvement_pct', 0):.2f}% faster** than HDD for p95 latency.
- **Circuit Breaker Health:** 
  - NVME trips: {metrics.get('nvme_breaker_trips', 'N/A')}
  - HDD trips: {metrics.get('hdd_breaker_trips', 'N/A')}

---

## Detailed Results

### NVMe Drive Statistics
- **Rows processed:** {len(nvme_df)}
- **Mean latency_p95_ms:** {nvme_df['latency_p95_ms'].mean():.2f} ms
- **Median latency_p95_ms:** {nvme_df['latency_p95_ms'].median():.2f} ms
- **Std Dev:** {nvme_df['latency_p95_ms'].std():.2f} ms
- **Min:** {nvme_df['latency_p95_ms'].min():.2f} ms
- **Max:** {nvme_df['latency_p95_ms'].max():.2f} ms

### HDD Drive Statistics
- **Rows processed:** {len(hdd_df)}
- **Mean latency_p95_ms:** {hdd_df['latency_p95_ms'].mean():.2f} ms
- **Median latency_p95_ms:** {hdd_df['latency_p95_ms'].median():.2f} ms
- **Std Dev:** {hdd_df['latency_p95_ms'].std():.2f} ms
- **Min:** {hdd_df['latency_p95_ms'].min():.2f} ms
- **Max:** {hdd_df['latency_p95_ms'].max():.2f} ms

---

## Recommendations

1. **For Production Race-Day Operations:**
   - Use **NVMe drives** for primary telemetry buffering to minimize latency.
   - Reserve HDD for archival and audit log retention.

2. **Cost-Benefit Analysis:**
   - NVMe latency benefit: {metrics.get('latency_improvement_pct', 0):.2f}%
   - Justifies NVMe investment for trackside critical path.

3. **Failover Strategy:**
   - If NVMe fails, HDD can take over with acceptable latency degradation.

---

## Test Parameters

- **Script:** {STRESS_TEST_SCRIPT}
- **NVME Path:** {NVME_DB_DIR}
- **HDD Path:** {HDD_DB_DIR}
- **Timestamp:** {timestamp}

---

*End of Report*
"""
    
    try:
        with open(REPORT_MD, 'w') as f:
            f.write(report)
        print(f"✓ Report written to {REPORT_MD.name}")
        return True
    except Exception as e:
        print(f"✗ Failed to write report: {e}")
        return False


def generate_comparison_chart(nvme_df, hdd_df):
    """Generate a dark-themed side-by-side comparison chart."""
    print_step(9, "Generating Comparison Chart")
    
    # Ensure latency_p95_ms column exists
    if "latency_p95_ms" not in nvme_df.columns or "latency_p95_ms" not in hdd_df.columns:
        print("✗ 'latency_p95_ms' column not found in results")
        return False
    
    try:
        # Set dark theme
        plt.style.use('dark_background')
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('Hardware Latency Comparison: NVMe vs HDD', fontsize=16, fontweight='bold')
        
        # NVME chart
        nvme_session_idx = range(len(nvme_df))
        ax1.bar(nvme_session_idx, nvme_df["latency_p95_ms"], color='#00ff41', alpha=0.7, label='NVMe')
        ax1.set_xlabel('Session #', fontsize=11)
        ax1.set_ylabel('Latency p95 (ms)', fontsize=11)
        ax1.set_title('NVMe Drive Performance', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.2)
        ax1.set_ylim(0, max(max(nvme_df["latency_p95_ms"]), max(hdd_df["latency_p95_ms"])) * 1.1)
        
        # HDD chart
        hdd_session_idx = range(len(hdd_df))
        ax2.bar(hdd_session_idx, hdd_df["latency_p95_ms"], color='#ff6b6b', alpha=0.7, label='HDD')
        ax2.set_xlabel('Session #', fontsize=11)
        ax2.set_ylabel('Latency p95 (ms)', fontsize=11)
        ax2.set_title('HDD Drive Performance', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.2)
        ax2.set_ylim(0, max(max(nvme_df["latency_p95_ms"]), max(hdd_df["latency_p95_ms"])) * 1.1)
        
        plt.tight_layout()
        plt.savefig(CHART_PNG, dpi=300, bbox_inches='tight')
        print(f"✓ Chart saved to {CHART_PNG.name}")
        plt.close()
        return True
        
    except Exception as e:
        print(f"✗ Failed to generate chart: {e}")
        return False


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================


def main():
    """Main orchestration workflow."""
    print_header("SRE HARDWARE PROFILING ORCHESTRATOR — CADILLAC F1 TELEMETRY PIPELINE")
    
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Working Directory: {Path.cwd()}")
    
    # Step 1: Prepare environment
    print_step(1, "Preparing Environment")
    ensure_reports_dir()
    
    # Step 2: Run NVMe test
    print_step(2, "Running NVMe Stress Test (Sequential)")
    if not run_stress_test("NVMe", NVME_DB_DIR):
        print("✗ NVMe test failed. Aborting.")
        return False
    
    # Step 3: Copy NVMe results
    print_step(3, "Archiving NVMe Results")
    if not copy_and_rename_output("NVMe", NVME_OUTPUT_CSV):
        print("✗ Failed to archive NVMe results. Aborting.")
        return False
    
    # Step 4: Run HDD test
    print_step(4, "Running HDD Stress Test (Sequential)")
    if not run_stress_test("HDD", HDD_DB_DIR):
        print("✗ HDD test failed. Aborting.")
        return False
    
    # Step 5: Copy HDD results
    print_step(5, "Archiving HDD Results")
    if not copy_and_rename_output("HDD", HDD_OUTPUT_CSV):
        print("✗ Failed to archive HDD results. Aborting.")
        return False
    
    # Step 6: Load and analyze
    nvme_df, hdd_df = load_and_analyze_results()
    if nvme_df is None or hdd_df is None:
        print("✗ Failed to load results. Aborting.")
        return False
    
    # Step 7: Compute metrics
    metrics = compute_sre_metrics(nvme_df, hdd_df)
    
    # Step 8: Generate markdown report
    if not generate_markdown_report(metrics, nvme_df, hdd_df):
        print("✗ Failed to generate report.")
        return False
    
    # Step 9: Generate chart
    if not generate_comparison_chart(nvme_df, hdd_df):
        print("✗ Failed to generate chart.")
        return False
    
    # Final summary
    print_header("ORCHESTRATION COMPLETE ✓")
    print(f"Outputs Generated:")
    print(f"  - {NVME_OUTPUT_CSV.name}")
    print(f"  - {HDD_OUTPUT_CSV.name}")
    print(f"  - {REPORT_MD.name}")
    print(f"  - {CHART_PNG.name}")
    print(f"\nRecommendation: NVMe is {metrics.get('latency_improvement_pct', 0):.2f}% faster than HDD.")
    print("\n✓ All benchmarks complete. Ready for presentation.\n")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
