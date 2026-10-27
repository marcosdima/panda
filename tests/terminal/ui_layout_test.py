"""Headless smoke tests for UI layout containers."""

import builtins

if getattr(builtins, "base", None) is None:
    from direct.showbase.ShowBase import ShowBase

    ShowBase(windowType="none")

import pytest

from src.ui import UIButton, UIColumn, UIGrid, UIPanel, UIRow


def test_panel_creation() -> None:
    parent = builtins.base.aspect2d
    panel = UIPanel(parent=parent, title="Panel", width=0.5, height=0.4)
    assert not panel.destroyed
    assert panel.content_parent is not None
    panel.destroy()


def test_row_layout() -> None:
    parent = builtins.base.aspect2d
    row = UIRow(parent=parent, spacing=0.05)
    b1 = UIButton(parent=row.node, text="A")
    b2 = UIButton(parent=row.node, text="B")
    row.add(b1)
    row.add(b2)
    assert b1.node.getPos().x != b2.node.getPos().x
    row.destroy()


def test_column_layout() -> None:
    parent = builtins.base.aspect2d
    column = UIColumn(parent=parent, spacing=0.05)
    b1 = UIButton(parent=column.node, text="A")
    b2 = UIButton(parent=column.node, text="B")
    column.add(b1)
    column.add(b2)
    assert b1.node.getPos().z != b2.node.getPos().z
    column.destroy()


def test_grid_layout() -> None:
    parent = builtins.base.aspect2d
    grid = UIGrid(parent=parent, columns=2, spacing=(0.05, 0.05))
    buttons = [UIButton(parent=grid.node, text=f"B{i}") for i in range(4)]
    for button in buttons:
        grid.add(button)
    xs = {round(b.node.getPos().x, 3) for b in buttons}
    zs = {round(b.node.getPos().z, 3) for b in buttons}
    assert len(xs) >= 2
    assert len(zs) >= 2
    grid.destroy()


def test_layout_destroy() -> None:
    parent = builtins.base.aspect2d
    row = UIRow(parent=parent)
    button = UIButton(parent=row.node, text="A")
    row.add(button)
    row.destroy()
    assert row.destroyed


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
