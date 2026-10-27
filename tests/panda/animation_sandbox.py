"""Interactive Animation State sandbox.

Demonstrates velocity-driven locomotion state transitions (Idle -> Walk -> Run)
in isolation: the entity is built with only an input, a character controller, an
animation handler and a camera, with no player driving. A scripted ramp writes
the movement vector and sprint flag so the states cycle deterministically.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec3

from ..__test import Test
from src.globals.lights import GlobalLights
from src.globals.clock import GlobalClock
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics
from src.handlers.input import InputHandler
from src.handlers.input.action_map import JUMP, SPRINT
from src.handlers.graphics import ActorAnimationHandler
from src.handlers.physics.character import CharacterControllerHandler
from src.prefabs.builder import EntityBuilder

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)


class _PhaseState:
    """Single step of the scripted locomotion sequence."""

    __slots__ = ("name", "move", "sprint", "duration")

    def __init__(self, name: str, move: float, sprint: bool, duration: float) -> None:
        self.name: str = name
        self.move: float = move
        self.sprint: bool = sprint
        self.duration: float = duration


class TestAnimationSandbox(Test):
    """Visual sandbox to evaluate velocity-driven locomotion state transitions."""

    _SEQUENCE: list[_PhaseState] = [
        _PhaseState("Idle", 0.0, False, 2.0),
        _PhaseState("Walk", 1.0, False, 3.0),
        _PhaseState("Run", 1.0, True, 3.0),
        _PhaseState("Walk", 1.0, False, 2.0),
        _PhaseState("Idle", 0.0, False, 2.0),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        self.animation: ActorAnimationHandler | None = None
        self.input_h: InputHandler | None = None
        self._controller: CharacterControllerHandler | None = None
        self._entity: Entity | None = None

        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None

        self.static_bodies: list[str] = []
        self.static_nodes: list[NodePath] = []

        self._task_name: str = "animation_sandbox_update_task"
        self._auto: bool = True
        self._phase_index: int = 0
        self._phase_time: float = 0.0
        self._jump_requested: int | None = None

    def on_start(self) -> None:
        self.print_title("Animation State Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()

        if self.base is None or getattr(self.base, "render", None) is None:
            self.p("No graphics context available; animation sandbox needs a window.", color="yellow")
            return

        self._build_environment()
        self._spawn_rig()

        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)
            self.base.accept("a", self._toggle_auto)
            self.base.accept("j", self._request_jump)

        self._setup_osd()
        self._setup_inspector()
        # Sort below Game.UPDATE_TASK_SORT so the scripted intent is written
        # before the scene entities consume it in the same frame.
        self.add_task(self._task_name, self._on_frame_update, sort=-6)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_inspector(self) -> None:
        """Expose blend durations and sequence controls in the pause inspector."""
        self.expose_toggle(
            "Auto Sequence (A)",
            lambda: self._auto,
            lambda _v: self._toggle_auto(),
        )
        self.expose_property(
            "Phase index",
            lambda: float(self._phase_index),
            self._set_phase_index,
            0.0,
            float(len(self._SEQUENCE) - 1),
            1.0,
        )
        if self.animation is not None:
            self.expose_field("air_threshold (s)", self.animation, "air_threshold", 0.02, 1.0, 0.02)
            for key in ("Idle->Walk", "Walk->Run", "Run->Walk", "Walk->Idle"):
                self.expose_property(
                    f"{key} (s)",
                    lambda k=key: self.animation.blend_durations.get(k, 0.0)
                    if self.animation is not None
                    else 0.0,
                    lambda v, k=key: self._set_blend(k, v),
                    0.02,
                    0.60,
                    0.02,
                )

    def _set_phase_index(self, value: float) -> None:
        self._phase_index = int(value) % len(self._SEQUENCE)
        self._phase_time = 0.0

    def _set_blend(self, key: str, value: float) -> None:
        if self.animation is None:
            return
        self.animation.blend_durations[key] = max(0.02, min(0.60, float(value)))

    def _print_controls_banner(self) -> None:
        self.print_subtitle("Controls", color="yellow")
        self.p(" A:     toggle auto sequence", color="green")
        self.p(" J:     request a jump", color="green")
        self.p(" Wireframe: F12", color="magenta")
        self.p(" Pause: P     (toggle)", color="magenta")
        self.space_line()
        self.p("Scripted Idle -> Walk -> Run -> Walk -> Idle cycle", color="cyan", bold=True)
        self.space_line()

    def _create_static_box(
        self,
        name: str,
        pos: tuple[float, float, float] | Vec3,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 1.0),
    ) -> NodePath:
        body = Physics.create_body(name, mass=0.0)
        shape = BulletBoxShape(Vec3(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0))
        body.addShape(shape)

        body_np = self.base.render.attachNewNode(body)
        body_np.setPos(*pos)

        box_model = GlobalLoader.load_panda_asset("box")
        visual_np = body_np.attachNewNode(f"{name}_visual")
        box_model.copyTo(visual_np)
        visual_np.setScale(size[0], size[1], size[2])
        visual_np.setPos(-size[0] / 2.0, -size[1] / 2.0, -size[2] / 2.0)
        visual_np.setColor(*color)

        self.static_bodies.append(name)
        self.static_nodes.append(body_np)
        return body_np

    def _build_environment(self) -> None:
        self._create_static_box(
            name="ground",
            pos=(0.0, 0.0, -0.25),
            size=(60.0, 60.0, 0.5),
            color=(0.24, 0.27, 0.30, 1.0),
        )

    def _spawn_rig(self) -> None:
        parent = None
        if self.base is not None and hasattr(self.base, "render"):
            parent = self.base.render

        builder = EntityBuilder("AnimStateDemo")
        if parent is not None:
            builder.parented_to(parent)
        builder.at(0.0, 0.0, 1.2)
        builder.with_handler(InputHandler())
        builder.with_character(acceleration=8.0, deceleration=8.0)
        builder.with_animation(
            kaykit="Knight",
            blend_duration=0.22,
            blend_easing=True,
        )
        builder.with_camera(
            "third_person",
            distance=8.0,
            target_offset=Vec3(0.0, 0.0, 2.0),
        )
        entity = builder.build(self)
        self._entity = entity
        self.animation = entity.get_handler(ActorAnimationHandler)
        self.input_h = entity.get_handler(InputHandler)
        self._controller = entity.get_handler(CharacterControllerHandler)

    def _setup_osd(self) -> None:
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="A: auto/manual | J: jump | F12 wireframe",
                pos=(-1.3, 0.9),
                scale=0.05,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )
            self.osd_telemetry = OnscreenText(
                text="State: -",
                pos=(-1.3, -0.9),
                scale=0.05,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except Exception:
            self.osd_instructions = None
            self.osd_telemetry = None

    # ------------------------------------------------------------------
    # Keys
    # ------------------------------------------------------------------

    def _toggle_physics_debug(self) -> None:
        try:
            Physics.get_instance().toggle_debug()
        except Exception:
            try:
                if self.base is not None and hasattr(self.base, "toggleBulletDebug"):
                    self.base.toggleBulletDebug()
            except Exception:
                pass

    def _toggle_auto(self) -> None:
        self._auto = not self._auto
        if not self._auto and self.input_h is not None:
            self.input_h.set_move_vector(0.0, 0.0)
            self.input_h.set_action_state(SPRINT, False)
        self.p(f"Auto sequence: {'ON' if self._auto else 'OFF'}", color="yellow")

    def _request_jump(self) -> None:
        self._jump_requested = 0
        if self.input_h is not None:
            # Hold the action down until the controller has observed one press
            # edge across a full scene update, then release it.
            self.input_h.set_action_state(JUMP, True)

    # ------------------------------------------------------------------
    # Frame update
    # ------------------------------------------------------------------

    def _apply_phase(self, phase: _PhaseState) -> None:
        if self.input_h is None:
            return
        self.input_h.set_move_vector(phase.move, 0.0)
        self.input_h.set_action_state(SPRINT, phase.sprint)

    def _on_frame_update(self, task):
        try:
            self._hold_jump()
            if self._auto:
                self._advance_sequence()
                phase = self._SEQUENCE[self._phase_index]
                self._apply_phase(phase)
            elif self.input_h is not None:
                self.input_h.set_action_state(SPRINT, False)
            self._update_osd()
        except Exception:
            logger.exception("Animation sandbox frame update failed.")
        return task.cont

    def _hold_jump(self) -> None:
        """Release the jump action one scene update after it was pressed."""
        if self._jump_requested is None or self.input_h is None:
            return
        self._jump_requested += 1
        if self._jump_requested >= 2:
            self.input_h.set_action_state(JUMP, False)
            self._jump_requested = None

    def _advance_sequence(self) -> None:
        dt = GlobalClock.get_dt() if hasattr(GlobalClock, "get_dt") else 0.016
        self._phase_time += dt
        phase = self._SEQUENCE[self._phase_index]
        if self._phase_time >= phase.duration:
            self._phase_time = 0.0
            self._phase_index = (self._phase_index + 1) % len(self._SEQUENCE)

    def _update_osd(self) -> None:
        if self.animation is None or self.osd_telemetry is None:
            return
        state = str(self.animation.locomotion.state)
        anim = self.animation.current_animation
        speed = 0.0
        if self._controller is not None:
            vel = self._controller.linear_velocity
            speed = math.hypot(vel.x, vel.y)
        blending = getattr(self.animation, "_blend_active", False)
        fw = getattr(self.animation, "_blend_from_name", None)
        tw = getattr(self.animation, "_blend_to_name", None)
        phase_name = self._SEQUENCE[self._phase_index].name if self._auto else "MANUAL"
        self.osd_telemetry.setText(
            f"Phase: {phase_name} | State: {state} | Anim: {anim} | Speed: {speed:.2f} "
            f"| Blending: {blending} ({fw}->{tw})"
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def on_stop(self) -> None:
        self.print_subtitle("Animation State Sandbox stopping...")
        self.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            try:
                self.base.ignore("f12")
                self.base.ignore("a")
                self.base.ignore("j")
                self.base.ignore("p")
            except Exception:
                pass

        if self.osd_telemetry is not None:
            try:
                self.osd_telemetry.destroy()
            except Exception:
                pass
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            try:
                self.osd_instructions.destroy()
            except Exception:
                pass
            self.osd_instructions = None

        for body_name in list(getattr(self, "static_bodies", [])):
            try:
                Physics.remove_body(body_name)
            except Exception:
                pass
        for node in list(getattr(self, "static_nodes", [])):
            try:
                if node is not None and not node.isEmpty():
                    node.removeNode()
            except Exception:
                pass
        self.static_nodes.clear()
        self.static_bodies.clear()

        try:
            GlobalLights.clear_lights()
        except Exception:
            pass

        if self._entity is not None:
            try:
                self._entity.free()
            except Exception:
                try:
                    self.remove_entity(self._entity)
                except Exception:
                    pass
        self._entity = None
        self.animation = None
        self.input_h = None
        self._controller = None

        super().on_stop()


if __name__ == "__main__":
    from src import game

    app = game.Game()
    sandbox = TestAnimationSandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
