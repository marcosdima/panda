"""High-level prefabs that compose common game entities.

Each prefab hides the internal handlers and returns a small *rig* dataclass
with typed references, so callers get convenience without losing access for
telemetry or advanced control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from panda3d.core import NodePath, Vec3
from panda3d.bullet import BulletShape

from src.entities.entity import Entity
from src.prefabs.builder import EntityBuilder
from src.handlers.ai import AIPatrolHandler, FollowHandler
from src.handlers.camera import FirstPersonCameraHandler, ThirdPersonCameraHandler
from src.handlers.graphics import ActorAnimationHandler
from src.handlers.graphics.model import ModelHandler
from src.handlers.input import WASDInputHandler
from src.handlers.input.base import InputHandler
from src.handlers.physics.character import CharacterControllerHandler
from src.handlers.physics.rigid_body import RigidBodyHandler
from src.utils.position import world_position

if TYPE_CHECKING:
    from src.scenes import Scene


@dataclass
class PlayerRig:
    entity: Entity
    input: WASDInputHandler
    controller: CharacterControllerHandler
    camera: ThirdPersonCameraHandler | FirstPersonCameraHandler
    animation: ActorAnimationHandler | None = None


@dataclass
class NpcRig:
    entity: Entity
    controller: CharacterControllerHandler
    animation: ActorAnimationHandler | None = None
    ai: AIPatrolHandler | FollowHandler | None = None


def _kwargs(d: dict[str, Any] | None) -> dict[str, Any]:
    return dict(d) if d else {}


def create_player(
    scene: "Scene | None" = None,
    *,
    name: str = "Player",
    model: str = "Knight",
    camera: str = "third_person",
    position: tuple[float, float, float] = (0.0, 0.0, 2.0),
    parent: NodePath | None = None,
    input_kwargs: dict[str, Any] | None = None,
    controller_kwargs: dict[str, Any] | None = None,
    camera_kwargs: dict[str, Any] | None = None,
    animation_kwargs: dict[str, Any] | None = None,
) -> PlayerRig:
    """Compose a player entity (input + character + animation + camera).

    Handlers are attached in the correct order internally; callers only pass
    high-level parameters. Returns a :class:`PlayerRig` with typed references.
    """
    builder = EntityBuilder(name)
    if parent is not None:
        builder.parented_to(parent)
    builder.at(*position)
    builder.with_input(**_kwargs(input_kwargs))
    builder.with_character(**_kwargs(controller_kwargs))
    builder.with_animation(kaykit=model, **_kwargs(animation_kwargs))
    builder.with_camera(camera, **_kwargs(camera_kwargs))
    entity = builder.build(scene)

    animation = entity.get_handler(ActorAnimationHandler)
    return PlayerRig(
        entity=entity,
        input=entity.get_handler(WASDInputHandler),  # type: ignore[arg-type]
        controller=entity.get_handler(CharacterControllerHandler),  # type: ignore[arg-type]
        camera=entity.get_handler(ThirdPersonCameraHandler)  # type: ignore[arg-type]
        or entity.get_handler(FirstPersonCameraHandler),  # type: ignore[arg-type]
        animation=animation,
    )


def create_patrol_npc(
    scene: "Scene | None" = None,
    *,
    name: str = "Npc",
    model: str = "Knight",
    waypoints: Sequence[Any] = (),
    target: Entity | None = None,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    parent: NodePath | None = None,
    follow: bool = False,
    controller_kwargs: dict[str, Any] | None = None,
    animation_kwargs: dict[str, Any] | None = None,
    ai_kwargs: dict[str, Any] | None = None,
) -> NpcRig:
    """Compose an NPC driven by patrol or follow AI.

    The AI handler is attached *before* the controller so its intent is fresh
    each tick, as required by the AI handlers.
    """
    builder = EntityBuilder(name)
    if parent is not None:
        builder.parented_to(parent)
    builder.at(*position)

    # NPCs need an InputHandler for the AI to write into and the controller to read.
    builder.with_handler(InputHandler())

    ai: AIPatrolHandler | FollowHandler | None = None
    if follow and target is not None:
        ai = FollowHandler(target=target, **_kwargs(ai_kwargs))
        builder.with_follow(handler=ai)
    elif waypoints:
        ai = AIPatrolHandler(waypoints=list(waypoints), target=target, **_kwargs(ai_kwargs))
        builder.with_patrol(handler=ai)
    # else: no AI, plain NPC

    builder.with_character(**_kwargs(controller_kwargs))
    builder.with_animation(kaykit=model, **_kwargs(animation_kwargs))
    entity = builder.build(scene)

    animation = entity.get_handler(ActorAnimationHandler)
    return NpcRig(
        entity=entity,
        controller=entity.get_handler(CharacterControllerHandler),  # type: ignore[arg-type]
        animation=animation,
        ai=ai,
    )


def create_static_prop(
    scene: "Scene | None" = None,
    *,
    name: str = "Prop",
    model_path: str,
    from_assets: bool = True,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    parent: NodePath | None = None,
    scale: float = 1.0,
    offset: tuple[float, float, float] | Vec3 = (0.0, 0.0, 0.0),
    shape: BulletShape | None = None,
    mass: float = 0.0,
) -> Entity:
    """Compose a static (or dynamic) prop with optional physics body."""
    builder = EntityBuilder(name)
    if parent is not None:
        builder.parented_to(parent)
    builder.at(*position)
    builder.with_model(model_path=model_path, scale=scale, from_assets=from_assets, offset=offset)
    if shape is not None:
        builder.with_rigid_body(shape=shape, mass=mass)
    return builder.build(scene)