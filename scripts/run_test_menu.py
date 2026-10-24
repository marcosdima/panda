"""Interactive test runner menu.

Usage:
    $ ./scripts/run_test_menu.py

The script scans the ``tests/terminal`` package for ``*.py`` test modules,
lists them as a numbered menu, and allows the user to select a test to run.
After the selected test finishes (whether it passes or fails), the script
returns to the menu so another test can be executed.  The menu also provides
an option to re‑run the *last* executed test ("current" test) and an option
to quit.

The implementation is deliberately simple – it uses ``subprocess.run`` to
invoke ``pytest`` with the chosen file.  ``windowType='none'`` is enforced for
head‑less execution, but if the selected test spawns a graphical sandbox it
will open a window as usual.
"""

#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = PROJECT_ROOT / "tests" / "terminal"
if (PROJECT_ROOT / ".venv" / "bin" / "python").exists():
    PYTHON_EXEC = (PROJECT_ROOT / ".venv" / "bin" / "python").resolve()
elif (PROJECT_ROOT / "venv" / "bin" / "python").exists():
    PYTHON_EXEC = (PROJECT_ROOT / "venv" / "bin" / "python").resolve()
else:
    PYTHON_EXEC = Path(sys.executable)
PYTEST_CMD = [str(PYTHON_EXEC), "-m", "pytest", "-q"]

def discover_tests() -> list[Path]:
    """Return a sorted list of ``*.py`` files inside ``tests/terminal``.

    Only files that look like test modules (start with ``test_`` or end with
    ``_test.py``) are included.  The list is sorted alphabetically for a stable
    menu order.
    """
    candidates = list(TESTS_ROOT.glob("*.py"))
    test_files = [p for p in candidates if p.name.startswith("test_") or p.name.endswith("_test.py")]
    return sorted(test_files)

def run_test(file_path: Path) -> int:
    """Execute ``pytest`` on the given file.

    Returns the subprocess exit code (``0`` == success).  The command runs with
    the environment variable ``windowType='none'`` so head‑less unit tests are
    fast, but any graphical sandbox inside the test will still open a window.
    """
    env = os.environ.copy()
    env.setdefault("windowType", "none")
    cmd = PYTEST_CMD + [str(file_path)]
    print(f"\nRunning test: {file_path.name}\n{'=' * (15 + len(file_path.name))}\n")
    result = subprocess.run(cmd, env=env)
    print("\n" + "─" * 40)
    return result.returncode

def main() -> None:
    tests = discover_tests()
    if not tests:
        print("No test modules found in", TESTS_ROOT)
        sys.exit(1)

    last_index: int | None = None

    while True:
        print("\nAvailable tests (choose a number):")
        for i, test_path in enumerate(tests, start=1):
            print(f"  {i}. {test_path.name}")
        print("  r. Re‑run last test" if last_index is not None else "  r. (no test run yet)")
        print("  q. Quit")

        choice = input("\nSelection: ").strip().lower()
        if choice == "q":
            print("Exiting test menu.")
            break
        if choice == "r":
            if last_index is None:
                print("No previous test to run.")
                continue
            idx = last_index
        else:
            if not choice.isdigit():
                print("Invalid input – please enter a number, 'r' or 'q'.")
                continue
            idx = int(choice) - 1
            if not (0 <= idx < len(tests)):
                print("Selection out of range.")
                continue
            last_index = idx
        test_file = tests[idx]
        rc = run_test(test_file)
        if rc == 0:
            print("Test completed successfully.")
        else:
            print(f"Test finished with exit code {rc}.")
        # Loop back to menu automatically.

if __name__ == "__main__":
    main()
