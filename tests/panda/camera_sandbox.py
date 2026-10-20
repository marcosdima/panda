"""Interactive First-Person / Third-Person camera sandbox.

Provides a physical test course to evaluate camera handlers in isolation:
- Static ground plane with a colored reference corridor (pillars, blocks, wall)
- A near wall to demonstrate that first-person mode has no spring-arm clipping
  while third-person mode keeps a collision-aware orbiting camera
- Player entity driven by WASDInputHandler and CharacterControllerHandler
- Live toggle between FirstPersonCameraHandler and ThirdPersonCameraHandler (V)
- Telemetry OSD / terminal output and F12 Bullet wireframe toggling
- Clean teardown with zero dangling physics bodies or node leaks
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from panda3d.core import Vec3

from ..__test import Test
from src.entities.entity import Entity
from src.handlers.camera import FirstPersonCameraHandler, ThirdPersonCameraHandler
from src.handlers.input.wasd import WASDInputHandler
from src.handlers.physics.character import CharacterControllerHandler

from src.globals.clock import GlobalClock
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics
from src.globals.tasks import Tasks

if TYPE_CHECKING:
    from panda3d.core import NodePath
    from direct.gui.OnscreenText import OnscreenText


class TestFirstPersonCameraSandbox(Test):
    """Interactive visual sandbox for comparing first-person and third-person cameras."""

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        # Entities and handlers
        self.player: Entity | None = None
        self.controller: CharacterControllerHandler | None = None
        self.input_handler: WASDInputHandler | None = None
        self.fp_handler: FirstPersonCameraHandler | None = None
        self.tp_handler: ThirdPersonCameraHandler | None = None
        self.first_person_active: bool = True

        # Environment tracking for clean teardown
        self.static_bodies: list[str] = []
        self.static_nodes: list[NodePath] = []

        # UI & Telemetry
        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._last_console_telemetry_time: float = 0.0
        self._console_interval: float = 1.0

        self._task_name: str = "camera_fp_sandbox_update_task"

    def on_start(self) -> None:
        """Initialize environment, player entity, camera handlers, controls, and telemetry."""
        self.print_title("First-Person Camera Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()
        self._build_environment()
        self._spawn_player()

        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)
            self.base.accept("v", self._toggle_camera_mode)

        self._setup_osd()
        Tasks.add_task(self._task_name, self._on_frame_update)

    def _print_controls_banner(self) -> None:
        """Print formatted ANSI startup banner with control instructions."""
        self.print_subtitle("Interactive Controls & Mechanics", color="yellow")
        self.p(" Controls:      WASD: Move | SPACE: Jump | LSHIFT: Sprint | Mouse: Look | V: Toggle Camera | Tab/Esc: Cursor | F12: Wireframe", color="cyan", bold=True)
        self.p(" Movement:      [W, A, S, D] or Arrow Keys", color="green", bold=True)
        self.p(" Jump:          [Spacebar] (only while grounded)", color="green", bold=True)
        self.p(" Sprint:        [Left Shift] (12.0 m/s vs 6.0 m/s walk)", color="green", bold=True)
        self.p(" Camera:        [V] Toggle First-Person / Third-Person", color="green", bold=True)
        self.p(" Look / Cursor: [Mouse] Direct Look | [Tab] Toggle Lock | [Esc] Unlock | [LMB] Lock", color="green", bold=True)
        self.p(" Wireframe:     [F12] Toggle Bullet debug visualization", color="magenta", bold=True)

        self.space_line()
        self.p("Test Course Layout:", color="cyan", bold=True)
        self.p(" - Colored pillars at increasing distance: eye-lock & orientation check", color="cyan")
        self.p(" - Near wall ahead: third-person spring-arm clips around it, first-person walks through", color="cyan")
        self.p(" - Raised blocks: pitch look down/up reference", color="cyan")
        self.space_line()

    def _create_static_box(
        self,
        name: str,
        pos: tuple[float, float, float] | Vec3,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 1.0),
        hpr: tuple[float, float, float] | Vec3 = (0.0, 0.0, 0.0),
    ) -> NodePath:
        """Create a static Bullet box body with aligned visual box geometry."""
        from panda3d.bullet import BulletBoxShape

        body = Physics.create_body(name, mass=0.0)
        shape = BulletBoxShape(Vec3(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0))
        body.addShape(shape)

        body_np = self.base.render.attachNewNode(body)
        body_np.setPos(*pos)
        body_np.setHpr(*hpr)

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
        """Build the reference corridor: ground, pillars, raised blocks, and a near wall."""
        self._create_static_box(
            name="ground",
            pos=(0.0, 0.0, -0.25),
            size=(60.0, 60.0, 0.5),
            color=(0.24, 0.27, 0.30, 1.0),
        )

        pillar_colors = [
            (0.85, 0.30, 0.30, 1.0),
            (0.30, 0.80, 0.35, 1.0),
            (0.30, 0.50, 0.90, 1.0),
            (0.90, 0.75, 0.20, 1.0),
            (0.75, 0.35, 0.80, 1.0),
        ]
        for i, color in enumerate(pillar_colors):
            self._create_static_box(
                name=f"pillar_{i + 1}",
                pos=(2.0 - i * 1.0, 8.0 + i * 6.0, 1.5),
                size=(0.8, 0.8, 3.0),
                color=color,
            )

        self._create_static_box(
            name="step_low",
            pos=(-4.0, 6.0, 0.25),
            size=(3.0, 3.0, 0.5),
            color=(0.55, 0.60, 0.65, 1.0),
        )
        self._create_static_box(
            name="step_high",
            pos=(-4.0, 10.0, 0.75),
            size=(3.0, 3.0, 1.5),
            color=(0.65, 0.70, 0.75, 1.0),
        )

        self._create_static_box(
            name="near_wall",
            pos=(0.0, 20.0, 2.0),
            size=(16.0, 0.5, 4.0),
            color=(0.40, 0.35, 0.55, 1.0),
        )

    def _spawn_player(self) -> None:
        """Spawn the player entity with WASD input, controller, and both camera handlers."""
        player = Entity("PlayerCameraHero")
        player.node.reparentTo(self.base.render)
        player.node.setPos(0.0, 0.0, 2.0)

        self.input_handler = WASDInputHandler()
        self.controller = CharacterControllerHandler(
            radius=0.5,
            height=1.0,
            step_height=0.4,
            walk_speed=6.0,
            sprint_speed=12.0,
            acceleration=25.0,
            deceleration=30.0,
        )
        self.fp_handler = FirstPersonCameraHandler(
            eye_offset=Vec3(0.0, 0.0, 1.2),
            pitch=0.0,
            min_pitch=-89.0,
            max_pitch=89.0,
            mouse_sensitivity=0.2,
        )
        self.tp_handler = ThirdPersonCameraHandler(
            distance=8.0,
            target_offset=Vec3(0.0, 0.0, 1.2),
            pitch=-15.0,
            smooth_speed=10.0,
            mouse_sensitivity=0.2,
        )

        player.add_handler(self.input_handler)
        player.add_handler(self.fp_handler)
        player.add_handler(self.controller)

        self.player = player
        self.first_person_active = True
        self.add_entity(player)

    def _activate_camera_mode(self, first_person: bool) -> None:
        """Swap the active camera handler, keeping look angles and pointer capture in sync."""
        if self.player is None or self.fp_handler is None or self.tp_handler is None:
            return

        if first_person:
            if self.player.get_handler(ThirdPersonCameraHandler) is self.tp_handler:
                self.player.remove_handler(self.tp_handler)
            if self.player.get_handler(FirstPersonCameraHandler) is None:
                self.fp_handler.yaw = self.tp_handler.get_camera_yaw() % 360.0
                self.fp_handler.pitch = max(self.fp_handler.min_pitch, min(self.fp_handler.max_pitch, self.tp_handler.pitch))
                self.player.add_handler(self.fp_handler)
            self.fp_handler.set_pointer_captured(self.tp_handler.is_pointer_captured)
        else:
            if self.player.get_handler(FirstPersonCameraHandler) is self.fp_handler:
                self.player.remove_handler(self.fp_handler)
            if self.player.get_handler(ThirdPersonCameraHandler) is None:
                self.tp_handler.yaw = self.fp_handler.yaw
                self.player.add_handler(self.tp_handler)
            self.tp_handler.set_pointer_captured(self.fp_handler.is_pointer_captured)

        self.first_person_active = first_person

    def _toggle_camera_mode(self) -> None:
        """Toggle between first-person and third-person camera handlers (bound to V)."""
        self._activate_camera_mode(not self.first_person_active)
        mode = "FIRST-PERSON" if self.first_person_active else "THIRD-PERSON"
        self.p(f"[Camera Mode] {mode}", color="cyan", bold=True)

    def _setup_osd(self) -> None:
        """Create on-screen text overlays for controls reminder and live telemetry."""
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="WASD: Move | SPACE: Jump | LSHIFT: Sprint | Mouse: Look | V: Toggle Camera | Tab/Esc: Cursor | F12: Wireframe",
                pos=(-1.28, 0.92),
                scale=0.045,
                fg=(1.0, 1.0, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=False,
            )

            self.osd_telemetry = OnscreenText(
                text="Initializing Telemetry...",
                pos=(-1.28, 0.84),
                scale=0.042,
                fg=(0.2, 0.9, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except Exception:
            self.p("OSD not available in this environment; skipping telemetry overlay.", color="yellow")
            self.osd_instructions = None
            self.osd_telemetry = None

    def _toggle_physics_debug(self) -> None:
        """Toggle Bullet physics debug wireframe and notify via console."""
        active = Physics.toggle_debug()
        state = "ENABLED" if active else "DISABLED"
        self.p(f"[Physics Debug] Bullet Wireframe {state}", color="cyan", bold=True)

    def _on_frame_update(self, task: Any) -> int:
        """Per-frame update driving scene entities and telemetry."""
        dt = GlobalClock.get_dt() if hasattr(GlobalClock, "get_dt") else 0.016
        self.on_update(dt)
        self._update_telemetry(task.time)
        return task.cont

    def _update_telemetry(self, current_time: float) -> None:
        """Update live telemetry display on OSD and periodic console logs."""
        if self.controller is None or self.controller.controller_np is None:
            return

        world_pos = self.controller.controller_np.getPos(self.base.render)
        is_on_ground = self.controller.is_on_ground
        speed = self.controller.current_speed
        wireframe = "ON" if Physics.is_debug_enabled() else "OFF"
        mode = "FP" if self.first_person_active else "TP"

        if self.first_person_active and self.fp_handler is not None:
            fwd = self.fp_handler.get_forward_vector()
            yaw = self.fp_handler.yaw
            pitch = self.fp_handler.pitch
        elif self.tp_handler is not None:
            fwd = self.tp_handler.get_forward_vector()
            yaw = self.tp_handler.get_camera_yaw()
            pitch = self.tp_handler.pitch
        else:
            fwd = Vec3(0.0, 1.0, 0.0)
            yaw = 0.0
            pitch = 0.0

        if self.osd_telemetry is not None:
            self.osd_telemetry.setText(
                f"Camera: {mode} | Pos: ({world_pos.x:6.2f}, {world_pos.y:6.2f}, {world_pos.z:6.2f}) | "
                f"Speed: {speed:4.1f} m/s | Ground: {str(is_on_ground):5} | Debug: {wireframe}\n"
                f"Yaw: {yaw:6.1f} | Pitch: {pitch:6.1f} | Fwd: ({fwd.x:5.2f}, {fwd.y:5.2f}, {fwd.z:5.2f})"
            )

        if current_time - self._last_console_telemetry_time >= self._console_interval:
            self._last_console_telemetry_time = current_time
            self.p(
                f"[Telemetry] Camera: {mode} | Pos: ({world_pos.x:.2f}, {world_pos.y:.2f}, {world_pos.z:.2f}) | "
                f"Speed: {speed:.1f} m/s | Yaw: {yaw:.1f} | Pitch: {pitch:.1f} | Grounded: {is_on_ground} | "
                f"Wireframe: {wireframe}",
                color="blue",
            )

    def on_stop(self) -> None:
        """Clean teardown: remove tasks, listeners, static bodies, nodes, and free player entity."""
        self.print_subtitle("First-Person Camera Sandbox stopping...")

        Tasks.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            self.base.ignore("f12")
            self.base.ignore("v")

        if self.osd_telemetry is not None:
            self.osd_telemetry.destroy()
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            self.osd_instructions.destroy()
            self.osd_instructions = None

        if self.player is not None:
            self.player.free()
            self.player = None
        self.controller = None
        self.input_handler = None
        self.fp_handler = None
        self.tp_handler = None

        GlobalLights.clear_lights()
        super().on_stop()

        for np in self.static_nodes:
            if np is not None and not np.isEmpty():
                np.removeNode()
        self.static_nodes.clear()

        for body_name in self.static_bodies:
            Physics.remove_body(body_name)
        self.static_bodies.clear()

        self.p("Clean teardown completed: zero dangling physics bodies.", color="green")
        self.print_subtitle("First-Person Camera Sandbox stopped.")


if __name__ == "__main__":
    from src.game import Game

    app = Game()
    sandbox = TestFirstPersonCameraSandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
