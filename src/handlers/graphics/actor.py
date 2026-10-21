from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any
from panda3d.core import NodePath, Vec3, autoBind, AnimControlCollection

from config import ASSETS_PATH
from src.handlers.base import Handler
from src.handlers.physics.character import CharacterControllerHandler

if TYPE_CHECKING:
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)


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
        animation_files: list[str] | None = None,
        state_clips: dict[str, str] | None = None,
        air_threshold: float = 0.12,
    ) -> None:
        """Create an ActorAnimationHandler.

        Parameters
        ----------
        animations: dict[str, str] | None
            Single-clip files, ``{clip_name: relative_path}``; the clip is renamed to ``clip_name``.
        animation_files: list[str] | None
            Multi-clip files (e.g. KayKit ``Rig_Medium_MovementBasic.glb``). Every clip keeps
            the name stored in the file; only the animation data is used (embedded meshes and
            skeletons are discarded) and clips already loaded are skipped.
        state_clips: dict[str, str] | None
            Maps the locomotion states ``Idle``, ``Walk``, ``Run`` and ``Jump`` (airborne) to the
            clip names to play. States default to a clip with the same name as the state.
        air_threshold: float
            Seconds the controller must be off the ground before the ``Jump`` clip is used.
        """
        super().__init__()
        self.model_path: str = model_path
        self.animations: dict[str, str] = (
            animations if animations is not None else {"Idle": "anims/X Bot@Idle.glb"}
        )
        self.scale: float = float(scale)
        self.offset: Vec3 = Vec3(offset)
        self.hpr: Vec3 = Vec3(hpr)

        self.animation_files: list[str] = list(animation_files) if animation_files else []
        self.state_clips: dict[str, str] = {"Idle": "Idle", "Walk": "Walk", "Run": "Run", "Jump": "Jump"}
        if state_clips:
            self.state_clips.update(state_clips)
        self.air_threshold: float = float(air_threshold)
        self._air_time: float = 0.0
        self._loaded_clips: set[str] = set()

        self.visual_pivot: NodePath | None = None
        self.model_root: NodePath | None = None
        self.anim_controls: AnimControlCollection = AnimControlCollection()
        self._current_anim: str | None = None

    @classmethod
    def kaykit_rig_medium(cls, character: str = "Knight", **kwargs: Any) -> ActorAnimationHandler:
        """Build a handler for a KayKit Adventurers character that uses the shared ``Rig_Medium`` clips.

        ``character`` is any model in ``Characters/gltf`` (Knight, Barbarian, Mage, Ranger, Rogue,
        Rogue_Hooded). Extra keyword arguments override the handler parameters.
        """
        pack = "KayKit_Adventurers_2.0_FREE/"
        options: dict[str, Any] = {
            "model_path": f"{pack}Characters/gltf/{character}.glb",
            "animations": {},
            "animation_files": [
                f"{pack}Animations/gltf/Rig_Medium/Rig_Medium_MovementBasic.glb",
                f"{pack}Animations/gltf/Rig_Medium/Rig_Medium_General.glb",
            ],
            "state_clips": {"Idle": "Idle_A", "Walk": "Walking_A", "Run": "Running_A", "Jump": "Jump_Idle"},
            "scale": 1.0,
            "offset": Vec3(0.0, 0.0, -1.0),
        }
        options.update(kwargs)
        return cls(**options)

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
            self._loaded_clips = set()
            if loader is not None and (self.animations or self.animation_files):
                # Sort character skeleton joints alphabetically so autoBind matches bone channels
                # cleanly even when glTF exporters write joint children in divergent orders.
                for char_np in self.model_root.findAllMatches("**/+Character"):
                    char_node = char_np.node()
                    for bi in range(char_node.getNumBundles()):
                        char_node.getBundle(bi).sortDescendants()

                for anim_name, anim_rel_path in self.animations.items():
                    self._load_anim_file(loader, anim_rel_path, rename=anim_name, keep_model=True)
                for anim_rel_path in self.animation_files:
                    self._load_anim_file(loader, anim_rel_path)

                autoBind(self.visual_pivot.node(), self.anim_controls, ~0)

        # Bind controller.visual_node to visual_pivot for drift-free rotation
        if controller is not None:
            controller.visual_node = self.visual_pivot

    def _load_anim_file(
        self,
        loader: Any,
        rel_path: str,
        rename: str | None = None,
        keep_model: bool = False,
    ) -> None:
        """Load an animation file under the visual pivot.

        By default only the animation bundles are kept: embedded meshes/skeletons are
        discarded so ``autoBind`` binds each clip exactly once to the character model, and
        clips whose name was already loaded are skipped. With ``keep_model`` the whole file
        is attached instead (legacy single-clip behavior).
        """
        if self.visual_pivot is None or self.visual_pivot.isEmpty():
            return
        full_path = (
            ASSETS_PATH + rel_path
            if not rel_path.startswith("/") and not rel_path.startswith(ASSETS_PATH)
            else rel_path
        )
        try:
            anim_model = loader.loadModel(full_path)
        except (IOError, OSError):
            logger.warning("Failed to load animation file %s.", full_path, exc_info=True)
            return

        if keep_model:
            for anim_node in anim_model.findAllMatches("**/+AnimBundleNode"):
                bundle = anim_node.node().getBundle()
                bundle.sortDescendants()
                if rename is not None:
                    bundle.setName(rename)
            self._loaded_clips.add(rename or rel_path)
            anim_model.reparentTo(self.visual_pivot)
            return

        for anim_node in anim_model.findAllMatches("**/+AnimBundleNode"):
            bundle = anim_node.node().getBundle()
            bundle.sortDescendants()
            if rename is not None:
                bundle.setName(rename)
            if bundle.getName() in self._loaded_clips:
                continue
            self._loaded_clips.add(bundle.getName())
            anim_node.reparentTo(self.visual_pivot)
        anim_model.removeNode()

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
        self._air_time = 0.0

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
        idle = self._clip_for("Idle", anim_names)
        if idle is None and "idle" in anim_names:
            idle = "idle"
        if idle is not None:
            self.loop_animation(idle)

    def on_update(self, dt: float) -> None:
        """Per-frame update managing animation states based on character movement speed."""
        super().on_update(dt)

        # Check movement speed from CharacterControllerHandler
        speed = 0.0
        is_sprinting = False
        airborne = False
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
                if controller.controller_node is not None and not controller.is_on_ground:
                    self._air_time += dt
                    airborne = self._air_time >= self.air_threshold
                else:
                    self._air_time = 0.0
                    airborne = False

        anim_names = self.get_anim_names()
        if not anim_names:
            return

        target_anim: str | None = None
        jump = self._clip_for("Jump", anim_names)
        idle = self._clip_for("Idle", anim_names)
        walk = self._clip_for("Walk", anim_names)
        run = self._clip_for("Run", anim_names)

        if airborne and jump is not None:
            target_anim = jump
        elif speed >= 0.1:
            # Moving: prioritize Run (if sprinting) -> Walk -> Run -> maintain Idle
            if is_sprinting and run is not None:
                target_anim = run
            elif walk is not None:
                target_anim = walk
            elif run is not None:
                target_anim = run
            else:
                target_anim = idle
        else:
            # Stopped (speed < 0.1): ensure Idle is playing
            target_anim = idle

        if target_anim is not None and self._current_anim != target_anim:
            self.loop_animation(target_anim)

    def _clip_for(self, state: str, anim_names: list[str]) -> str | None:
        """Return the clip configured for a locomotion state if it is loaded, else None."""
        clip = self.state_clips.get(state)
        return clip if clip in anim_names else None

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
