from __future__ import annotations

import math
from typing import TYPE_CHECKING
from panda3d.core import NodePath, Vec3, autoBind, AnimControlCollection

from config import ASSETS_PATH
from src.handlers.base import Handler
from src.handlers.physics.character import CharacterControllerHandler

if TYPE_CHECKING:
    from src.entities.entity import Entity


class ActorAnimationHandler(Handler):
    """Modular graphics handler managing animated 3D character models (glTF/Actor).

    Preserves the complete character hierarchy (joints, armor plates, armature) and
    creates a dedicated visual pivot at (0, 0, 0) attached to CharacterControllerHandler's
    controller NodePath to eliminate rotational drift. Synchronizes animation playback
    with character movement states.
    """

    def __init__(
        self,
        model_path: str = "X Bot.glb",
        animations: dict[str, str] | None = None,
        scale: float = 100.0,
        offset: Vec3 = Vec3(0.0, 0.0, -1.0),
        hpr: Vec3 = Vec3(0.0, 0.0, 0.0),
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
        self.model_root: NodePath | None = None
        self.anim_controls: AnimControlCollection = AnimControlCollection()
        self._current_anim: str | None = None

    @property
    def current_animation(self) -> str | None:
        """Return the name of the currently active animation clip, or None."""
        return self._current_anim

    def get_anim_names(self) -> list[str]:
        """Return the list of available animation names."""
        names: list[str] = []
        if self.anim_controls is not None and hasattr(self.anim_controls, "getNumAnims"):
            for i in range(self.anim_controls.getNumAnims()):
                name = self.anim_controls.getAnimName(i)
                if name and name not in names:
                    names.append(name)
        return names

    def _setup_nodes(self) -> None:
        """Initialize the visual pivot at (0, 0, 0) and load the 3D model with animation binding."""
        if self.entity is None:
            return

        import builtins
        import gltf  # noqa: F401

        base = getattr(builtins, "base", None)
        loader = getattr(base, "loader", None) if base is not None else None

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

        # Load 3D model and bind animations cleanly via autoBind
        if self.model_root is None or self.model_root.isEmpty():
            full_model_path = (
                ASSETS_PATH + self.model_path
                if not self.model_path.startswith("/") and not self.model_path.startswith(ASSETS_PATH)
                else self.model_path
            )

            if loader is not None:
                self.model_root = loader.loadModel(full_model_path)
            else:
                self.model_root = NodePath("ModelFallback")

            self.model_root.reparentTo(self.visual_pivot)
            self.model_root.setScale(self.scale)
            self.model_root.setPos(self.offset)
            self.model_root.setHpr(self.hpr)

            # Load animation bundles and bind to model
            self.anim_controls = AnimControlCollection()
            if loader is not None and self.animations:
                for anim_name, anim_rel_path in self.animations.items():
                    full_anim_path = (
                        ASSETS_PATH + anim_rel_path
                        if not anim_rel_path.startswith("/") and not anim_rel_path.startswith(ASSETS_PATH)
                        else anim_rel_path
                    )
                    try:
                        anim_model = loader.loadModel(full_anim_path)
                        for anim_node in anim_model.findAllMatches("**/+AnimBundleNode"):
                            anim_node.node().getBundle().setName(anim_name)
                        anim_model.reparentTo(self.visual_pivot)
                    except Exception:
                        pass

                autoBind(self.visual_pivot.node(), self.anim_controls, ~0)

        # Bind controller.visual_node to visual_pivot for drift-free rotation
        if controller is not None:
            controller.visual_node = self.visual_pivot

    def _cleanup_nodes(self) -> None:
        """Stop animation and remove visual nodes cleanly."""
        self.stop_animation()
        self.anim_controls = AnimControlCollection()

        if self.model_root is not None and not self.model_root.isEmpty():
            self.model_root.removeNode()
            self.model_root = None

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

        self._current_anim = None

    def on_attach(self, entity: Entity) -> None:
        """Attach handler to entity, set up visual pivot and model."""
        super().on_attach(entity)
        self._setup_nodes()

    def on_start(self) -> None:
        """Called when active scene or entity starts. Loops Idle animation if available."""
        super().on_start()
        if self.visual_pivot is None or self.visual_pivot.isEmpty():
            self._setup_nodes()

        # Start default Idle loop
        anim_names = self.get_anim_names()
        if "Idle" in anim_names or "idle" in anim_names:
            target = "Idle" if "Idle" in anim_names else "idle"
            self.loop_animation(target)

    def on_update(self, dt: float) -> None:
        """Per-frame update managing animation states based on character movement speed."""
        super().on_update(dt)

        # Check movement speed from CharacterControllerHandler
        speed = 0.0
        is_sprinting = False
        if self.entity is not None:
            controller = self.entity.get_handler(CharacterControllerHandler)
            if controller is not None:
                if (
                    controller.visual_node != self.visual_pivot
                    and self.visual_pivot is not None
                    and not self.visual_pivot.isEmpty()
                ):
                    controller.visual_node = self.visual_pivot
                vel = controller.linear_velocity
                speed = math.hypot(vel.x, vel.y)
                is_sprinting = controller.is_sprinting

        anim_names = self.get_anim_names()
        if not anim_names:
            return

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

            if target_anim is not None and self._current_anim != target_anim:
                self.loop_animation(target_anim)
        else:
            # Stopped (speed < 0.1): ensure Idle is playing
            if "Idle" in anim_names and self._current_anim != "Idle":
                self.loop_animation("Idle")

    def play_animation(self, anim_name: str) -> bool:
        """Explicitly play an animation clip once by name."""
        ctrl = self.anim_controls.findAnim(anim_name)
        if ctrl is not None:
            ctrl.play()
            self._current_anim = anim_name
            return True
        return False

    def loop_animation(self, anim_name: str) -> bool:
        """Loop an animation clip continuously by name."""
        ctrl = self.anim_controls.findAnim(anim_name)
        if ctrl is not None:
            ctrl.loop(True)
            self._current_anim = anim_name
            return True
        return False

    def stop_animation(self) -> None:
        """Explicitly stop any active animation playback."""
        if self.anim_controls is not None and hasattr(self.anim_controls, "stopAll"):
            self.anim_controls.stopAll()
        self._current_anim = None

    def on_stop(self) -> None:
        """Clean teardown on scene or entity stop."""
        self._cleanup_nodes()
        super().on_stop()

    def on_detach(self) -> None:
        """Clean teardown on handler detach."""
        self._cleanup_nodes()
        super().on_detach()
