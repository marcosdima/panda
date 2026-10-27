"""Smoke tests for the central scene registry."""

from pathlib import Path

import pytest

from tests.registry import SCENE_REGISTRY


def test_registry_is_nonempty_dict() -> None:
    assert isinstance(SCENE_REGISTRY, dict)
    assert SCENE_REGISTRY


def test_registry_entries_shape() -> None:
    for key, value in SCENE_REGISTRY.items():
        assert isinstance(key, str) and key
        assert isinstance(value, tuple) and len(value) == 3
        title, category, scene_cls = value
        assert isinstance(title, str) and title
        assert category in {"visual", "integration"}
        assert isinstance(scene_cls, type)


def test_visual_scenes_present() -> None:
    visual = {key for key, value in SCENE_REGISTRY.items() if value[1] == "visual"}
    for key in ("animation_state", "animation_blend", "ai", "character"):
        assert key in visual


def test_scene_modules_exist() -> None:
    project_root = Path(__file__).resolve().parents[2]
    for _key, (_title, _category, scene_cls) in SCENE_REGISTRY.items():
        module_name = scene_cls.__module__
        assert module_name.startswith("tests.")
        relative = module_name.replace(".", "/") + ".py"
        assert (project_root / relative).is_file()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
