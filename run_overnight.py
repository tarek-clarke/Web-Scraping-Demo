"""run_overnight.py — run the pipeline and push results to GitHub.

Stays on the current branch (semantic_only) — no branch switching.
Results are committed to a machine-specific subfolder so two machines
can run simultaneously without conflicts.
"""

import subprocess
import sys
import platform
from datetime import datetime

def run(cmd):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode

# ── Info ──────────────────────────────────────────────────────────────────────
machine = "windows" if platform.system() == "Windows" else "macbook"
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"\n{'='*50}")
print(f"  Machine : {platform.node()} ({platform.system()})")
print(f"  Started : {timestamp}")
print(f"{'='*50}\n")

# ── Run the pipeline ──────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print("  Running pipeline...")
print(f"{'='*50}\n")

exit_code = run(f"{sys.executable} run_all.py --erase-existing")

# ── Commit only result files (small JSON) and push ───────────────────────────
status = "success" if exit_code == 0 else f"exit-code-{exit_code}"
ts = datetime.now().strftime("%Y-%m-%d %H:%M")

print(f"\n{'='*50}")
print(f"  Pipeline finished: {status}")
print("  Committing and pushing results...")
print(f"{'='*50}\n")

run("git add results/")
run(f'git commit -m "results({machine}): overnight run {ts} [{status}]"')
run("git push origin semantic_only")

print(f"\nDone! Results pushed to origin/semantic_only")
print(f"In the morning, pull on the other machine to get combined results:")
print(f"    git pull origin semantic_only")
