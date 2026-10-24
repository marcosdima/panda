#!/usr/bin/env bash
###############################################################################
# Interactive test-runner menu (bash) with a persistent default test.
#
#  * Scans tests/terminal/ and tests/panda/ for Python test/sandbox files.
#  * Shows a numbered menu in the terminal.
#  * Choices:
#        - number: run that test
#        - r:      re-run the last executed test
#        - d:      mark the last chosen test as the new "default" (persisted)
#        - q:      quit the menu
#  * After a test finishes the menu appears again.
#
#  Persistent default:
#    The file .test_default at the project root stores the path of the test
#    "we are currently working on".  You (or an agent switching test
#    environments) only need to write the new path into that file, and the
#    script will pick it up automatically on the next run.
#    Priority: DEFAULT_TEST env var  >  .test_default file  >  no default.
#
#  CLI (non-interactive, handy for agents / automation):
#    $0 --set-default <path>   write <path> as the default test and exit
#    $0 --run-default          run the default test directly and exit
#    $0 --help                 show this help
#
#  Execution mode:
#    All tests are launched as Python modules (``python -m <module>``) so that
#    relative imports (``from ..__test import Test``) resolve correctly.
#    tests/panda/*.py   -> python -m tests.panda.<module>   (visual sandbox, may open a window)
#    tests/terminal/*   -> windowType=none python -m tests.terminal.<module>  (headless)
###############################################################################

set -u

# ---- Paths / interpreter ----------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

if [[ -x "./.venv/bin/python" ]]; then
    VENV_PYTHON="./.venv/bin/python"
elif [[ -x "./venv/bin/python" ]]; then
    VENV_PYTHON="./venv/bin/python"
else
    VENV_PYTHON="python3"
fi
TEST_ROOTS=("tests/terminal" "tests/panda")
DEFAULT_FILE="$PROJECT_ROOT/.test_default"

# ---- CLI flags (non-interactive) -------------------------------------------
set_default=""
run_default=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --set-default|--default)
            set_default="$2"; shift 2 ;;
        --run-default)
            run_default=1; shift ;;
        -h|--help)
            cat <<EOF
Usage: $0 [--set-default <path>] [--run-default] [-h|--help]

  (no args)      interactive menu
  --set-default <path>
                 write <path> as the persistent default test and exit
  --run-default  run the persistent default test directly and exit
  -h, --help     show this help

The persistent default is stored in: $DEFAULT_FILE
Edit that file directly to change which test is "the one we are testing".
EOF
            exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [[ -n "$set_default" ]]; then
    if [[ "$set_default" != /* ]]; then
        set_default="$PROJECT_ROOT/$set_default"
    fi
    if [[ ! -f "$set_default" ]]; then
        echo "❌ Not a file: $set_default" >&2
        exit 1
    fi
    printf '%s\n' "$set_default" > "$DEFAULT_FILE"
    echo "✅ Default test set to: $set_default"
    echo "   (stored in $DEFAULT_FILE)"
    exit 0
fi

# ---- Collect test files -----------------------------------------------------
ALL_PY=()
for root in "${TEST_ROOTS[@]}"; do
    while IFS= read -r -d '' f; do
        ALL_PY+=("$f")
    done < <(find "$root" -maxdepth 1 -type f -name '*.py' ! -name '__init__.py' -print0 | sort -z)
done

if [[ ${#ALL_PY[@]} -eq 0 ]]; then
    echo "No test files found under ${TEST_ROOTS[*]}." >&2
    exit 1
fi

TEST_FILES=()
TEST_LABELS=()
for f in "${ALL_PY[@]}"; do
    TEST_FILES+=("$f")
    if [[ "$f" == tests/panda/* ]]; then
        TEST_LABELS+=("$(basename "$f")   [panda sandbox]")
    else
        TEST_LABELS+=("$(basename "$f")   [terminal]")
    fi
done

# ---- Resolve persistent default --------------------------------------------
resolve_default_index() {
    local candidate="$1"
    [[ -z "$candidate" ]] && return 1
    for i in "${!TEST_FILES[@]}"; do
        if [[ "${TEST_FILES[$i]}" == "$candidate" ]]; then
            echo "$i"
            return 0
        fi
    done
    return 1
}

DEFAULT_IDX=-1
if [[ -n "${DEFAULT_TEST:-}" ]]; then
    if idx="$(resolve_default_index "$DEFAULT_TEST")"; then DEFAULT_IDX="$idx"; fi
elif [[ -f "$DEFAULT_FILE" ]]; then
    saved="$(cat "$DEFAULT_FILE" | tr -d '[:space:]')"
    if idx="$(resolve_default_index "$saved")"; then DEFAULT_IDX="$idx"; fi
fi

last_index="$DEFAULT_IDX"

# ---- Helpers ----------------------------------------------------------------
# Convert a path like tests/panda/camera_sandbox.py -> tests.panda.camera_sandbox
path_to_module() {
    local p="$1"
    p="${p#./}"            # strip leading ./
    p="${p%.py}"           # strip .py
    p="${p//\//.}"         # replace / with .
    echo "$p"
}

is_panda() { [[ "$1" == tests/panda/* ]]; }

run_one() {
    local test_file="$1"
    local module
    module="$(path_to_module "$test_file")"
    echo ""
    echo "Running test: $(basename "$test_file")  (module: $module)"
    echo "----------------------------------------"
    if is_panda "$test_file"; then
        "$VENV_PYTHON" -m "$module"
    else
        env windowType=none "$VENV_PYTHON" -m "$module"
    fi
    local rc=$?
    echo "----------------------------------------"
    if (( rc == 0 )); then
        echo "✅ Test completed successfully."
    else
        echo "❌ Test exited with code $rc."
    fi
    return $rc
}

save_default() {
    local test_file="$1"
    printf '%s\n' "$test_file" > "$DEFAULT_FILE"
    echo "🔖 Default test set to: $(basename "$test_file")"
    echo "   (stored in $DEFAULT_FILE)"
}

# ---- Non-interactive: run the default directly ------------------------------
if (( run_default )); then
    if (( DEFAULT_IDX < 0 )); then
        echo "No default test configured. Use --set-default <path> first." >&2
        exit 1
    fi
    run_one "${TEST_FILES[$DEFAULT_IDX]}"
    exit $?
fi

# ---- Interactive menu -------------------------------------------------------
while true; do
    echo ""
    echo "=== Test Menu ==="
    for i in "${!TEST_FILES[@]}"; do
        marker=""
        if (( i == DEFAULT_IDX )); then marker="  <-- default"; fi
        printf "  %2d) %s%s\n" $((i+1)) "${TEST_LABELS[$i]}" "$marker"
    done
    if (( last_index >= 0 )); then
        echo "  r) Re-run last test ($(basename "${TEST_FILES[$last_index]}"))"
    fi
    if (( last_index >= 0 )); then
        echo "  d) Mark last chosen test as the new default"
    fi
    echo "  q) Quit"
    echo -n "Select a test (number, r, d, q): "
    read -r choice

    case "$choice" in
        q|Q)
            echo "Bye!"
            exit 0 ;;
        r|R)
            if (( last_index < 0 )); then
                echo "No test has been run yet."
                continue
            fi
            idx="$last_index" ;;
        d|D)
            if (( last_index < 0 )); then
                echo "No test chosen yet to set as default."
                continue
            fi
            save_default "${TEST_FILES[$last_index]}"
            DEFAULT_IDX="$last_index"
            continue ;;
        ''|*[!0-9]*)
            echo "Invalid input – enter a number, 'r', 'd' or 'q'."
            continue ;;
        *)
            idx=$((choice - 1))
            if (( idx < 0 || idx >= ${#TEST_FILES[@]} )); then
                echo "Selection out of range."
                continue
            fi
            last_index="$idx" ;;
    esac

    run_one "${TEST_FILES[$idx]}"
done
