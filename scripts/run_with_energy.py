#!/usr/bin/env python3
"""Run one benchmark command with periodic host power/energy sampling."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.telemetry.metrics_logger import EnergyTracker


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--label", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("A command is required after --")
    if args.interval <= 0:
        raise SystemExit("--interval must be positive")

    csv_path = Path(args.csv)
    summary_path = Path(args.summary)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started = time.perf_counter()
    process = None
    tracker = EnergyTracker(str(csv_path))
    telemetry_summary = {}
    failure = None
    return_code = 70

    try:
        tracker.start()
        tracker.log_epoch()
        process = subprocess.Popen(command)
        while process.poll() is None:
            time.sleep(args.interval)
            tracker.log_epoch()
        return_code = int(process.returncode)
        tracker.log_epoch()
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if isinstance(exc, KeyboardInterrupt):
            return_code = 130
    finally:
        try:
            telemetry_summary = tracker.stop()
        except Exception as exc:
            if failure is None:
                failure = f"{type(exc).__name__}: {exc}"
                return_code = 70

    report = {
        "status": "complete" if return_code == 0 and failure is None else "failed",
        "label": args.label,
        "started_at": started_at,
        "completed_at": utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "return_code": return_code,
        "failure": failure,
        "hostname": platform.node(),
        "python": platform.python_version(),
        "command": command,
        "command_sha256": hashlib.sha256("\0".join(command).encode()).hexdigest(),
        "energy_csv": str(csv_path.resolve()),
        "telemetry": telemetry_summary,
        "accelerator_environment": {
            key: os.environ.get(key)
            for key in (
                "CUDA_VISIBLE_DEVICES",
                "ROCR_VISIBLE_DEVICES",
                "HIP_VISIBLE_DEVICES",
                "RAP_ASSIGNED_GPU_ID",
                "SLURM_JOB_ID",
                "SLURM_ARRAY_JOB_ID",
                "SLURM_ARRAY_TASK_ID",
            )
        },
    }
    summary_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if failure:
        print(f"ERROR: workload telemetry failed: {failure}", file=sys.stderr)
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
