#!/usr/bin/env python3
"""Check that a batch of changes stays within the project scope.

Usage:
    scripts/check_diff_scope.py                   # inspect the whole working tree
    scripts/check_diff_scope.py src/... docs/...  # inspect only a feature batch
    scripts/check_diff_scope.py --strict          # advisories become failures
    scripts/check_diff_scope.py --all             # also fail on root/config files

Hard failures (exit 1):
- A *new* file under ``tests/terminal/`` that is not named ``*_test.py`` or
  lacks the ``pytest.main([__file__])`` guard.
- A *new* document under ``docs/`` without ``Source:``/``Tests:`` footers.

Advisory notes (printed, fatal only with ``--strict``):
- A public class under ``src/`` that its package ``__init__.py`` does not
  mention. Module-path imports are a valid convention here, so this is a
  reminder to check whether the new symbol should be re-exported.
- Modified (not new) files that break the hard checks above. The repository
  still contains older tests and components that predate these conventions.
- Files outside the project trees, unless ``--all`` is passed.

Paths outside ``src/``, ``tests/``, ``docs/``, ``scripts/`` and ``.opencode/``
are ignored in the default whole-tree mode: they belong to other batches.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_TREES = ("src/", "tests/", "docs/", "scripts/", ".opencode/")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git {' '.join(args)} failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(2)
    return result.stdout


def normalize(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return path


def status_map() -> dict[str, str]:
    """Map repo-relative path -> one-letter git status (A/M/D/R/C/?)."""
    entries: dict[str, str] = {}
    tokens = git("status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        code = token[:2]
        path = normalize(token[3:])
        entries[path] = code[0] if code[0] != " " else code[1]
        if code[0] in {"R", "C"}:
            index += 1  # the next token is the original path
    return entries


def is_new(code: str) -> bool:
    return code in {"A", "?"}


def check_file(rel: str, code: str) -> tuple[list[str], list[str]]:
    """Return (hard_failures, advisories) for one repo-relative path."""
    failures: list[str] = []
    advisories: list[str] = []
    path = PROJECT_ROOT / rel
    new = is_new(code)

    if not path.exists():
        return failures, advisories  # deleted file, nothing to inspect

    if rel.startswith("tests/terminal/") and path.suffix == ".py":
        if not path.stem.endswith("_test"):
            message = f"terminal test does not end with _test: {rel}"
            (failures if new else advisories).append(message)
        else:
            text = path.read_text(encoding="utf-8")
            if "pytest.main([__file__])" not in text:
                (failures if new else advisories).append(f"terminal test missing pytest main guard: {rel}")

    if rel.startswith("src/") and path.suffix == ".py" and path.name != "__init__.py":
        init_file = path.parent / "__init__.py"
        if init_file.exists():
            init_text = init_file.read_text(encoding="utf-8")
            text = path.read_text(encoding="utf-8")
            for cls in re.findall(r"^class\s+([A-Z]\w+)", text, re.MULTILINE):
                if cls not in init_text:
                    message = f"public class {cls} in {rel} not exported from {init_file.relative_to(PROJECT_ROOT)}"
                    advisories.append(message)

    if rel.startswith("docs/") and not rel.startswith("docs/tickets/") and path.suffix == ".md":
        text = path.read_text(encoding="utf-8")
        if "Source:" not in text or "Tests:" not in text:
            message = f"doc missing Source:/Tests: footer: {rel}"
            (failures if new else advisories).append(message)

    return failures, advisories


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    include_all = "--all" in argv
    explicit = [normalize(a) for a in argv if not a.startswith("--")]
    statuses = status_map()

    if explicit:
        paths = explicit
        ignored: list[str] = []
    else:
        paths = []
        ignored = []
        for rel in sorted(statuses):
            if any(rel.startswith(tree) for tree in PROJECT_TREES):
                paths.append(rel)
            else:
                ignored.append(rel)

    if not paths:
        print("No changed files in scope (nothing staged/modified/untracked).")
        return 0

    failures: list[str] = []
    advisories: list[str] = []

    if include_all:
        for rel in ignored:
            failures.append(f"file outside {', '.join(PROJECT_TREES)}: {rel}")
        ignored = []

    for rel in paths:
        if not any(rel.startswith(tree) for tree in PROJECT_TREES):
            message = f"file outside {', '.join(PROJECT_TREES)}: {rel}"
            (failures if include_all else advisories).append(message)
            continue
        file_failures, file_advisories = check_file(rel, statuses.get(rel, "M"))
        failures.extend(file_failures)
        advisories.extend(file_advisories)

    for advisory in advisories:
        print(f"  note: {advisory}")
    if ignored:
        print(f"  note: {len(ignored)} file(s) outside the project trees ignored (pass --all to inspect them).")
    if failures:
        print(f"Scope check failed ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    if strict and advisories:
        print(f"Scope check failed in --strict mode ({len(advisories)} note(s)).")
        return 1

    print(f"Scope check OK ({len(paths)} file(s), {len(advisories)} note(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
