#!/usr/bin/env bash
# =============================================================================
# Cadillac F1 — Full Showcase Runner
# =============================================================================
# One-click execution of every subsystem in the telemetry spine.
# Designed for live demos to the Cadillac F1 engineering team.
#
# Usage:
#   chmod +x tools/run_cadillac_showcase.sh
#   ./tools/run_cadillac_showcase.sh
#
# What it runs (in order):
#   1. Unit tests       — 31 tests covering every new module
#   2. Stress test      — Triple-Header (showcase mode)
#   3. Health monitor   — 15-second live pit wall dashboard
#   4. Original demos   — OpenF1, NHL, Clinical, Semantic, PDF
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="."

# Activate venv if present
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

divider() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${BOLD}  $1${RESET}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo ""
}

header() {
  clear
  echo ""
  echo -e "${RED}${BOLD}"
  echo "     ╔═══════════════════════════════════════════════════════════╗"
  echo "     ║           CADILLAC F1 — TELEMETRY SPINE SHOWCASE         ║"
  echo "     ║       The Defensive D · Research-to-Production Spine     ║"
  echo "     ╚═══════════════════════════════════════════════════════════╝"
  echo -e "${RESET}"
  echo ""
}

passed=0
failed=0
total=0

run_stage() {
  local label="$1"
  shift
  total=$((total + 1))
  divider "STAGE ${total}: ${label}"
  if "$@"; then
    passed=$((passed + 1))
    echo -e "\n${GREEN}✓ ${label} — PASSED${RESET}\n"
  else
    failed=$((failed + 1))
    echo -e "\n${RED}✗ ${label} — FAILED (non-fatal, continuing)${RESET}\n"
  fi
}

# ===========================================================================
header

# --- Stage 1: Unit Tests ---
run_stage "Cadillac Module Tests (31 tests)" \
  python3 -m pytest tests/test_cadillac_modules.py -v --tb=short

# --- Stage 2: Triple-Header Stress Test (showcase mode) ---
run_stage "Triple-Header Stress Test (Showcase)" \
  python3 tools/cadillac_stress_test.py --showcase

# --- Stage 3: Pit Wall Health Monitor (15s demo) ---
run_stage "Pit Wall Health Monitor (15s live demo)" \
  python3 tools/health_monitor.py --duration 15

# --- Stage 4: OpenF1 Telemetry Demo ---
run_stage "OpenF1 API Telemetry" \
  python3 tools/demo_openf1.py --session 9158 --driver 1

# --- Stage 5: Engine Temperature Stress ---
run_stage "Engine Temperature Stress Test" \
  python3 tools/stress_test_engine_temp.py

# --- Stage 6: Semantic Layer Benchmark ---
run_stage "Semantic Layer Benchmark" \
  python3 tools/benchmark_semantic_layer.py

# --- Stage 7: PDF Audit Report ---
run_stage "PDF Audit Report" \
  python3 tools/demo_pdf_report.py

# ===========================================================================
divider "SHOWCASE SUMMARY"

echo -e "  ${BOLD}Total:${RESET}  ${total}"
echo -e "  ${GREEN}${BOLD}Passed:${RESET} ${passed}"
if [[ $failed -gt 0 ]]; then
  echo -e "  ${RED}${BOLD}Failed:${RESET} ${failed}"
fi

echo ""
echo -e "  Reports exported to ${BOLD}data/reports/${RESET}"
echo ""

if [[ $failed -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}  ✅ ALL STAGES PASSED — SHOWCASE COMPLETE${RESET}"
else
  echo -e "${RED}${BOLD}  ⚠️  ${failed} stage(s) had issues — review above${RESET}"
fi
echo ""
