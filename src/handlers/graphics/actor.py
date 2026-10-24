from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any
from panda3d.core import NodePath, Vec3, autoBind, AnimControlCollection

from config import ASSETS_PATH
from src.handlers.base import Handler
from src.handlers.physics.character import CharacterControllerHandler
from src.utils.state_machine import StateMachine

if TYPE_CHECKING:
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)

LOCOMOTION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Idle": ("Walk", "Run", "Jump"),
    "Walk": ("Idle", "Run", "Jump"),
    "Run": ("Idle", "Walk", "Jump"),
    "Jump": ("Idle", "Walk", "Run"),
}

# Clip lookup order per locomotion state (first available clip wins).
_STATE_CLIP_FALLBACK: dict[str, tuple[str, ...]] = {
    "Idle": ("Idle",),
    "Walk": ("Walk", "Run", "Idle"),
    "Run": ("Run", "Walk", "Idle"),
    "Jump": ("Jump",),
}


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
        blend_duration: float = 0.18,
        blend_durations: dict[str, float] | None = None,
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
        blend_duration: float
            Duration in seconds for crossfading between animations. Set to 0 to disable blending.
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

        self.blend_duration: float = max(0.0, float(blend_duration))
        self.blend_durations: dict[str, float] = {
            "Idle->Walk": 0.10,
            "Idle->Run": 0.12,
            "Walk->Run": 0.10,
            "Run->Walk": 0.12,
            "Walk->Idle": 0.14,
            "Run->Idle": 0.16,
            "Idle->Jump": 0.07,
            "Walk->Jump": 0.07,
            "Run->Jump": 0.07,
            "Jump->Idle": 0.14,
            "Jump->Walk": 0.12,
            "Jump->Run": 0.12,
        }
        if blend_durations:
            self.blend_durations.update(blend_durations)

        self.visual_pivot: NodePath | None = None
        self.model_root: NodePath | None = None
        self.anim_controls: AnimControlCollection = AnimControlCollection()
        self._current_anim: str | None = None
        self._last_locomotion_state: str | None = None
        self.locomotion = StateMachine("Idle", LOCOMOTION_TRANSITIONS)
        enter_hook = lambda _prev, _new: self._apply_state_clip()
        for state in LOCOMOTION_TRANSITIONS:
            self.locomotion.on_enter(state, enter_hook)

        # Blending state
        self._blend_active: bool = False
        self._blend_time: float = 0.0
        self._blend_duration: float = 0.0
        self._blend_from_name: str | None = None
        self._blend_to_name: str | None = None
        self._blend_from_ctrl = None
        self._blend_to_ctrl = None
        self._part_bundles: list = []

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
            "hpr": Vec3(180.0, 0.0, 0.0),
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
        self._part_bundles = []

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
        self._last_locomotion_state = None
        self._cancel_blend(reset_weights=False)
        self.locomotion.reset("Idle")

    def on_attach(self, entity: Entity) -> None:
        """Attach handler to entity, set up visual pivot and model."""
        super().on_attach(entity)
        self._setup_nodes()

    def on_start(self) -> None:
        """Called when active scene or entity starts. Loops Idle animation if available."""
        super().on_start()
        if self.visual_pivot is None or self.visual_pivot.isEmpty():
            self._setup_nodes()

        self._enable_blending()
        # Start default Idle loop
        anim_names = self.get_anim_names()
        idle = self._clip_for("Idle", anim_names)
        if idle is None and "idle" in anim_names:
            idle = "idle"
        if idle is not None:
            # Try to crossfade from any playing animation if exists
            if self.blend_duration > 0.0 and self._current_anim and self._current_anim != idle:
                self._start_crossfade(idle, duration=min(0.12, self.blend_duration))
            else:
                self._cancel_blend(reset_weights=False)
                ctrl = self.anim_controls.findAnim(idle)
                if ctrl is not None:
                    try:
                        ctrl.loop(True)
                    except Exception:
                        pass
                    self._set_control_weight(ctrl, 1.0)
                    self._current_anim = idle
            self._last_locomotion_state = "Idle"

    def on_update(self, dt: float) -> None:
        """Per-frame update managing animation states based on character movement speed."""
        super().on_update(dt)

        self._update_blend(dt)

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
        if airborne and self._clip_for("Jump", anim_names) is not None:
            desired = "Jump"
        elif speed >= 0.1:
            desired = "Run" if is_sprinting else "Walk"
        else:
            desired = "Idle"
        prev_state = str(self.locomotion.state)
        self.locomotion.transition(desired)
        curr_state = str(self.locomotion.state)
        if curr_state != prev_state:
            self._last_locomotion_state = prev_state
        elif self._last_locomotion_state is None:
            self._last_locomotion_state = prev_state

        # Entering a state plays its clip; reconcile every frame so manual
        # play/loop calls or late-loaded clips fall back to the state's clip.
        if prev_state == "Idle" and curr_state == "Walk" and not self._blend_active:
            target = self._state_clip(curr_state, anim_names)
            if target is not None and (self._current_anim != target or True):
                self._start_crossfade(target, duration=min(0.08, self.blend_durations.get("Idle->Walk", 0.1)))
        else:
            self._apply_state_clip()

    def _state_clip(self, state: str, anim_names: list[str]) -> str | None:
        """Return the clip for a locomotion state following its fallback order."""
        for name in _STATE_CLIP_FALLBACK[state]:
            clip = self._clip_for(name, anim_names)
            if clip is not None:
                return clip
        return None

    def _apply_state_clip(self) -> None:
        """Loop the clip of the current locomotion state if it is not already playing."""
        anim_names = self.get_anim_names()
        if not anim_names:
            return
        curr = str(self.locomotion.state)
        target = self._state_clip(curr, anim_names)
        if target is None:
            return
        if self._blend_active and self._blend_to_name == target:
            return
        if not self._blend_active and self._current_anim == target:
            return
        prev = self._last_locomotion_state or curr
        key = f"{prev}->{curr}"
        dur = self.blend_durations.get(key, self.blend_duration)
        self._start_crossfade(target, duration=dur)

    def _clip_for(self, state: str, anim_names: list[str]) -> str | None:
        """Return the clip configured for a locomotion state if it is loaded, else None."""
        clip = self.state_clips.get(state)
        return clip if clip in anim_names else None

    def _cancel_blend(self, reset_weights: bool = True) -> None:
        if reset_weights:
            try:
                if self._blend_from_ctrl is not None:
                    self._set_control_weight(self._blend_from_ctrl, 0.0)
            except Exception:
                pass
            try:
                if self._blend_to_ctrl is not None:
                    self._set_control_weight(self._blend_to_ctrl, 1.0)
            except Exception:
                pass
        self._blend_active = False
        self._blend_time = 0.0
        self._blend_duration = 0.0
        self._blend_from_name = None
        self._blend_to_name = None
        self._blend_from_ctrl = None
        self._blend_to_ctrl = None

    def _enable_blending(self) -> None:
        if self._part_bundles:
            return
        if self.visual_pivot is None or self.visual_pivot.isEmpty():
            return
        try:
            from panda3d.core import PartBundle
        except Exception:
            PartBundle = None
        bundles = set()
        try:
            for anim_np in self.visual_pivot.findAllMatches("**/+AnimBundleNode"):
                try:
                    bundle = anim_np.node().getBundle()
                    bundles.add(bundle)
                except Exception:
                    continue
        except Exception:
            pass
        try:
            for char_np in self.visual_pivot.findAllMatches("**/+Character"):
                try:
                    char_node = char_np.node()
                    for bi in range(char_node.getNumBundles()):
                        bundles.add(char_node.getBundle(bi))
                except Exception:
                    continue
        except Exception:
            pass
        for bundle in bundles:
            try:
                if hasattr(bundle, "setAnimBlendFlag"):
                    bundle.setAnimBlendFlag(True)
                elif hasattr(bundle, "anim_blend_flag"):
                    bundle.anim_blend_flag = True
            except Exception:
                pass
        self._part_bundles = list(bundles)

    def _set_control_weight(self, ctrl, weight: float) -> None:
        if ctrl is None:
            return
        self._enable_blending()
        weight = max(0.0, min(1.0, float(weight)))
        # Panda3D 1.10: use PartBundle.setControlEffect
        for bundle in self._part_bundles:
            try:
                if hasattr(bundle, "setControlEffect"):
                    bundle.setControlEffect(ctrl, weight)
                    continue
            except Exception:
                pass
            try:
                if hasattr(bundle, "getControlEffect") or hasattr(bundle, "clearControlEffects"):
                    pass
            except Exception:
                pass
        # Fallbacks for other APIs if present
        if hasattr(ctrl, "setControlEffect"):
            try:
                ctrl.setControlEffect(weight)
                return
            except Exception:
                pass
        if hasattr(ctrl, "setBlendAmount"):
            try:
                ctrl.setBlendAmount(weight)
                return
            except Exception:
                pass
        if hasattr(ctrl, "setWeight"):
            try:
                ctrl.setWeight(weight)
                return
            except Exception:
                pass

    def _start_crossfade(self, target_name: str, duration: float | None = None) -> bool:
        if not target_name:
            return False
        if self.anim_controls is None:
            return False

        self._enable_blending()
        dur = self.blend_duration if duration is None else max(0.0, float(duration))
        to_ctrl = self.anim_controls.findAnim(target_name)
        if to_ctrl is None:
            return False

        if dur <= 0.0:
            old_from = self._blend_from_ctrl
            old_to = self._blend_to_ctrl
            self._cancel_blend(reset_weights=False)
            if old_from is not None and old_from != to_ctrl:
                try:
                    self._set_control_weight(old_from, 0.0)
                    old_from.stop()
                except Exception:
                    pass
            if old_to is not None and old_to != to_ctrl:
                try:
                    self._set_control_weight(old_to, 0.0)
                    old_to.stop()
                except Exception:
                    pass
            try:
                to_ctrl.loop(True)
            except Exception:
                try:
                    to_ctrl.play()
                except Exception:
                    pass
            self._set_control_weight(to_ctrl, 1.0)
            self._current_anim = target_name
            return True

        from_ctrl = None
        from_name = self._current_anim
        if self._blend_active and self._blend_to_ctrl is not None:
            from_ctrl = self._blend_to_ctrl
            from_name = self._blend_to_name
        else:
            if from_name:
                from_ctrl = self.anim_controls.findAnim(from_name)
            if from_ctrl is None and self._current_anim:
                from_ctrl = self.anim_controls.findAnim(self._current_anim)
            if from_ctrl is None:
                try:
                    if hasattr(self.anim_controls, "getNumAnims"):
                        for i in range(self.anim_controls.getNumAnims()):
                            c = self.anim_controls.getAnim(i)
                            try:
                                if c is not None and c.isPlaying():
                                    from_ctrl = c
                                    from_name = self.anim_controls.getAnimName(i) or from_name
                                    break
                            except Exception:
                                continue
                except Exception:
                    pass

        if from_ctrl is to_ctrl:
            self._cancel_blend(reset_weights=False)
            try:
                to_ctrl.loop(True)
            except Exception:
                pass
            self._set_control_weight(to_ctrl, 1.0)
            if self._blend_from_ctrl is not None and self._blend_from_ctrl != to_ctrl:
                try:
                    self._set_control_weight(self._blend_from_ctrl, 0.0)
                except Exception:
                    pass
            self._current_anim = target_name
            return True

        # If reversing to the clip we came from, swap
        if self._blend_active and self._blend_to_name == target_name and self._blend_from_name is not None:
            # will be handled by normal flow, but ensure weights consistent
            pass

        # Cancel previous blend cleanly
        if self._blend_active:
            prev_from = self._blend_from_ctrl
            prev_to = self._blend_to_ctrl
            self._blend_active = False
            if prev_from is not None and prev_from != from_ctrl and prev_from != to_ctrl:
                try:
                    self._set_control_weight(prev_from, 0.0)
                    prev_from.stop()
                except Exception:
                    pass

        try:
            to_ctrl.loop(True)
        except Exception:
            try:
                to_ctrl.play()
            except Exception:
                pass

        self._blend_from_ctrl = from_ctrl
        self._blend_to_ctrl = to_ctrl
        self._blend_from_name = from_name
        self._blend_to_name = target_name
        self._blend_duration = dur
        self._blend_time = 0.0
        self._blend_active = True
        self._current_anim = target_name

        if from_ctrl is not None and from_ctrl != to_ctrl:
            try:
                self._set_control_weight(from_ctrl, 1.0)
            except Exception:
                pass
            try:
                self._set_control_weight(to_ctrl, 0.0)
            except Exception:
                pass
            return True
        else:
            # No known source to blend from; fade in new and fade out others
            try:
                self._set_control_weight(to_ctrl, 0.0)
            except Exception:
                pass
            if hasattr(self.anim_controls, "getNumAnims"):
                try:
                    for i in range(self.anim_controls.getNumAnims()):
                        c = self.anim_controls.getAnim(i)
                        if c is to_ctrl:
                            continue
                        try:
                            self._set_control_weight(c, 1.0)
                        except Exception:
                            pass
                except Exception:
                    pass
            return True

    def _update_blend(self, dt: float) -> None:
        if not self._blend_active:
            return
        self._blend_time += float(dt)
        if self._blend_duration <= 0.0:
            t = 1.0
        else:
            t = self._blend_time / self._blend_duration
        if t >= 1.0:
            t = 1.0

        # Interpolate weights
        w_to = t
        w_from = 1.0 - t
        self._set_control_weight(self._blend_from_ctrl, w_from)
        self._set_control_weight(self._blend_to_ctrl, w_to)

        if t >= 1.0:
            # Finish blend: stop from clip, keep to clip looping
            if self._blend_from_ctrl is not None and self._blend_from_ctrl != self._blend_to_ctrl:
                try:
                    self._blend_from_ctrl.stop()
                except Exception:
                    pass
                self._set_control_weight(self._blend_from_ctrl, 0.0)
            if self._blend_to_ctrl is not None:
                try:
                    self._blend_to_ctrl.loop(True)
                except Exception:
                    pass
                self._set_control_weight(self._blend_to_ctrl, 1.0)
            self._current_anim = self._blend_to_name
            self._cancel_blend()

    def play_animation(self, anim_name: str) -> bool:
        """Explicitly play an animation clip once by name."""
        self._enable_blending()
        old_from = self._blend_from_ctrl
        old_to = self._blend_to_ctrl
        self._cancel_blend(reset_weights=False)
        ctrl = self.anim_controls.findAnim(anim_name)
        if ctrl is not None:
            if old_from is not None and old_from != ctrl:
                try:
                    self._set_control_weight(old_from, 0.0)
                    old_from.stop()
                except Exception:
                    pass
            if old_to is not None and old_to != ctrl:
                try:
                    self._set_control_weight(old_to, 0.0)
                    old_to.stop()
                except Exception:
                    pass
            try:
                ctrl.play()
            except Exception:
                try:
                    ctrl.loop(False)
                except Exception:
                    pass
            self._current_anim = anim_name
            try:
                self._set_control_weight(ctrl, 1.0)
            except Exception:
                pass
            return True
        return False

    def loop_animation(self, anim_name: str) -> bool:
        """Loop an animation clip continuously by name."""
        self._enable_blending()
        old_from = self._blend_from_ctrl
        old_to = self._blend_to_ctrl
        self._cancel_blend(reset_weights=False)
        ctrl = self.anim_controls.findAnim(anim_name)
        if ctrl is not None:
            if old_from is not None and old_from != ctrl:
                try:
                    self._set_control_weight(old_from, 0.0)
                    old_from.stop()
                except Exception:
                    pass
            if old_to is not None and old_to != ctrl:
                try:
                    self._set_control_weight(old_to, 0.0)
                    old_to.stop()
                except Exception:
                    pass
            try:
                ctrl.loop(True)
            except Exception:
                try:
                    ctrl.play()
                except Exception:
                    pass
            self._current_anim = anim_name
            try:
                self._set_control_weight(ctrl, 1.0)
            except Exception:
                pass
            return True
        return False

    def stop_animation(self) -> None:
        """Explicitly stop any active animation playback."""
        old_from = self._blend_from_ctrl
        old_to = self._blend_to_ctrl
        self._cancel_blend(reset_weights=False)
        for c in [old_from, old_to]:
            if c is not None:
                try:
                    self._set_control_weight(c, 0.0)
                    c.stop()
                except Exception:
                    pass
        if self.anim_controls is not None and hasattr(self.anim_controls, "stopAll"):
            try:
                self.anim_controls.stopAll()
            except Exception:
                pass
        self._current_anim = None

    def on_stop(self) -> None:
        """Clean teardown on scene or entity stop."""
        self._cleanup_nodes()
        super().on_stop()

    def on_detach(self) -> None:
        """Clean teardown on handler detach."""
        self._cleanup_nodes()
        super().on_detach()
