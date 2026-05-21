"""run_overnight.py — run the pipeline and push results to a machine-specific branch.

Usage:
    python run_overnight.py

Each machine automatically pushes to its own branch (results/windows or
results/macbook), so two machines can run simultaneously without conflicts.
"""

import subprocess
import sys
import os
import socket
import platform
from datetime import datetime

# ── Detect which machine this is ──────────────────────────────────────────────
def get_branch_name():
    system = platform.system()
    if system == "Windows":
        return "results/windows"
    elif system == "Darwin":
        return "results/macbook"
    else:
        hostname = socket.gethostname().split(".")[0].lower()
        return f"results/{hostname}"

def run(cmd, **kwargs):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, **kwargs)
    return result.returncode

# ── Setup branch ──────────────────────────────────────────────────────────────
branch = get_branch_name()
print(f"\n{'='*50}")
print(f"  Machine : {platform.node()} ({platform.system()})")
print(f"  Branch  : {branch}")
print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*50}\n")

# Create or switch to the machine-specific results branch
run(f"git fetch origin")
# Try to track remote branch, fall back to creating from current HEAD
code = run(f"git checkout {branch}")
if code != 0:
    # Branch doesn't exist yet — create it
    run(f"git checkout -b {branch}")
    # Try to push the new branch to remote
    run(f"git push -u origin {branch}")
else:
    run(f"git pull origin {branch}")

# ── Run the pipeline ──────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print("  Running pipeline...")
print(f"{'='*50}\n")

exit_code = run(f"{sys.executable} run_all.py --erase-existing")

# ── Commit and push results ───────────────────────────────────────────────────
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
status = "success" if exit_code == 0 else f"exit-code-{exit_code}"

print(f"\n{'='*50}")
print(f"  Pipeline finished: {status}")
print("  Committing and pushing results...")
print(f"{'='*50}\n")

run("git add results/ logs/ summary.json")
run(f'git commit -m "results({platform.system().lower()}): overnight run {timestamp} [{status}]"')
run(f"git push origin {branch}")

print(f"\nDone! Results pushed to branch: {branch}")
print(f"In the morning, merge both with:")
print(f"    git checkout semantic_only")
print(f"    git merge results/windows")
print(f"    git merge results/macbook")
print(f"    git push origin semantic_only")
