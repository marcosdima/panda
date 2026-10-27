#!/usr/bin/env python3
"""Verify documentation links and ``Source:``/``Tests:`` footers.

Exits 0 if everything is in order, non-zero otherwise.

Checks performed on every ``.md`` file under ``docs/``:

- Every relative markdown link resolves to an existing file.
- Each document declares both a ``Source:`` and a ``Tests:`` footer.
- Every path quoted in ``Source:`` / ``Tests:`` exists in the repository.
  Paths may be files or directories; links and anchors are ignored.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

LINK_RE = re.compile(r"\]\(([^)]+)\)")
FOOTER_RE = re.compile(r"^(Source|Tests):[ \t]*(.+)$", re.MULTILINE)
TOKEN_RE = re.compile(r"`([^`]+)`")


def relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def footer_paths(line: str) -> list[str]:
    """Extract repo paths from a footer line (backtick-quoted or comma separated)."""
    quoted = TOKEN_RE.findall(line)
    raw = quoted if quoted else line.split(",")
    paths: list[str] = []
    for token in raw:
        token = token.strip().strip("`").strip().rstrip(".,;:)")
        if token:
            paths.append(token)
    return paths


def resolve_link(doc_path: Path, target: str) -> Path | None:
    target = target.split("#")[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    for base in (doc_path.parent, DOCS_DIR, PROJECT_ROOT):
        candidate = (base / target).resolve()
        if candidate.exists():
            return candidate
    return None


def check_doc(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    doc_name = relative(path)

    for match in LINK_RE.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.split("#")[0].strip() and resolve_link(path, target) is None:
            problems.append(f"{doc_name}: dangling link: {target}")

    footers = list(FOOTER_RE.finditer(text))
    kinds = {match.group(1) for match in footers}
    for kind in ("Source", "Tests"):
        if kind not in kinds:
            problems.append(f"{doc_name}: missing {kind}: footer")

    for match in footers:
        kind, line = match.group(1), match.group(2)
        for token in footer_paths(line):
            if not (PROJECT_ROOT / token).exists():
                problems.append(f"{doc_name}: {kind}: path does not exist: {token}")

    return problems


def main() -> int:
    if not DOCS_DIR.exists():
        print(f"Docs dir not found: {DOCS_DIR}")
        return 1

    files = sorted(DOCS_DIR.rglob("*.md"))
    problems: list[str] = []
    for path in files:
        try:
            rel_parts = path.relative_to(DOCS_DIR).parts
        except ValueError:
            rel_parts = ()
        if rel_parts and rel_parts[0] == "tickets":
            continue
        problems.extend(check_doc(path))

    if problems:
        print(f"Docs verification failed ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"Docs verification OK ({len(files)} file(s) checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
