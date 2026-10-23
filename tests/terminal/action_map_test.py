"""Headless tests for ActionMap and its integration with WASDInputHandler."""
import builtins
from types import SimpleNamespace

import pytest

from src.entities.entity import Entity
from src.handlers.input import ActionMap, WASDInputHandler
from src.handlers.input.action_map import resolve_button


def down(*names):
    held = {resolve_button(n) for n in names}
    return lambda btn: btn in held


def test_default_bindings():
    amap = ActionMap.default()
    assert amap.keys_for("jump") == ["space"]
    assert amap.is_down("move_forward", down("w"))
    assert amap.is_down("move_forward", down("up"))
    assert not amap.is_down("jump", down("w"))
    assert not amap.is_down("unknown", down("w"))


def test_bind_unbind_rebind():
    amap = ActionMap({"jump": ["space"]})
    amap.bind("jump", "x")
    amap.bind("jump", "X")  # duplicate ignored (case-insensitive)
    assert amap.keys_for("jump") == ["space", "x"]
    amap.unbind("jump", "space")
    assert not amap.is_down("jump", down("space"))
    assert amap.is_down("jump", down("x"))
    amap.rebind("jump", ["mouse1"])
    assert amap.keys_for("jump") == ["mouse1"]
    amap.unbind("jump")
    assert amap.actions == []


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        resolve_button("notakey")


class _Watcher:
    def __init__(self, held):
        self.held = set(held)

    def is_button_down(self, btn):
        return btn in self.held


class _Base:
    def __init__(self, watcher):
        self.mouseWatcherNode = watcher

    def destroy(self):
        pass


def _run(handler_map, held_names):
    entity = Entity("MapHero")
    wasd = WASDInputHandler(handler_map)
    entity.add_handler(wasd)
    original = getattr(builtins, "base", None)
    try:
        builtins.base = _Base(_Watcher({resolve_button(n) for n in held_names}))
        entity.start()
        entity.update(0.016)
        return SimpleNamespace(
            move_vector=wasd.move_vector,
            down={a for a in ("jump", "sprint", "interact") if wasd.is_action_down(a)},
        )
    finally:
        if original is not None:
            builtins.base = original
        else:
            delattr(builtins, "base")
        entity.stop()
        entity.free()


def test_wasd_default_map_unchanged():
    wasd = _run(None, ["w", "d", "space", "lshift"])
    assert abs(wasd.move_vector.x - 0.7071) < 1e-3 and abs(wasd.move_vector.y - 0.7071) < 1e-3
    assert {"jump", "sprint"} <= wasd.down


def test_wasd_custom_map_and_extra_action():
    amap = ActionMap.default()
    amap.rebind("move_forward", ["i"])
    amap.rebind("jump", ["j"])
    amap.bind("interact", "e")
    wasd = _run(amap, ["i", "j", "e", "w"])  # 'w' no longer bound
    assert wasd.move_vector.y == 1.0 and wasd.move_vector.x == 0.0
    assert wasd.down == {"jump", "interact"}


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__]))
