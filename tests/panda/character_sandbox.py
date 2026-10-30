"""Interactive 3D Character Controller sandbox.

Provides a physical test course featuring:
- Static ground plane
- Stepped obstacles of varying heights (0.2m, 0.4m, 0.6m) for step climbing evaluation
- Ramps of varying slope angles (15 deg, 30 deg, 45 deg) for slope climbing and sliding evaluation
- Elevated platform accessible via stairs and ramps
- Player character entity driven by WASDInputHandler and CharacterControllerHandler
- Telemetry OSD / terminal output and F12 Bullet wireframe toggling
- Clean teardown with zero dangling physics bodies or node leaks
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.globals.clock import GlobalClock
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics
from src.handlers.camera import (
    ADVENTURE_PRESET,
    ISOMETRIC_PRESET,
    OVERHEAD_PRESET,
    SHOOTER_PRESET,
    ThirdPersonCameraHandler,
)
from src.handlers.graphics import ActorAnimationHandler
from src.handlers.input.wasd import WASDInputHandler
from src.handlers.physics.character import (
    CharacterControllerHandler,
    CharacterOrientationMode,
)

from ..__test import Test

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText


class TestCharacterSandbox(Test):
    """Interactive visual 3D sandbox scene for evaluating character controller mechanics."""

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        # Entities and handlers
        self.player: Entity | None = None
        self.controller: CharacterControllerHandler | None = None
        self.input_handler: WASDInputHandler | None = None
        self.camera_handler: ThirdPersonCameraHandler | None = None
        self.actor_handler: ActorAnimationHandler | None = None

        # Environment tracking for clean teardown
        self.static_bodies: list[str] = []
        self.static_nodes: list[NodePath] = []

        # UI & Telemetry
        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._last_console_telemetry_time: float = 0.0
        self._console_interval: float = 1.0  # seconds between terminal telemetry prints

        self._task_name: str = "character_sandbox_update_task"
        self._preset_index: int = 0
        self.current_preset_name: str = ADVENTURE_PRESET.name

    def on_start(self) -> None:
        """Initialize environment, player entity, camera, controls, and telemetry."""
        self.print_title("Character Controller Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()
        # Build test environment (ground, stairs, ramps, elevated platform)
        self._build_environment()

        # Spawn and configure player entity
        self._spawn_player()

        # Setup key listeners
        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)
            self.base.accept("1", self._set_preset_adventure)
            self.base.accept("2", self._set_preset_shooter)
            self.base.accept("3", self._set_preset_isometric)
            self.base.accept("4", self._set_preset_overhead)
            self.base.accept("c", self._cycle_camera_preset)
            self.base.accept("b", self._toggle_body_orientation)

        # Setup On-Screen Display (OSD)
        self._setup_osd()
        self._setup_inspector()

        # Register per-frame update and telemetry task
        self.add_task(self._task_name, self._on_frame_update)

    def _setup_inspector(self) -> None:
        """Register live-editable sandbox controls for the pause inspector (Esc / P)."""
        if self.controller is not None:
            self.expose_toggle(
                "Body Follows Cam Yaw",
                lambda: self.controller.body_follows_camera_yaw if self.controller else False,
                lambda v: setattr(self.controller, "body_follows_camera_yaw", bool(v)) if self.controller else None,
            )
        self.expose_action("Cycle Camera Preset (C)", self._cycle_camera_preset)
        if self.actor_handler is not None:
            self.expose_action(
                "Action: Interact",
                lambda: self.actor_handler.play_action("Interact") if self.actor_handler else None,
            )

    def _print_controls_banner(self) -> None:
        """Print formatted ANSI startup banner with control instructions."""
        self.print_subtitle("Interactive Controls & Mechanics", color="yellow")
        self.p(
            " Character:     KayKit Knight with animated Idle/Walk/Run/Jump & camera-relative navigation",
            color="cyan",
            bold=True,
        )
        self.p(
            " Controls:      WASD: Move | SPACE: Jump | LSHIFT: Sprint | Mouse: Look | Tab/Esc: Cursor | "
            "Wheel: Zoom | F12: Wireframe",
            color="cyan",
            bold=True,
        )
        self.p(" Movement:      [W, A, S, D] or Arrow Keys", color="green", bold=True)
        self.p(" Jump:          [Spacebar] (only while grounded)", color="green", bold=True)
        self.p(
            " Sprint:        [Left Shift] (12.0 m/s vs 6.0 m/s walk)",
            color="green",
            bold=True,
        )
        self.p(
            " Camera Presets:[1] Adventure/Orbit | [2] Over-Shoulder Shooter | "
            "[3] Isometric | [4] Top-Down | [C] Cycle",
            color="green",
            bold=True,
        )
        self.p(
            " Body Mode:     [B] Toggle Movement-Dir vs Camera-Look orientation",
            color="green",
            bold=True,
        )
        self.p(
            " Look / Cursor: [Mouse] Direct Look | [Tab] Toggle Lock | [Esc] Unlock | [LMB] Lock",
            color="green",
            bold=True,
        )
        self.p(" Zoom:          [Mouse Wheel] Zoom in/out", color="green", bold=True)
        self.p(
            " Wireframe:     [F12] Toggle Bullet debug visualization",
            color="magenta",
            bold=True,
        )

        self.space_line()
        self.p("Test Course Layout:", color="cyan", bold=True)
        self.p(" - Stairs 0.2m: Smooth step climbing test", color="cyan")
        self.p(" - Stairs 0.4m: Controller step height threshold test", color="cyan")
        self.p(" - Stairs 0.6m: Obstacle test (requires jump)", color="cyan")
        self.p(
            " - Ramp 15 deg: Low-incline slope leading to elevated platform",
            color="cyan",
        )
        self.p(" - Ramp 30 deg: Medium-incline slope test", color="cyan")
        self.p(" - Ramp 45 deg: Critical-incline slope / slide test", color="cyan")
        self.p(" - Elevated Platform at Z=2.0m: Accessible via stairs/ramps", color="cyan")
        self.space_line()

    def _create_static_box(
        self,
        name: str,
        pos: tuple[float, float, float] | Vec3,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 1.0),
        hpr: tuple[float, float, float] | Vec3 = (0.0, 0.0, 0.0),
    ) -> NodePath:
        """Create a static Bullet box body with perfectly aligned visual box geometry."""
        body = Physics.create_body(name, mass=0.0)
        shape = BulletBoxShape(Vec3(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0))
        body.addShape(shape)

        body_np = self.base.render.attachNewNode(body)
        body_np.setPos(*pos)
        body_np.setHpr(*hpr)

        # Visual model matching physical box dimensions and centered at node origin
        box_model = GlobalLoader.load_panda_asset("box")
        visual_np = body_np.attachNewNode(f"{name}_visual")
        box_model.copyTo(visual_np)
        visual_np.setScale(size[0], size[1], size[2])
        visual_np.setPos(-size[0] / 2.0, -size[1] / 2.0, -size[2] / 2.0)
        visual_np.setColor(*color)

        self.static_bodies.append(name)
        self.static_nodes.append(body_np)
        return body_np

    def _create_ramp(
        self,
        name: str,
        start_x: float,
        start_y: float,
        start_z: float,
        angle_deg: float,
        length: float,
        width: float,
        thickness: float,
        color: tuple[float, float, float, float],
    ) -> NodePath:
        """Create an angled ramp rising along +Y axis with pitch angle_deg."""
        rad = math.radians(angle_deg)
        center_x = start_x
        center_y = start_y + (length / 2.0) * math.cos(rad)
        center_z = start_z + (length / 2.0) * math.sin(rad)

        return self._create_static_box(
            name=name,
            pos=(center_x, center_y, center_z),
            size=(width, length, thickness),
            color=color,
            hpr=(0.0, angle_deg, 0.0),
        )

    def _build_environment(self) -> None:
        """Build the full testing arena: ground, stairs, ramps, and elevated platform."""
        # 1. Main Static Ground (60m x 60m x 0.5m, surface at Z=0.0)
        self._create_static_box(
            name="ground",
            pos=(0.0, 0.0, -0.25),
            size=(60.0, 60.0, 0.5),
            color=(0.24, 0.27, 0.30, 1.0),
        )

        # 2. Elevated Platform (10m x 8m x 0.4m, top surface at Z=2.0)
        self._create_static_box(
            name="elevated_platform",
            pos=(0.0, 16.0, 1.8),
            size=(10.0, 8.0, 0.4),
            color=(0.38, 0.43, 0.48, 1.0),
        )

        # 3. Ramp 15 deg (leads from Z=0 up to elevated platform at Z=2.0, width=3.0m)
        # Rise = 2.0m, length = 2.0 / sin(15 deg) ~= 7.727m
        ramp15_len = 2.0 / math.sin(math.radians(15.0))
        ramp15_start_y = 12.0 - ramp15_len * math.cos(math.radians(15.0))
        self._create_ramp(
            name="ramp_15_deg",
            start_x=3.0,
            start_y=ramp15_start_y,
            start_z=0.0,
            angle_deg=15.0,
            length=ramp15_len,
            width=3.0,
            thickness=0.3,
            color=(0.20, 0.75, 0.55, 1.0),
        )

        # 4. Stairs 0.4m (Step height threshold test: 5 steps of 0.4m rising to Z=2.0)
        # Positioned along X = -3.0 leading up to elevated platform front edge (Y=12.0)
        step4_depth = (12.0 - ramp15_start_y) / 5.0
        for i in range(5):
            top_z = (i + 1) * 0.4
            center_z = top_z - 0.2
            center_y = ramp15_start_y + (i + 0.5) * step4_depth
            self._create_static_box(
                name=f"stairs_04_step_{i + 1}",
                pos=(-3.0, center_y, center_z),
                size=(3.0, step4_depth, 0.4),
                color=(0.85, 0.70, 0.20, 1.0),
            )

        # 5. Stairs 0.2m (Smooth climbing test: 6 steps of 0.2m rising to Z=1.2)
        # Positioned at X = -8.0, Y starting at 3.0
        for i in range(6):
            top_z = (i + 1) * 0.2
            center_z = top_z - 0.1
            center_y = 3.0 + i * 1.0 + 0.5
            self._create_static_box(
                name=f"stairs_02_step_{i + 1}",
                pos=(-8.0, center_y, center_z),
                size=(3.0, 1.0, 0.2),
                color=(0.25, 0.75, 0.40, 1.0),
            )
        # Landing platform for 0.2m stairs
        self._create_static_box(
            name="stairs_02_landing",
            pos=(-8.0, 10.0, 1.1),
            size=(3.0, 2.0, 0.2),
            color=(0.25, 0.75, 0.40, 1.0),
        )

        # 6. Stairs 0.6m (Obstacle barrier test: 2 steps of 0.6m rising to Z=1.2, requires jump)
        # Positioned at X = -13.0, Y starting at 3.0
        for i in range(2):
            top_z = (i + 1) * 0.6
            center_z = top_z - 0.3
            center_y = 3.0 + i * 1.4 + 0.7
            self._create_static_box(
                name=f"stairs_06_step_{i + 1}",
                pos=(-13.0, center_y, center_z),
                size=(3.0, 1.4, 0.6),
                color=(0.82, 0.28, 0.28, 1.0),
            )
        # Landing platform for 0.6m stairs
        self._create_static_box(
            name="stairs_06_landing",
            pos=(-13.0, 6.8, 1.0),
            size=(3.0, 2.0, 0.4),
            color=(0.82, 0.28, 0.28, 1.0),
        )

        # 7. Ramp 30 deg (Slope climbing evaluation: 8m length, width 3m)
        # Positioned at X = 8.0, Y starting at 3.0
        self._create_ramp(
            name="ramp_30_deg",
            start_x=8.0,
            start_y=3.0,
            start_z=0.0,
            angle_deg=30.0,
            length=8.0,
            width=3.0,
            thickness=0.3,
            color=(0.90, 0.55, 0.15, 1.0),
        )
        # Landing platform at top of 30 deg ramp
        ramp30_rad = math.radians(30.0)
        ramp30_top_y = 3.0 + 8.0 * math.cos(ramp30_rad)
        ramp30_top_z = 8.0 * math.sin(ramp30_rad)
        self._create_static_box(
            name="ramp_30_landing",
            pos=(8.0, ramp30_top_y + 1.25, ramp30_top_z - 0.2),
            size=(3.0, 2.5, 0.4),
            color=(0.90, 0.55, 0.15, 1.0),
        )

        # 8. Ramp 45 deg (Steep slope / sliding threshold test: 8m length, width 3m)
        # Positioned at X = 13.0, Y starting at 3.0
        self._create_ramp(
            name="ramp_45_deg",
            start_x=13.0,
            start_y=3.0,
            start_z=0.0,
            angle_deg=45.0,
            length=8.0,
            width=3.0,
            thickness=0.3,
            color=(0.75, 0.25, 0.75, 1.0),
        )
        ramp45_rad = math.radians(45.0)
        ramp45_top_y = 3.0 + 8.0 * math.cos(ramp45_rad)
        ramp45_top_z = 8.0 * math.sin(ramp45_rad)
        self._create_static_box(
            name="ramp_45_landing",
            pos=(13.0, ramp45_top_y + 1.25, ramp45_top_z - 0.2),
            size=(3.0, 2.5, 0.4),
            color=(0.75, 0.25, 0.75, 1.0),
        )

    def _spawn_player(self) -> None:
        """Spawn the player Entity with WASD input, CharacterController, and visual model."""
        player = Entity("PlayerCharacter")
        player.node.reparentTo(self.base.render)
        player.node.setPos(0.0, 0.0, 2.0)

        # Attach Input, Camera, and Character Controller handlers
        self.input_handler = WASDInputHandler()
        self.camera_handler = ThirdPersonCameraHandler(
            distance=8.0,
            target_offset=Vec3(0.0, 0.0, 1.2),
            pitch=-15.0,
            smooth_speed=10.0,
            mouse_sensitivity=0.2,
        )
        self.controller = CharacterControllerHandler(
            radius=0.5,
            height=1.0,
            step_height=0.4,
            walk_speed=6.0,
            sprint_speed=12.0,
            acceleration=25.0,
            deceleration=30.0,
        )

        player.add_handler(self.input_handler)
        player.add_handler(self.camera_handler)
        player.add_handler(self.controller)

        # Attach animated KayKit Knight (shared Rig_Medium clips: Idle/Walk/Run/Jump)
        self.actor_handler = ActorAnimationHandler.kaykit_rig_medium("Knight")
        player.add_handler(self.actor_handler)

        self.player = player
        self.add_entity(player)

    def _setup_osd(self) -> None:
        """Create on-screen text overlays for controls reminder and live telemetry."""
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="WASD: Move | SPACE: Jump | 1-4/C: Cam Presets | B: Body Mode | "
                "Esc/P: Pause & Inspector | F12: Wireframe",
                pos=(-1.28, 0.92),
                scale=0.040,
                fg=(1.0, 1.0, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=False,
            )

            self.osd_telemetry = OnscreenText(
                text="Initializing Telemetry...",
                pos=(-1.28, 0.84),
                scale=0.040,
                fg=(0.2, 0.9, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except Exception:  # noqa: BLE001
            # Gracefully ignore in non-graphical environments where OnscreenText is not supported
            self.p(
                "OSD not available in this environment; skipping telemetry overlay.",
                color="yellow",
            )
            self.osd_instructions = None
            self.osd_telemetry = None

    def _set_preset_adventure(self) -> None:
        """Switch to standard Third-Person Orbit Adventure camera preset."""
        if self.camera_handler is not None:
            self.camera_handler.apply_preset(ADVENTURE_PRESET, snap=True)
            self.current_preset_name = ADVENTURE_PRESET.name
        if self.controller is not None:
            self.controller.orientation_mode = CharacterOrientationMode.MOVE_DIRECTION
        self.p(
            f"[Camera Preset] {ADVENTURE_PRESET.name} | Body: MOVE_DIRECTION",
            color="cyan",
            bold=True,
        )

    def _set_preset_shooter(self) -> None:
        """Switch to Over-The-Shoulder Shooter camera preset."""
        if self.camera_handler is not None:
            self.camera_handler.apply_preset(SHOOTER_PRESET, snap=True)
            self.current_preset_name = SHOOTER_PRESET.name
        if self.controller is not None:
            self.controller.orientation_mode = CharacterOrientationMode.CAMERA_LOOK
        self.p(
            f"[Camera Preset] {SHOOTER_PRESET.name} | Body: CAMERA_LOOK",
            color="cyan",
            bold=True,
        )

    def _set_preset_isometric(self) -> None:
        """Switch to Isometric Strategy camera preset."""
        if self.camera_handler is not None:
            self.camera_handler.apply_preset(ISOMETRIC_PRESET, snap=True)
            self.current_preset_name = ISOMETRIC_PRESET.name
        if self.controller is not None:
            self.controller.orientation_mode = CharacterOrientationMode.MOVE_DIRECTION
        self.p(
            f"[Camera Preset] {ISOMETRIC_PRESET.name} | Body: MOVE_DIRECTION",
            color="cyan",
            bold=True,
        )

    def _set_preset_overhead(self) -> None:
        """Switch to Top-Down Overhead camera preset."""
        if self.camera_handler is not None:
            self.camera_handler.apply_preset(OVERHEAD_PRESET, snap=True)
            self.current_preset_name = OVERHEAD_PRESET.name
        if self.controller is not None:
            self.controller.orientation_mode = CharacterOrientationMode.MOVE_DIRECTION
        self.p(
            f"[Camera Preset] {OVERHEAD_PRESET.name} | Body: MOVE_DIRECTION",
            color="cyan",
            bold=True,
        )

    def _cycle_camera_preset(self) -> None:
        """Cycle sequentially through all available standard camera presets."""
        presets = [ADVENTURE_PRESET, SHOOTER_PRESET, ISOMETRIC_PRESET, OVERHEAD_PRESET]
        self._preset_index = (self._preset_index + 1) % len(presets)
        preset = presets[self._preset_index]
        if preset == SHOOTER_PRESET:
            self._set_preset_shooter()
        elif preset == ISOMETRIC_PRESET:
            self._set_preset_isometric()
        elif preset == OVERHEAD_PRESET:
            self._set_preset_overhead()
        else:
            self._set_preset_adventure()

    def _toggle_body_orientation(self) -> None:
        """Toggle body rotation mode between MOVE_DIRECTION and CAMERA_LOOK."""
        if self.controller is None:
            return
        if self.controller.orientation_mode == CharacterOrientationMode.MOVE_DIRECTION:
            self.controller.orientation_mode = CharacterOrientationMode.CAMERA_LOOK
            mode_str = "CAMERA_LOOK (Body faces camera look)"
        else:
            self.controller.orientation_mode = CharacterOrientationMode.MOVE_DIRECTION
            mode_str = "MOVE_DIRECTION (Body faces movement direction)"
        self.p(f"[Body Orientation] {mode_str}", color="magenta", bold=True)

    def _toggle_physics_debug(self) -> None:
        """Toggle Bullet physics debug wireframe and notify via console."""
        active = Physics.toggle_debug()
        state = "ENABLED" if active else "DISABLED"
        self.p(f"[Physics Debug] Bullet Wireframe {state}", color="cyan", bold=True)

    def _on_frame_update(self, task: Any) -> int:
        """Per-frame update driving scene entity updates and telemetry."""
        GlobalClock.get_dt() if hasattr(GlobalClock, "get_dt") else 0.016

        # Scene entities are updated centrally by Game's update task.
        # Update telemetry
        self._update_telemetry(task.time)

        return task.cont

    def _update_telemetry(self, current_time: float) -> None:
        """Update live telemetry display on OSD and periodic console logs."""
        if self.controller is None or self.controller.controller_np is None:
            return

        world_pos = self.controller.controller_np.getPos(self.base.render)
        is_on_ground = self.controller.is_on_ground
        can_jump = self.controller.can_jump
        is_sprinting = self.controller.is_sprinting
        speed = self.controller.current_speed
        mode = "SPRINT" if is_sprinting else "WALK"
        wireframe = "ON" if Physics.is_debug_enabled() else "OFF"
        body_mode = (
            "CAM-LOOK" if self.controller.orientation_mode == CharacterOrientationMode.CAMERA_LOOK else "MOV-DIR"
        )
        cam_preset = getattr(self, "current_preset_name", "Custom")
        locomotion = str(self.actor_handler.locomotion.state) if self.actor_handler is not None else "-"
        clip = (self.actor_handler.current_animation if self.actor_handler is not None else None) or "-"

        # Update OnscreenText OSD
        if self.osd_telemetry is not None:
            self.osd_telemetry.setText(
                f"Camera: {cam_preset} | Body: {body_mode} | "
                f"Pos: ({world_pos.x:6.2f}, {world_pos.y:6.2f}, {world_pos.z:6.2f})\n"
                f"Speed: {speed:4.1f} m/s ({mode}) | Ground: {is_on_ground!s:5} | "
                f"CanJump: {can_jump!s:5} | Debug: {wireframe}\n"
                f"Locomotion: {locomotion:6} | Clip: {clip}"
            )

        # Periodic console telemetry
        if current_time - self._last_console_telemetry_time >= self._console_interval:
            self._last_console_telemetry_time = current_time
            self.p(
                f"[Telemetry] Cam: {cam_preset} | Body: {body_mode} | "
                f"Pos: ({world_pos.x:.2f}, {world_pos.y:.2f}, {world_pos.z:.2f}) | "
                f"Speed: {speed:.1f} m/s ({mode}) | Grounded: {is_on_ground} | "
                f"Wireframe: {wireframe} | Locomotion: {locomotion} | Clip: {clip}",
                color="blue",
            )

    def on_stop(self) -> None:
        """Clean teardown: remove tasks, listeners, static bodies, nodes, and free player entity."""
        self.print_subtitle("Character Controller Sandbox stopping...")

        # 1. Remove telemetry and update task
        self.remove_task(self._task_name)

        # 2. Ignore key listeners
        if self.base is not None and hasattr(self.base, "ignore"):
            self.base.ignore("f12")
            self.base.ignore("1")
            self.base.ignore("2")
            self.base.ignore("3")
            self.base.ignore("4")
            self.base.ignore("c")
            self.base.ignore("b")

        # 3. Destroy OSD elements
        if self.osd_telemetry is not None:
            self.osd_telemetry.destroy()
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            self.osd_instructions.destroy()
            self.osd_instructions = None

        # 4. Free player entity and clear handler references
        if self.player is not None:
            self.player.free()
            self.player = None
        self.actor_handler = None
        self.controller = None
        self.input_handler = None
        self.camera_handler = None

        # 5. Clear global lights to prevent orphaned light nodes
        GlobalLights.clear_lights()

        # 6. Call Scene base stop to free any remaining entities
        super().on_stop()

        # 7. Remove all static environment NodePaths
        for np in self.static_nodes:
            if np is not None and not np.isEmpty():
                np.removeNode()
        self.static_nodes.clear()

        # 8. Remove all static bodies from Bullet physics world
        for body_name in self.static_bodies:
            Physics.remove_body(body_name)
        self.static_bodies.clear()

        self.p("Clean teardown completed: zero dangling physics bodies.", color="green")
        self.print_subtitle("Character Controller Sandbox stopped.")


if __name__ == "__main__":
    from src.game import Game

    app = Game()
    sandbox = TestCharacterSandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
