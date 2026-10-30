"""Tests for the Service Locator (src/services/__init__.py).

Pure logic tests: no Panda3D/ShowBase required, so they run headless and fast.
"""

import pytest

from src.services import services


def setup_function() -> None:
    """Reset the service locator before each test for isolation."""
    services.clear()


def test_register_and_get() -> None:
    services.register("physics", "physics_world")
    assert services.has("physics") is True
    assert "physics" in services
    assert services.get("physics") == "physics_world"


def test_get_with_default() -> None:
    assert services.get("missing", default="fallback") == "fallback"


def test_get_missing_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        services.get("missing")


def test_get_with_type_cast() -> None:
    services.register("count", 42)
    value = services.get("count", typ=int)
    assert value == 42
    assert isinstance(value, int)


def test_has_returns_false_for_unknown() -> None:
    assert services.has("nonexistent") is False
    assert "nonexistent" not in services


def test_clear_removes_all() -> None:
    services.register("a", 1)
    services.register("b", 2)
    services.clear()
    assert services.has("a") is False
    assert services.has("b") is False


def test_register_overwrites() -> None:
    services.register("key", "first")
    services.register("key", "second")
    assert services.get("key") == "second"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
