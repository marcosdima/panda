"""Test package.

The central scene registry lives in ``tests.registry``; this package no longer
selects a single suite via a ``TARGET`` constant. Launch scenes through the
playground (``python -m tests.playground``) or directly
(``python -m tests.panda.<module>``).
"""


def __getattr__(name: str):
    if name == "SCENE_REGISTRY":
        from .registry import SCENE_REGISTRY

        return SCENE_REGISTRY
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["SCENE_REGISTRY"]
