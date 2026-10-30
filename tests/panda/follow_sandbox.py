"""Interactive 3D Follow Handler sandbox.

Provides a visual testbed for the ``FollowHandler`` virtual-input AI:
- A follower entity built from ``InputHandler`` + ``FollowHandler`` +
  ``CharacterControllerHandler``: the brain writes the movement intent and the
  controller consumes it, exactly like a player-driven body
- A target entity with its own ``CharacterControllerHandler`` that patrols a
  route automatically and can be driven manually with WASD
- A third-person camera mounted on a **separate rig entity**, never on the
  follower: a camera handler on the follower would make the character
  controller interpret the follower's world-space intent as camera-relative
  (see ``docs/handlers/ai.md``)
- Live OSD telemetry with the follow ``state`` and the written ``move_vector``,
  plus a runtime leash toggle that exercises the ``out_of_range`` state
- Clean teardown with zero dangling physics bodies or node leaks
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec2, Vec3

from src.entities.entity import Entity
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics
from src.handlers.ai import FollowHandler
from src.handlers.base import Handler
from src.handlers.camera import ThirdPersonCameraHandler
from src.handlers.input.action_map import SPRINT
from src.handlers.input.base import InputHandler
from src.handlers.input.wasd import WASDInputHandler
from src.handlers.physics import (
    CharacterControllerHandler,
    CollisionGroup,
    RigidBodyHandler,
)

from ..__test import Test

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText


class _TargetDriverHandler(Handler):
    """Drives the target entity as a virtual input source.

    It is registered *after* the ``WASDInputHandler`` and *before* the
    character controller, so in AUTO mode the patrol intent is the freshest
    one the controller reads. In MANUAL mode it stays silent and lets the
    WASD handler own the intent.
    """

    def __init__(self, sandbox: TestFollowSandbox) -> None:
        super().__init__()
        self._sandbox = sandbox

    def on_update(self, dt: float) -> None:
        """Write the target movement intent for this frame."""
        super().on_update(dt)
        self._sandbox.drive_target(dt)


class TestFollowSandbox(Test):
    """Interactive visual 3D sandbox scene for evaluating the follow handler."""

    FOLLOWER_START = Vec3(0.0, 0.0, 1.0)
    TARGET_ROUTE = (
        Vec3(9.0, 0.0, 0.0),
        Vec3(9.0, 9.0, 0.0),
        Vec3(-9.0, 9.0, 0.0),
        Vec3(-9.0, 0.0, 0.0),
    )
    STOP_RADIUS = 3.0
    LEASH_DISTANCE = 12.0
    WAYPOINT_REACHED = 1.2

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        self.follower: Entity | None = None
        self.follower_input: InputHandler | None = None
        self.follow_handler: FollowHandler | None = None
        self.follower_controller: CharacterControllerHandler | None = None

        self.target: Entity | None = None
        self.target_input: WASDInputHandler | None = None
        self.target_controller: CharacterControllerHandler | None = None

        self.camera_rig: Entity | None = None
        self.camera_handler: ThirdPersonCameraHandler | None = None

        self.static_entities: list[Entity] = []

        self._route_index: int = 0
        self._target_auto: bool = True
        self._leash_enabled: bool = True
        self._last_state: str | None = None

        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._last_console_telemetry_time: float = 0.0
        self._console_interval: float = 1.0

        self._task_name: str = "follow_sandbox_update_task"

    # --- lifecycle -------------------------------------------------------

    def on_start(self) -> None:
        """Initialize environment, entities, camera, controls, and telemetry."""
        self.print_title("Follow Handler Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()

        if self.base is None or getattr(self.base, "render", None) is None:
            self.p(
                "No graphics context available; the follow sandbox needs a window.",
                color="yellow",
            )
            return

        self._build_environment()
        self._spawn_camera_rig()
        self._spawn_target()
        self._spawn_follower()

        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)
            self.base.accept("t", self._toggle_target_control)
            self.base.accept("l", self._toggle_leash)

        self._setup_osd()
        self._setup_inspector()
        self.add_task(self._task_name, self._on_frame_update)

    def _setup_inspector(self) -> None:
        """Register follow and target controls for live editing in the pause inspector."""
        self.expose_toggle(
            "Target Auto Route (T)",
            lambda: self._target_auto,
            lambda _v: self._toggle_target_control(),
        )
        self.expose_toggle(
            "Leash Enabled (L)",
            lambda: self._leash_enabled,
            lambda _v: self._toggle_leash(),
        )

    def on_stop(self) -> None:
        """Clean teardown: remove tasks, listeners, entities, nodes, and lights."""
        self.print_subtitle("Follow Handler Sandbox stopping...")

        self.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            self.base.ignore("f12")
            self.base.ignore("t")
            self.base.ignore("l")

        if self.osd_telemetry is not None:
            self.osd_telemetry.destroy()
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            self.osd_instructions.destroy()
            self.osd_instructions = None

        entities = [
            self.follower,
            self.target,
            self.camera_rig,
            *self.static_entities,
        ]
        for entity in entities:
            if entity is not None:
                entity.free()
        self.static_entities.clear()

        self.follower_controller = None
        self.follow_handler = None
        self.follower_input = None
        self.follower = None
        self.target_controller = None
        self.target_input = None
        self.target = None
        self.camera_handler = None
        self.camera_rig = None

        GlobalLights.clear_lights()

        super().on_stop()

        self.p("Clean teardown completed: zero dangling physics bodies.", color="green")
        self.print_subtitle("Follow Handler Sandbox stopped.")

    def _print_controls_banner(self) -> None:
        """Print formatted ANSI startup banner with control and layout instructions."""
        self.print_subtitle("Interactive Controls & Follow Behaviour", color="yellow")
        self.p(
            " Controls:   WASD: Move Target | Mouse: Look | T: Target Mode | L: Leash | F12: Wireframe",
            color="cyan",
            bold=True,
        )
        self.p(
            " Follower:   the brain writes a world-space intent into the InputHandler",
            color="green",
            bold=True,
        )
        self.p(
            "             the character controller consumes it, so the follower walks to the target",
            color="green",
            bold=True,
        )
        self.p(
            " Target:     [W, A, S, D] drives the target (camera relative) in MANUAL mode",
            color="green",
            bold=True,
        )
        self.p(
            " Camera:     mounted on a separate rig entity, never on the follower",
            color="green",
            bold=True,
        )
        self.p(
            " Leash:      [L] toggles max_distance; drive the target past it to see OUT_OF_RANGE",
            color="green",
            bold=True,
        )
        self.p(
            " Wireframe:  [F12] Toggle Bullet debug visualization",
            color="magenta",
            bold=True,
        )

        self.space_line()
        self.p("Arena Layout:", color="cyan", bold=True)
        self.p(
            " - The follower starts at the origin and patrols after a target on a square route",
            color="cyan",
        )
        self.p(
            f" - The follower stops once it is within {self.STOP_RADIUS:.1f}m of the target",
            color="cyan",
        )
        self.p(
            f" - With the leash ON the follower gives up beyond {self.LEASH_DISTANCE:.1f}m and resumes when the target returns",
            color="cyan",
        )
        self.space_line()

    # --- environment -----------------------------------------------------

    def _create_static_box(
        self,
        name: str,
        pos: tuple[float, float, float] | Vec3,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 1.0),
    ) -> Entity:
        """Create a static RigidBodyHandler entity with a matching visual box."""
        entity = Entity(name)
        entity.node.reparentTo(self.base.render)
        entity.node.setPos(*pos)
        entity.add_handler(
            RigidBodyHandler(
                shape=BulletBoxShape(Vec3(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)),
                mass=0.0,
            )
        )
        self._attach_box_visual(entity.node, f"{name}_visual", size, color)
        self.static_entities.append(entity)
        self.add_entity(entity)
        return entity

    def _build_environment(self) -> None:
        """Build the arena: a ground platform and four corner markers."""
        self._create_static_box(
            name="ground",
            pos=(0.0, 0.0, -0.25),
            size=(48.0, 48.0, 0.5),
            color=(0.22, 0.25, 0.28, 1.0),
        )

        for index, waypoint in enumerate(self.TARGET_ROUTE):
            marker = Entity(f"waypoint_{index}")
            marker.node.reparentTo(self.base.render)
            marker.node.setPos(waypoint.x, waypoint.y, 0.06)
            self._attach_box_visual(
                marker.node,
                f"waypoint_{index}_visual",
                (1.2, 1.2, 0.12),
                (0.85, 0.70, 0.20, 1.0),
            )
            self.static_entities.append(marker)
            self.add_entity(marker)

    @staticmethod
    def _attach_box_visual(
        parent: NodePath,
        name: str,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float],
    ) -> NodePath:
        """Attach a scaled box model visual centered on the given parent NodePath."""
        box_model = GlobalLoader.load_panda_asset("box")
        visual_np = parent.attachNewNode(name)
        box_model.copyTo(visual_np)
        visual_np.setScale(size[0], size[1], size[2])
        visual_np.setPos(-size[0] / 2.0, -size[1] / 2.0, -size[2] / 2.0)
        visual_np.setColor(*color)
        return visual_np

    # --- entities --------------------------------------------------------

    def _spawn_camera_rig(self) -> None:
        """Spawn the camera rig entity that frames the follower from a distance."""
        rig = Entity("CameraRig")
        rig.node.reparentTo(self.base.render)
        rig.node.setPos(
            self.FOLLOWER_START.x, self.FOLLOWER_START.y, self.FOLLOWER_START.z
        )

        self.camera_handler = ThirdPersonCameraHandler(
            distance=11.0,
            min_distance=3.0,
            max_distance=25.0,
            target_offset=Vec3(0.0, 0.0, 1.2),
            pitch=-22.0,
            smooth_speed=8.0,
            mouse_sensitivity=0.2,
            collision_enabled=False,
        )
        rig.add_handler(self.camera_handler)

        self.camera_rig = rig
        self.add_entity(rig)

    def _spawn_target(self) -> None:
        """Spawn the target entity: WASD intent, patrol driver, then the controller."""
        target = Entity("Target")
        target.node.reparentTo(self.base.render)
        start = self.TARGET_ROUTE[0]
        target.node.setPos(start.x, start.y, 1.0)

        self.target_input = WASDInputHandler()
        target.add_handler(self.target_input)
        target.add_handler(_TargetDriverHandler(self))

        self.target_controller = CharacterControllerHandler(
            radius=0.4,
            height=1.0,
            walk_speed=3.5,
            sprint_speed=6.0,
            acceleration=20.0,
            deceleration=24.0,
            collision_group=CollisionGroup.ENEMY,
            camera_handler=self.camera_handler,
        )
        target.add_handler(self.target_controller)

        if (
            self.target_controller.controller_np is not None
            and not self.target_controller.controller_np.isEmpty()
        ):
            self._attach_box_visual(
                self.target_controller.controller_np,
                "target_visual",
                (0.8, 0.8, 1.8),
                (0.95, 0.75, 0.20, 1.0),
            )

        self.target = target
        self.add_entity(target)

    def _spawn_follower(self) -> None:
        """Spawn the follower entity: intent, follow brain, then the controller."""
        follower = Entity("Follower")
        follower.node.reparentTo(self.base.render)
        follower.node.setPos(
            self.FOLLOWER_START.x, self.FOLLOWER_START.y, self.FOLLOWER_START.z
        )

        self.follower_input = InputHandler()
        follower.add_handler(self.follower_input)

        self.follow_handler = FollowHandler(
            target=self.target,
            stop_radius=self.STOP_RADIUS,
            max_distance=self.LEASH_DISTANCE,
            speed_factor=1.0,
            chase_sprint=True,
        )
        follower.add_handler(self.follow_handler)

        self.follower_controller = CharacterControllerHandler(
            radius=0.4,
            height=1.0,
            walk_speed=4.0,
            sprint_speed=7.5,
            acceleration=22.0,
            deceleration=26.0,
            collision_group=CollisionGroup.PLAYER,
        )
        follower.add_handler(self.follower_controller)

        if (
            self.follower_controller.controller_np is not None
            and not self.follower_controller.controller_np.isEmpty()
        ):
            self._attach_box_visual(
                self.follower_controller.controller_np,
                "follower_visual",
                (0.8, 0.8, 1.8),
                (0.25, 0.55, 0.95, 1.0),
            )

        self.follower = follower
        self.add_entity(follower)

    # --- behaviour -------------------------------------------------------

    def drive_target(self, dt: float) -> None:
        """Steer the target along its patrol route (AUTO mode only)."""
        if self.target is None or self.target.is_freed:
            return
        if not self._target_auto:
            # MANUAL mode: the WASD handler owns the intent, stay silent.
            return

        input_handler = self.target_input
        if input_handler is None:
            return

        position = self.target_position()
        goal = self.TARGET_ROUTE[self._route_index]
        to_goal = Vec3(goal.x - position.x, goal.y - position.y, 0.0)
        if to_goal.length() <= self.WAYPOINT_REACHED:
            self._route_index = (self._route_index + 1) % len(self.TARGET_ROUTE)
            goal = self.TARGET_ROUTE[self._route_index]
            to_goal = Vec3(goal.x - position.x, goal.y - position.y, 0.0)

        if to_goal.length_squared() <= 1e-8:
            input_handler.set_move_vector(0.0, 0.0)
            return

        direction = to_goal.normalized()
        relative = self._world_to_camera_relative(direction)
        input_handler.set_move_vector(relative.x, relative.y)

    def _world_to_camera_relative(self, direction: Vec3) -> Vec2:
        """Convert a world-space direction into the camera's horizontal frame.

        The target controller consumes the intent as camera-relative (it is
        wired to the camera rig), so the patrol route must be expressed in
        the same frame or the target would drift when the camera is orbited.
        """
        camera = self.camera_handler
        if camera is None:
            return Vec2(direction.x, direction.y)

        forward = camera.get_forward_vector()
        forward_h = Vec3(forward.x, forward.y, 0.0)
        if forward_h.length_squared() <= 1e-8:
            forward_h = Vec3(0.0, 1.0, 0.0)
        forward_h.normalize()

        right_h = forward_h.cross(Vec3(0.0, 0.0, 1.0))
        if right_h.length_squared() <= 1e-8:
            right_h = Vec3(1.0, 0.0, 0.0)
        right_h.normalize()

        return Vec2(direction.dot(right_h), direction.dot(forward_h))

    def follower_position(self) -> Vec3:
        """Return the follower world position, preferring the character controller node."""
        controller = self.follower_controller
        if (
            controller is not None
            and controller.controller_np is not None
            and not controller.controller_np.isEmpty()
        ):
            return Vec3(controller.controller_np.getPos(self.base.render))
        if self.follower is not None:
            return Vec3(self.follower.node.getPos(self.base.render))
        return Vec3(0.0, 0.0, 0.0)

    def target_position(self) -> Vec3:
        """Return the target world position, preferring the character controller node."""
        controller = self.target_controller
        if (
            controller is not None
            and controller.controller_np is not None
            and not controller.controller_np.isEmpty()
        ):
            return Vec3(controller.controller_np.getPos(self.base.render))
        if self.target is not None:
            return Vec3(self.target.node.getPos(self.base.render))
        return Vec3(0.0, 0.0, 0.0)

    def _toggle_target_control(self) -> None:
        """Switch the target between the automatic route and manual player control."""
        self._target_auto = not self._target_auto
        mode = "AUTO" if self._target_auto else "MANUAL (WASD)"
        self.p(f"[Target] Control mode: {mode}", color="yellow", bold=True)

    def _toggle_leash(self) -> None:
        """Toggle the follow leash, switching the brain between following and out of range."""
        self._leash_enabled = not self._leash_enabled
        if self.follow_handler is not None:
            self.follow_handler.max_distance = (
                self.LEASH_DISTANCE if self._leash_enabled else None
            )
        state = "ON" if self._leash_enabled else "OFF"
        self.p(f"[Follow] Leash: {state}", color="yellow", bold=True)

    def _toggle_physics_debug(self) -> None:
        """Toggle the Bullet physics debug wireframe and notify via console."""
        active = Physics.toggle_debug()
        state = "ENABLED" if active else "DISABLED"
        self.p(f"[Physics Debug] Bullet Wireframe {state}", color="cyan", bold=True)

    # --- frame update ----------------------------------------------------

    def _on_frame_update(self, task: Any) -> int:
        """Per-frame update: keep the camera rig on the follower and refresh the telemetry."""
        if self.camera_rig is not None and self.follower is not None:
            follower_pos = self.follower_position()
            self.camera_rig.node.setPos(follower_pos)

        if self.follow_handler is not None:
            state = self.follow_handler.state.value
            if state != self._last_state:
                self._last_state = state
                self.p(f"[Follow] State -> {state.upper()}", color="cyan", bold=True)

        self._update_osd(task.time)
        return task.cont

    def _update_osd(self, current_time: float) -> None:
        """Update the live telemetry on the OSD and print it to the terminal."""
        state = (
            self.follow_handler.state.value.upper()
            if self.follow_handler is not None
            else "?"
        )
        move = (
            self.follow_handler.move_vector if self.follow_handler is not None else None
        )
        move_x = move.x if move is not None else 0.0
        move_y = move.y if move is not None else 0.0
        distance = (self.target_position() - self.follower_position()).length()
        target_mode = "AUTO" if self._target_auto else "MANUAL"
        leash = "ON" if self._leash_enabled else "OFF"
        wireframe = "ON" if Physics.is_debug_enabled() else "OFF"
        sprinting = (
            self.follower_input is not None
            and self.follower_input.is_action_down(SPRINT)
        )

        if self.osd_telemetry is not None:
            self.osd_telemetry.setText(
                f"Follow state: {state:<12} | move_vector: ({move_x:+.2f}, {move_y:+.2f}) | dist: {distance:5.2f}m\n"
                f"Leash: {leash:<3} | Target: {target_mode:<6} | Sprint: {'YES' if sprinting else 'NO ':<3} | Wireframe: {wireframe}"
            )

        if current_time - self._last_console_telemetry_time >= self._console_interval:
            self._last_console_telemetry_time = current_time
            self.p(
                f"[Follow] state={state} | move_vector=({move_x:+.2f}, {move_y:+.2f}) | dist={distance:.2f}m | "
                f"leash={leash} | target={target_mode} | sprint={sprinting} | wireframe={wireframe}",
                color="blue",
            )

    def _setup_osd(self) -> None:
        """Create the on-screen text overlays for the controls reminder and telemetry."""
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="WASD: Move Target | Mouse: Look | T: Target Mode | L: Leash | Esc/P: Pause & Inspector | F12: Wireframe",
                pos=(-1.28, 0.92),
                scale=0.045,
                fg=(1.0, 1.0, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=False,
            )

            self.osd_telemetry = OnscreenText(
                text="Initializing follow telemetry...",
                pos=(-1.28, 0.84),
                scale=0.042,
                fg=(0.2, 0.9, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except Exception:  # noqa: BLE001
            self.p(
                "OSD not available in this environment; skipping telemetry overlay.",
                color="yellow",
            )
            self.osd_instructions = None
            self.osd_telemetry = None


if __name__ == "__main__":
    from src.game import Game

    app = Game()
    sandbox = TestFollowSandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
