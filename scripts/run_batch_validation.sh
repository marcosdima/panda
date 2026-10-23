#!/usr/bin/env bash
###############################################################################
# Batch validation for a feature batch (lead-owned entry point).
#
# Runs, in order:
#   1. scripts/check_diff_scope.py        - naming, docs footers, scope
#   2. scripts/audit_handler_contract.py  - handler lifecycle contract
#   3. scripts/verify_docs_links.py       - links + Source/Tests footers
#   4. ./venv/bin/python -m tests.terminal.run_all  - full headless suite
#
# Every step runs even if an earlier one fails, so a single pass reports all
# the mechanical problems. The script exits non-zero if any step failed.
#
# Usage:
#   ./scripts/run_batch_validation.sh                # full validation
#   ./scripts/run_batch_validation.sh --no-suite     # skip the headless suite
#   ./scripts/run_batch_validation.sh --strict       # advisories are failures
#   ./scripts/run_batch_validation.sh src/... docs/... [--no-suite]
#                                                    # restrict the scope check
###############################################################################

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

PYTHON="./venv/bin/python"
RUN_SUITE=1
STRICT=0
SCOPE_PATHS=()

for arg in "$@"; do
    case "$arg" in
        --no-suite) RUN_SUITE=0 ;;
        --strict)   STRICT=1 ;;
        --*)        echo "Unknown option: $arg" >&2; exit 2 ;;
        *)          SCOPE_PATHS+=("$arg") ;;
    esac
done

failed_steps=()

run_step() {
    local name="$1"; shift
    echo
    echo "============================================================"
    echo "Step: $name"
    echo "============================================================"
    if "$@"; then
        echo "PASS: $name"
    else
        echo "FAIL: $name"
        failed_steps+=("$name")
    fi
}

scope_args=()
if (( ${#SCOPE_PATHS[@]} > 0 )); then
    scope_args=("${SCOPE_PATHS[@]}")
fi
if (( STRICT )); then
    scope_args+=(--strict)
fi

run_step "check_diff_scope"      "$PYTHON" scripts/check_diff_scope.py "${scope_args[@]}"
run_step "audit_handler_contract" "$PYTHON" scripts/audit_handler_contract.py
run_step "verify_docs_links"      "$PYTHON" scripts/verify_docs_links.py

if (( RUN_SUITE )); then
    run_step "headless_suite" "$PYTHON" -m tests.terminal.run_all
fi

echo
echo "============================================================"
if (( ${#failed_steps[@]} == 0 )); then
    echo "Batch validation: ALL STEPS PASSED."
    exit 0
fi
echo "Batch validation: ${#failed_steps[@]} step(s) FAILED: ${failed_steps[*]}"
exit 1
