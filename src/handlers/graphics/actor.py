from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any
from panda3d.core import NodePath, Vec3

from src.globals.loader import GlobalLoader
from src.handlers.base import Handler
from src.handlers.physics.character import CharacterControllerHandler

if TYPE_CHECKING:
    from direct.actor.Actor import Actor
    from src.entities.entity import Entity


class ActorAnimationHandler(Handler):
    """Modular graphics handler managing an animated glTF Actor character.

    Creates a dedicated visual pivot at (0, 0, 0) attached to CharacterControllerHandler's
    controller NodePath (or entity node) to eliminate rotation drift, loads the glTF Actor
    model with skeletal animations, and synchronizes animation playback with character
    movement states.
    """

    def __init__(
        self,
        model_path: str = "X Bot.glb",
        animations: dict[str, str] | None = None,
        scale: float = 1.0,
        offset: Vec3 = Vec3(0.0, 0.0, -1.0),
        hpr: Vec3 = Vec3(180.0, 90.0, 0.0),
    ) -> None:
        super().__init__()
        self.model_path: str = model_path
        self.animations: dict[str, str] = (
            animations if animations is not None else {"Idle": "anims/X Bot@Idle.glb"}
        )
        self.scale: float = float(scale)
        self.offset: Vec3 = Vec3(offset)
        self.hpr: Vec3 = Vec3(hpr)

        self.visual_pivot: NodePath | None = None
        self.actor: Any | None = None
        self._current_anim: str | None = None

    @property
    def current_animation(self) -> str | None:
        """Return the name of the currently active animation clip, or None."""
        return self._current_anim

    def _setup_nodes(self) -> None:
        """Initialize the visual pivot at (0, 0, 0) and load the glTF Actor model."""
        if self.entity is None:
            return

        # Ensure panda3d-gltf loader is registered to parse glTF without segfaults
        import gltf  # noqa: F401

        controller = self.entity.get_handler(CharacterControllerHandler)
        parent_np: NodePath = (
            controller.controller_np
            if controller is not None
            and controller.controller_np is not None
            and not controller.controller_np.isEmpty()
            else self.entity.node
        )

        # Create or reparent visual_pivot at (0, 0, 0)
        if self.visual_pivot is None or self.visual_pivot.isEmpty():
            self.visual_pivot = parent_np.attachNewNode("visual_pivot")
            self.visual_pivot.setPos(0.0, 0.0, 0.0)
        elif self.visual_pivot.getParent() != parent_np:
            self.visual_pivot.reparentTo(parent_np)
            self.visual_pivot.setPos(0.0, 0.0, 0.0)

        # Load Actor model via GlobalLoader and attach to visual_pivot
        if self.actor is None or (hasattr(self.actor, "isEmpty") and self.actor.isEmpty()):
            self.actor = GlobalLoader.load_actor(self.model_path, self.animations)
            self.actor.reparentTo(self.visual_pivot)
            self.actor.setScale(self.scale)
            self.actor.setPos(self.offset)
            self.actor.setHpr(self.hpr)

        # Bind controller.visual_node to visual_pivot for drift-free rotation
        if controller is not None:
            controller.visual_node = self.visual_pivot

    def _cleanup_nodes(self) -> None:
        """Stop animation, cleanup Actor, and remove visual nodes cleanly."""
        if self.actor is not None:
            if hasattr(self.actor, "stop"):
                self.actor.stop()
            if hasattr(self.actor, "cleanup"):
                self.actor.cleanup()
            if hasattr(self.actor, "isEmpty") and not self.actor.isEmpty():
                self.actor.removeNode()
            self.actor = None
        self._current_anim = None

        if self.entity is not None:
            controller = self.entity.get_handler(CharacterControllerHandler)
            if controller is not None:
                if (
                    controller.visual_node == self.visual_pivot
                    or (controller.visual_node is not None and controller.visual_node.isEmpty())
                ):
                    controller.visual_node = None

        if self.visual_pivot is not None and not self.visual_pivot.isEmpty():
            self.visual_pivot.removeNode()
            self.visual_pivot = None

    def on_attach(self, entity: Entity) -> None:
        """Attach handler to entity, set up visual pivot and Actor."""
        super().on_attach(entity)
        self._setup_nodes()

    def on_start(self) -> None:
        """Called when active scene or entity starts. Loops Idle animation if available."""
        super().on_start()
        if (
            self.visual_pivot is None
            or self.visual_pivot.isEmpty()
            or self.actor is None
            or (hasattr(self.actor, "isEmpty") and self.actor.isEmpty())
        ):
            self._setup_nodes()

        # Start default Idle loop
        if self.actor is not None and hasattr(self.actor, "getAnimNames"):
            anim_names = self.actor.getAnimNames()
            if "Idle" in anim_names:
                self.actor.loop("Idle")
                self._current_anim = "Idle"

    def on_update(self, dt: float) -> None:
        """Per-frame update managing animation states based on character movement speed."""
        super().on_update(dt)
        if self.actor is None or not hasattr(self.actor, "getAnimNames"):
            return

        # Check movement speed from CharacterControllerHandler
        speed = 0.0
        is_sprinting = False
        if self.entity is not None:
            controller = self.entity.get_handler(CharacterControllerHandler)
            if controller is not None:
                # Ensure controller.visual_node points to visual_pivot
                if (
                    controller.visual_node != self.visual_pivot
                    and self.visual_pivot is not None
                    and not self.visual_pivot.isEmpty()
                ):
                    controller.visual_node = self.visual_pivot
                vel = controller.linear_velocity
                speed = math.hypot(vel.x, vel.y)
                is_sprinting = controller.is_sprinting

        anim_names = self.actor.getAnimNames()

        if speed >= 0.1:
            # Moving: prioritize Run (if sprinting) -> Walk -> Run -> maintain Idle
            target_anim: str | None = None
            if is_sprinting and "Run" in anim_names:
                target_anim = "Run"
            elif "Walk" in anim_names:
                target_anim = "Walk"
            elif "Run" in anim_names:
                target_anim = "Run"
            elif "Idle" in anim_names:
                target_anim = "Idle"

            if target_anim is not None:
                curr_playback = self.actor.getCurrentAnim() if hasattr(self.actor, "getCurrentAnim") else None
                if self._current_anim != target_anim or curr_playback != target_anim:
                    self.actor.loop(target_anim)
                    self._current_anim = target_anim
        else:
            # Stopped (speed < 0.1): ensure Idle is playing
            if "Idle" in anim_names:
                curr_playback = self.actor.getCurrentAnim() if hasattr(self.actor, "getCurrentAnim") else None
                if self._current_anim != "Idle" or curr_playback != "Idle":
                    self.actor.loop("Idle")
                    self._current_anim = "Idle"

    def play_animation(self, anim_name: str, loop: bool = True) -> bool:
        """Explicitly play or loop an animation clip by name."""
        if self.actor is None or not hasattr(self.actor, "getAnimNames"):
            return False
        if anim_name not in self.actor.getAnimNames():
            return False
        if loop:
            self.actor.loop(anim_name)
        else:
            self.actor.play(anim_name)
        self._current_anim = anim_name
        return True

    def stop_animation(self) -> None:
        """Explicitly stop any active animation playback."""
        if self.actor is not None and hasattr(self.actor, "stop"):
            self.actor.stop()
        self._current_anim = None

    def on_stop(self) -> None:
        """Clean teardown on scene or entity stop."""
        self._cleanup_nodes()
        super().on_stop()

    def on_detach(self) -> None:
        """Clean teardown on handler detach."""
        self._cleanup_nodes()
        super().on_detach()
