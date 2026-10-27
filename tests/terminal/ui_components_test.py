"""Headless smoke tests for the reusable UI components."""

import builtins

if getattr(builtins, "base", None) is None:
    from direct.showbase.ShowBase import ShowBase

    ShowBase(windowType="none")

import pytest
from panda3d.core import NodePath

from src.ui import UIButton, UIList, UIScrollContainer, UITheme


def test_button_creation_and_destroy() -> None:
    parent = builtins.base.aspect2d
    button = UIButton(parent=parent, text="Hello")
    assert not button.destroyed
    assert button.node is not None
    button.destroy()
    assert button.destroyed
    assert button.node is None


def test_button_text_update() -> None:
    parent = builtins.base.aspect2d
    button = UIButton(parent=parent, text="Before")
    button.set_text("After")
    assert button.node["text"] == "After"
    button.destroy()


def test_button_enabled_toggle() -> None:
    parent = builtins.base.aspect2d
    button = UIButton(parent=parent, text="Run", enabled=True)
    assert button.enabled is True
    button.set_enabled(False)
    assert button.enabled is False
    assert button.node["state"] == "disabled"
    button.destroy()


def test_button_command_invoked() -> None:
    parent = builtins.base.aspect2d
    calls: list[int] = []
    button = UIButton(parent=parent, text="Run", command=lambda: calls.append(1))
    button._on_click()
    assert calls == [1]
    button.set_enabled(False)
    button._on_click()
    assert calls == [1]
    button.destroy()


def test_list_add_remove_clear() -> None:
    parent = builtins.base.aspect2d
    ui_list = UIList(parent=parent, items=[("a", 1), ("b", 2)])
    assert ui_list.items_count == 2
    ui_list.remove_item(0)
    assert ui_list.items_count == 1
    ui_list.clear()
    assert ui_list.items_count == 0
    ui_list.destroy()


def test_list_selection_callback() -> None:
    parent = builtins.base.aspect2d
    selected: list[tuple[int, object]] = []
    ui_list = UIList(
        parent=parent,
        items=[("a", 1), ("b", 2)],
        on_select=lambda index, value: selected.append((index, value)),
    )
    ui_list.select(1)
    assert ui_list.selected_index == 1
    assert ui_list.selected_value == 2
    assert selected == [(1, 2)]
    ui_list.destroy()


def test_scroll_container_content() -> None:
    parent = builtins.base.aspect2d
    container = UIScrollContainer(parent=parent, width=0.4, height=0.4)
    assert container.canvas is not None
    content = NodePath("content")
    container.set_content(content)
    assert content.getParent() is not None
    container.destroy()


def test_theme_defaults() -> None:
    theme = UITheme()
    assert theme.scale > 0
    assert theme.button_frame_color(True) == theme.frame_color
    assert theme.button_frame_color(False) == theme.disabled_color


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
