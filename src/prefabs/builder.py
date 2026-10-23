"""Fluent, thin composer for :class:`src.entities.entity.Entity`.

``EntityBuilder`` is intentionally a *layer of convenience*: it only records
handlers and applies node/position/parent transforms at ``build()`` time. It
does **not** duplicate any handler lifecycle logic -- every handler is attached
through ``Entity.add_handler`` so attach/start/update/stop/detach semantics
stay identical to hand-composed entities.

The builder exists to make the *composition order* explicit and readable, not
to introduce a second entity system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.handlers.ai import AIPatrolHandler, FollowHandler
from src.handlers.camera import FirstPersonCameraHandler, ThirdPersonCameraHandler
from src.handlers.graphics import ActorAnimationHandler
from src.handlers.graphics.model import ModelHandler
from src.handlers.input import WASDInputHandler
from src.handlers.physics.character import CharacterControllerHandler
from src.handlers.physics.rigid_body import RigidBodyHandler

if TYPE_CHECKING:
    from src.scenes import Scene


class EntityBuilder:
    """Fluent builder that composes an :class:`Entity` from handlers.

    Handlers are appended in the order the ``with_*`` methods are called, so
    callers control update ordering explicitly. ``with_handler`` is the generic
    escape hatch for any handler not covered by a named helper.
    """

    def __init__(self, name: str = "Entity", node: NodePath | None = None) -> None:
        self._name: str = name
        self._node: NodePath | None = node
        self._handlers: list[Any] = []
        self._position: Vec3 | None = None
        self._parent: NodePath | None = None

    # ------------------------------------------------------------------ #
    # Transforms
    # ------------------------------------------------------------------ #
    def at(self, x: float, y: float, z: float) -> "EntityBuilder":
        self._position = Vec3(float(x), float(y), float(z))
        return self

    def parented_to(self, node: NodePath) -> "EntityBuilder":
        self._parent = node
        return self

    # ------------------------------------------------------------------ #
    # Named handler helpers (thin pass-throughs)
    # ------------------------------------------------------------------ #
    def with_input(self, handler: Any = None, **kwargs: Any) -> "EntityBuilder":
        if handler is None:
            handler = WASDInputHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_character(self, handler: Any = None, **kwargs: Any) -> "EntityBuilder":
        if handler is None:
            handler = CharacterControllerHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_animation(
        self,
        *,
        model_path: str | None = None,
        kaykit: str | None = None,
        handler: Any = None,
        **kwargs: Any,
    ) -> "EntityBuilder":
        if handler is not None:
            self._handlers.append(handler)
            return self
        if kaykit is not None:
            handler = ActorAnimationHandler.kaykit_rig_medium(kaykit, **kwargs)
        elif model_path is not None:
            handler = ActorAnimationHandler(model_path=model_path, **kwargs)
        else:
            handler = ActorAnimationHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_camera(
        self, mode: str = "third_person", handler: Any = None, **kwargs: Any
    ) -> "EntityBuilder":
        if handler is not None:
            self._handlers.append(handler)
            return self
        if mode in ("first", "first_person", "fp"):
            handler = FirstPersonCameraHandler(**kwargs)
        else:
            handler = ThirdPersonCameraHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_patrol(self, handler: Any = None, **kwargs: Any) -> "EntityBuilder":
        if handler is None:
            handler = AIPatrolHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_follow(self, handler: Any = None, **kwargs: Any) -> "EntityBuilder":
        if handler is None:
            handler = FollowHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_model(self, handler: Any = None, **kwargs: Any) -> "EntityBuilder":
        if handler is None:
            handler = ModelHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_rigid_body(self, handler: Any = None, **kwargs: Any) -> "EntityBuilder":
        if handler is None:
            handler = RigidBodyHandler(**kwargs)
        self._handlers.append(handler)
        return self

    def with_handler(self, handler: Any) -> "EntityBuilder":
        """Generic escape hatch for any handler not covered above."""
        self._handlers.append(handler)
        return self

    # ------------------------------------------------------------------ #
    # Build
    # ------------------------------------------------------------------ #
    def build(self, scene: "Scene | None" = None) -> Entity:
        entity = Entity(self._name, node=self._node)
        if self._parent is not None:
            entity.node.reparentTo(self._parent)
        if self._position is not None:
            entity.node.setPos(self._position)
        for handler in self._handlers:
            entity.add_handler(handler)
        if scene is not None:
            scene.add_entity(entity)
        return entity