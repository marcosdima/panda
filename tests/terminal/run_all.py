"""Run every headless terminal suite in an isolated subprocess and report results.

Each suite module under ``tests/terminal`` (excluding ``_``-prefixed helpers)
is executed as ``python -m tests.terminal.<name>`` so ShowBase bootstraps,
global singletons, and Bullet worlds stay fully isolated between suites.

Usage:
    python -m tests.terminal.run_all
    python -m tests.terminal.run_all physics_handlers events
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

_TERMINAL_DIR = Path(__file__).resolve().parent
_SKIP_MODULES = {"run_all"}


def discover_suites() -> list[str]:
    """Return sorted suite module names found in ``tests/terminal``."""
    names = []
    for path in _TERMINAL_DIR.glob("*.py"):
        if path.name.startswith("_") or path.stem in _SKIP_MODULES:
            continue
        names.append(path.stem)
    return sorted(names)


def run_suite(name: str) -> SimpleNamespace:
    """Execute one suite in a subprocess and capture its outcome."""
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-u", "-m", f"tests.terminal.{name}"],
        cwd=_TERMINAL_DIR.parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return SimpleNamespace(
        name=name,
        exit_code=completed.returncode,
        output=completed.stdout or "",
        duration=time.monotonic() - started,
    )


def main(targets: list[str] | None = None) -> int:
    """Run the requested suites (or all discovered) and return a process exit code."""
    suites = [s for s in (targets if targets else discover_suites()) if s not in _SKIP_MODULES]
    if not suites:
        print("No terminal suites discovered.")
        return 1

    print(f"Running {len(suites)} terminal suite(s)...\n")
    results: list[SimpleNamespace] = []
    for name in suites:
        print(f"=== {name} ".ljust(60, "="))
        result = run_suite(name)
        results.append(result)
        tail_lines = [line for line in result.output.splitlines() if line.strip()][-8:]
        for line in tail_lines:
            print(f"  {line}")
        status = "PASS" if result.exit_code == 0 else f"FAIL(exit={result.exit_code})"
        print(f"--- {name}: {status} in {result.duration:.1f}s\n")

    failed = [r for r in results if r.exit_code != 0]
    print("=" * 60)
    print(f"Total: {len(results)} | Passed: {len(results) - len(failed)} | Failed: {len(failed)}")
    for r in failed:
        print(f"  FAILED: {r.name} (exit={r.exit_code})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
