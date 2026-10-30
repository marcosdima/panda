#!/usr/bin/env python3
"""Audit that handler modules respect the Handler lifecycle contract.

Exits 0 if everything is in order, non-zero otherwise.

Hard checks (exit 1) on every helper class under ``src/handlers/``:

- ``on_attach`` and ``on_detach`` must call ``super()``: the base class owns
  the ``entity`` reference, so skipping it leaves a dangling or missing link.
- ``direct.showbase`` must only be imported under ``if TYPE_CHECKING:``.
  ``direct.gui`` is allowed: UI handlers import it at module level and guard
  every use behind a live ``base``.
- ``attachNewNode`` must not run from ``__init__``: a handler creates nodes in
  ``on_attach`` / ``on_start`` so it never owns a node before attachment.
- Collaborators are read with ``entity.get_handler(Type)``; positional
  indexing such as ``entity.get_handlers()[0]`` is rejected.
- ``on_update`` / ``on_post_update`` declare exactly ``(self, dt)`` so the
  per-frame loop can call every handler uniformly.

Advisory notes (printed, never fatal):

- ``on_start`` / ``on_stop`` / ``on_detach`` that call ``super()`` after other
  statements. Cleanup order is sometimes intentional, so this is a reminder,
  not a defect. Use ``--strict`` to make advisories fatal.

Every finding is printed as ``path:line: message``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLERS_DIR = PROJECT_ROOT / "src" / "handlers"

SUPER_REQUIRED = {"on_attach", "on_detach"}
UPDATE_HOOKS = {"on_update", "on_post_update"}
ORDERED_HOOKS = {"on_start", "on_stop", "on_detach"}


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def is_docstring(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


def is_super_call(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr):
        return False
    value = stmt.value
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and isinstance(value.func.value, ast.Call)
        and isinstance(value.func.value.func, ast.Name)
        and value.func.value.func.id == "super"
    )


def calls_super(func: ast.FunctionDef) -> bool:
    return any(is_super_call_node(node) for node in ast.walk(func))


def is_super_call_node(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name)
        and node.func.value.func.id == "super"
    )


def is_helper_class(cls: ast.ClassDef) -> bool:
    if cls.name == "Handler":
        return False
    for base in cls.bases:
        name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        if name.endswith("Handler") or name.endswith("Component"):
            return True
    return False


def helper_classes(tree: ast.Module) -> list[ast.ClassDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and is_helper_class(node)]


def methods(cls: ast.ClassDef) -> list[ast.FunctionDef]:
    return [node for node in cls.body if isinstance(node, ast.FunctionDef)]


def check_super_calls(path: Path, cls: ast.ClassDef, advisories: list[str]) -> list[str]:
    problems: list[str] = []
    for func in methods(cls):
        if func.name in SUPER_REQUIRED and not calls_super(func):
            problems.append(f"{rel(path)}:{func.lineno}: {cls.name}.{func.name} must call super()")
        if func.name not in ORDERED_HOOKS or not calls_super(func):
            continue
        body = list(func.body)
        while body and is_docstring(body[0]):
            body.pop(0)
        if body and not is_super_call(body[0]):
            advisories.append(
                f"{rel(path)}:{body[0].lineno}: {cls.name}.{func.name} calls super() after other statements"
            )
    return problems


def _in_type_checking(node: ast.stmt, parents: dict[ast.AST, ast.AST]) -> bool:
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.If):
            test = parent.test
            if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            ):
                return True
        current = parent
    return False


def check_showbase_imports(path: Path, tree: ast.Module) -> list[str]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    problems: list[str] = []
    for node in ast.walk(tree):
        module: str | None = None
        if isinstance(node, ast.ImportFrom):
            module = node.module
        elif isinstance(node, ast.Import):
            module = next(
                (alias.name for alias in node.names if alias.name and alias.name.startswith("direct.showbase")),
                None,
            )
        if not module or not module.startswith("direct.showbase"):
            continue
        if not _in_type_checking(node, parents):
            problems.append(
                f"{rel(path)}:{node.lineno}: direct.showbase imported outside "
                "`if TYPE_CHECKING:`; keep handlers headless-safe"
            )
    return problems


def check_init_node_creation(path: Path, cls: ast.ClassDef) -> list[str]:
    problems: list[str] = []
    for func in methods(cls):
        if func.name != "__init__":
            continue
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "attachNewNode"
            ):
                problems.append(
                    f"{rel(path)}:{node.lineno}: {cls.name}.__init__ calls attachNewNode; "
                    "create nodes in on_attach/on_start"
                )
    return problems


def check_handlers_indexing(path: Path, tree: ast.Module) -> list[str]:
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "get_handlers":
            problems.append(
                f"{rel(path)}:{node.lineno}: positional get_handlers() indexing; use entity.get_handler(Type)"
            )
    return problems


def check_update_signature(path: Path, cls: ast.ClassDef) -> list[str]:
    problems: list[str] = []
    for func in methods(cls):
        if func.name not in UPDATE_HOOKS:
            continue
        args = func.args
        positional = list(args.posonlyargs) + list(args.args)
        if len(positional) != 2 or args.vararg is not None:
            problems.append(f"{rel(path)}:{func.lineno}: {cls.name}.{func.name} must declare (self, dt)")
            continue
        if positional[1].arg != "dt":
            problems.append(
                f"{rel(path)}:{func.lineno}: {cls.name}.{func.name} seconds argument is "
                f"{positional[1].arg!r}, expected 'dt'"
            )
    return problems


def audit_file(path: Path, advisories: list[str]) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{rel(path)}:{exc.lineno}: syntax error: {exc.msg}"]

    classes = helper_classes(tree)
    if not classes:
        return []

    problems: list[str] = []
    for cls in classes:
        problems.extend(check_super_calls(path, cls, advisories))
        problems.extend(check_init_node_creation(path, cls))
        problems.extend(check_update_signature(path, cls))
    problems.extend(check_showbase_imports(path, tree))
    problems.extend(check_handlers_indexing(path, tree))
    return problems


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    if not HANDLERS_DIR.exists():
        print(f"Handlers dir not found: {HANDLERS_DIR}")
        return 1

    checked = 0
    problems: list[str] = []
    advisories: list[str] = []
    for path in sorted(HANDLERS_DIR.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        checked += 1
        problems.extend(audit_file(path, advisories))

    for advisory in advisories:
        print(f"  note: {advisory}")
    if problems:
        print(f"Handler contract audit failed ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    if strict and advisories:
        print(f"Handler contract audit failed in --strict mode ({len(advisories)} note(s)).")
        return 1

    print(f"Handler contract audit OK ({checked} file(s), {len(advisories)} note(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
