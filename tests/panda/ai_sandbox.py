"""Interactive 3D AI Patrol sandbox.

Provides a physical test course featuring:
- Static ground plus two wall segments that leave a sight gap in the middle,
  so the NPC loses and regains sight of the target while patrolling
- An AI NPC entity built from InputHandler + AIPatrolHandler +
  CharacterControllerHandler, patrolling waypoints and chasing on sight
- A movable target entity (static rigid body) that the player drives with WASD
  or that follows an automatic route, so the line of sight can be tested both
  ways
- A trigger volume wired to TriggerZoneHandler enter/stay/exit events
- Live line-of-sight telemetry with a runtime toggle between the real Bullet
  raycast and an injected callable (`[L]`), plus `[T]` to switch the target
  between automatic and manual control and `[F12]` for the Bullet wireframe
- Clean teardown with zero dangling physics bodies or node leaks
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, TransparencyAttrib, Vec3

from src.entities.entity import Entity
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics
from src.handlers.ai import AINavigationHandler, NavigationState
from src.handlers.base import Handler
from src.handlers.camera import ThirdPersonCameraHandler
from src.handlers.input.base import InputHandler
from src.handlers.input.wasd import WASDInputHandler
from src.handlers.physics import (
    CharacterControllerHandler,
    CollisionGroup,
    RigidBodyHandler,
    TriggerZoneHandler,
)
from src.navigation import generate_nav_grid

from ..__test import Test

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText


class _TargetMoverHandler(Handler):
    """Moves the target entity node, either along its route or from player input.

    It is registered *before* the rigid body handler so the transform is
    propagated to Bullet within the same frame.
    """

    def __init__(self, sandbox: TestAISandbox) -> None:
        super().__init__()
        self._sandbox = sandbox

    def on_update(self, dt: float) -> None:
        """Apply the target movement for this frame."""
        super().on_update(dt)
        self._sandbox.move_target(dt)


class TestAISandbox(Test):
    """Interactive visual 3D sandbox scene for evaluating the AI patrol handler."""

    NPC_WAYPOINTS = (
        Vec3(-7.0, -5.0, 0.0),
        Vec3(-7.0, 5.0, 0.0),
        Vec3(-3.5, 0.0, 0.0),
    )
    TARGET_ROUTE = (
        Vec3(4.0, -5.0, 0.0),
        Vec3(4.0, 5.0, 0.0),
        Vec3(8.0, 0.0, 0.0),
    )
    TARGET_HEIGHT = 0.5
    TARGET_SPEED = 3.0
    SIGHT_RANGE = 9.0
    LOSE_RANGE = 13.0

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        self.npc: Entity | None = None
        self.npc_controller: CharacterControllerHandler | None = None
        self.ai_handler: AINavigationHandler | None = None
        self.npc_input: InputHandler | None = None

        self.target: Entity | None = None
        self.target_input: WASDInputHandler | None = None
        self.target_rigid: RigidBodyHandler | None = None

        self.camera_rig: Entity | None = None
        self.camera_handler: ThirdPersonCameraHandler | None = None

        self.zone_entity: Entity | None = None
        self.zone_handler: TriggerZoneHandler | None = None
        self.static_entities: list[Entity] = []

        self._route_index: int = 0
        self._target_auto: bool = True
        self._los_injected: bool = False
        self.target_speed: float = float(self.TARGET_SPEED)
        self._counters: dict[str, int] = {"enter": 0, "stay": 0, "exit": 0}
        self._last_state: NavigationState | None = None

        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._last_console_telemetry_time: float = 0.0
        self._console_interval: float = 1.0

        self._obstacle_closed: bool = False
        self._obstacle_entity: Entity | None = None
        self._task_name: str = "ai_sandbox_update_task"

    # --- lifecycle -------------------------------------------------------

    def on_start(self) -> None:
        """Initialize environment, entities, camera, controls, and telemetry."""
        self.print_title("AI Patrol Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()

        self._build_environment()
        self._spawn_target()
        self._spawn_npc()
        self._spawn_camera_rig()
        self._spawn_zone()

        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)
            self.base.accept("l", self._toggle_line_of_sight)
            self.base.accept("t", self._toggle_target_control)
            self.base.accept("o", self._toggle_obstacle)
            self.base.accept("O", self._toggle_obstacle)
            self.base.accept("1", self._toggle_obstacle)
            self.p("[Keys] Bound O/1 -> toggle obstacle", color="cyan")

        self._setup_osd()
        self._setup_inspector()
        self.add_task(self._task_name, self._on_frame_update)

    def _setup_inspector(self) -> None:
        """Register AI patrol and target parameters for live editing in the pause inspector."""
        self.expose_toggle(
            "Target Auto Route (T)",
            lambda: self._target_auto,
            lambda _v: self._toggle_target_control(),
        )
        self.expose_toggle(
            "Injected LOS (L)",
            lambda: self._los_injected,
            lambda _v: self._toggle_line_of_sight(),
        )
        self.expose_field("Target Speed", self, "target_speed", 0.5, 12.0, 0.5)
        if self.ai_handler is not None:
            self.expose_field("Search Time", self.ai_handler, "search_time", 0.0, 10.0, 0.5)
            self.expose_toggle(
                "Remember Last Target",
                lambda: self.ai_handler.remember_last_target if self.ai_handler is not None else False,
                lambda v: (
                    setattr(self.ai_handler, "remember_last_target", bool(v)) if self.ai_handler is not None else None
                ),
            )
            self.expose_toggle(
                "Search Pathfinding",
                lambda: self.ai_handler.search_uses_pathfinding if self.ai_handler is not None else False,
                lambda v: (
                    setattr(self.ai_handler, "search_uses_pathfinding", bool(v))
                    if self.ai_handler is not None
                    else None
                ),
            )

    def on_stop(self) -> None:
        """Clean teardown: remove tasks, listeners, entities, nodes, and lights."""
        self.print_subtitle("AI Patrol Sandbox stopping...")

        self.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            self.base.ignore("f12")
            self.base.ignore("l")
            self.base.ignore("t")
            self.base.ignore("o")
            self.base.ignore("O")
            self.base.ignore("1")

        if self.osd_telemetry is not None:
            self.osd_telemetry.destroy()
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            self.osd_instructions.destroy()
            self.osd_instructions = None

        entities = [
            self.npc,
            self.target,
            self.camera_rig,
            self.zone_entity,
            self._obstacle_entity,
            *self.static_entities,
        ]
        for entity in entities:
            if entity is not None:
                entity.free()
        self.static_entities.clear()

        self.zone_handler = None
        self.zone_entity = None
        self.camera_handler = None
        self.camera_rig = None
        self.target_rigid = None
        self.target_input = None
        self.target = None
        self.npc_input = None
        self.ai_handler = None
        self.npc_controller = None
        self.npc = None

        GlobalLights.clear_lights()

        super().on_stop()

        self.p("Clean teardown completed: zero dangling physics bodies.", color="green")
        self.print_subtitle("AI Patrol Sandbox stopped.")

    def _print_controls_banner(self) -> None:
        """Print formatted ANSI startup banner with control and layout instructions."""
        self.print_subtitle("Interactive Controls & AI Behaviour", color="yellow")
        self.p(
            " Controls:   WASD: Move Target | Mouse: Look | L: Toggle LOS | T: Target Mode | F12: Wireframe",
            color="cyan",
            bold=True,
        )
        self.p(
            " Target:     [W, A, S, D] moves the target when the target mode is MANUAL",
            color="green",
            bold=True,
        )
        self.p(
            " AI:         the NPC patrols waypoints and chases the target when it can see it",
            color="green",
            bold=True,
        )
        self.p(
            " Line of Sight: [L] switches between the real Bullet raycast and an injected callable",
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
        self.p(" - Two wall segments at x=0 leave a 2m sight gap around y=0", color="cyan")
        self.p(
            " - The NPC patrols on the left side, the target moves on the right side",
            color="cyan",
        )
        self.p(
            " - The trigger volume sits on the NPC patrol route and counts enter/stay/exit",
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

    @staticmethod
    def _attach_box_visual(
        parent: NodePath,
        name: str,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float],
        translucent: bool = False,
    ) -> NodePath:
        """Attach a scaled box model visual centered on the given parent NodePath."""
        box_model = GlobalLoader.load_panda_asset("box")
        visual_np = parent.attachNewNode(name)
        box_model.copyTo(visual_np)
        visual_np.setScale(size[0], size[1], size[2])
        visual_np.setPos(-size[0] / 2.0, -size[1] / 2.0, -size[2] / 2.0)
        if translucent:
            visual_np.setTransparency(TransparencyAttrib.MAlpha)
            visual_np.setTwoSided(True)
        visual_np.setColor(*color)
        return visual_np

    def _build_environment(self) -> None:
        """Build the arena: ground plus the two wall segments that create the sight gap."""
        self._create_static_box(
            name="ground",
            pos=(0.0, 0.0, -0.25),
            size=(44.0, 44.0, 0.5),
            color=(0.24, 0.27, 0.30, 1.0),
        )
        self._create_static_box(
            name="wall_west",
            pos=(0.0, -4.5, 1.5),
            size=(0.6, 7.0, 3.0),
            color=(0.45, 0.50, 0.55, 1.0),
        )
        self._create_static_box(
            name="wall_east",
            pos=(0.0, 4.5, 1.5),
            size=(0.6, 7.0, 3.0),
            color=(0.45, 0.50, 0.55, 1.0),
        )

    # --- entities --------------------------------------------------------

    def _spawn_target(self) -> None:
        """Spawn the target entity as a static rigid body the player can drive around."""
        target = Entity("Target")
        target.node.reparentTo(self.base.render)
        target.node.setPos(self.TARGET_ROUTE[0].x, self.TARGET_ROUTE[0].y, self.TARGET_HEIGHT)

        self.target_input = WASDInputHandler()
        target.add_handler(self.target_input)
        target.add_handler(_TargetMoverHandler(self))
        self.target_rigid = target.add_handler(
            RigidBodyHandler(
                shape=BulletBoxShape(Vec3(0.45, 0.45, 0.5)),
                mass=0.0,
                collision_group=CollisionGroup.PLAYER,
            )
        )
        self._attach_box_visual(
            target.node,
            "target_visual",
            (0.9, 0.9, 1.0),
            (0.95, 0.75, 0.2, 1.0),
        )

        self.target = target
        self.add_entity(target)

    def _spawn_npc(self) -> None:
        """Spawn the AI NPC: virtual input, patrol brain, then the movement controller."""
        npc = Entity("Npc")
        npc.node.reparentTo(self.base.render)
        npc.node.setPos(self.NPC_WAYPOINTS[0].x, self.NPC_WAYPOINTS[0].y, 1.0)

        self.npc_input = InputHandler()
        npc.add_handler(self.npc_input)

        nav_grid = generate_nav_grid(bounds_min=(-20.0, -20.0), bounds_max=(20.0, 20.0), cell_size=1.0)

        self.ai_handler = AINavigationHandler(
            waypoints=self.NPC_WAYPOINTS,
            nav_grid=nav_grid,
            arrive_radius=0.6,
            wait_time=1.0,
            ping_pong=False,
            target=self.target,
            sight_range=self.SIGHT_RANGE,
            lose_range=self.LOSE_RANGE,
            chase_sprint=True,
            eye_height=1.0,
            search_time=4.0,
            remember_last_target=True,
            search_uses_pathfinding=True,
        )
        npc.add_handler(self.ai_handler)

        self.npc_controller = CharacterControllerHandler(
            radius=0.4,
            height=1.0,
            step_height=0.4,
            walk_speed=3.2,
            sprint_speed=5.5,
            acceleration=18.0,
            deceleration=22.0,
            collision_group=CollisionGroup.ENEMY,
        )
        npc.add_handler(self.npc_controller)

        if self.npc_controller.controller_np is not None and not self.npc_controller.controller_np.isEmpty():
            self._attach_box_visual(
                self.npc_controller.controller_np,
                "npc_visual",
                (0.8, 0.8, 1.8),
                (0.25, 0.55, 0.95, 1.0),
            )

        self.npc = npc
        self.add_entity(npc)

    def _spawn_camera_rig(self) -> None:
        """Spawn a camera rig entity that follows the NPC without touching its entity."""
        rig = Entity("CameraRig")
        rig.node.reparentTo(self.base.render)
        rig.node.setPos(self.NPC_WAYPOINTS[0].x, self.NPC_WAYPOINTS[0].y, 1.0)

        self.camera_handler = ThirdPersonCameraHandler(
            distance=9.0,
            min_distance=3.0,
            max_distance=20.0,
            target_offset=Vec3(0.0, 0.0, 1.2),
            pitch=-18.0,
            smooth_speed=8.0,
            mouse_sensitivity=0.2,
            collision_enabled=False,
        )
        rig.add_handler(self.camera_handler)

        self.camera_rig = rig
        self.add_entity(rig)

    def _spawn_zone(self) -> None:
        """Create the trigger volume on the NPC patrol route and wire its counters."""
        zone = Entity("NpcZone")
        zone.node.reparentTo(self.base.render)
        zone.node.setPos(-7.0, 0.0, 1.0)

        handler = zone.add_handler(
            TriggerZoneHandler(
                shape=BulletBoxShape(Vec3(1.5, 1.5, 1.0)),
                target_groups={CollisionGroup.ENEMY},
            )
        )
        self._attach_box_visual(
            zone.node,
            "zone_visual",
            (3.0, 3.0, 2.0),
            (0.2, 0.6, 1.0, 0.35),
            translucent=True,
        )

        handler.on_enter.add_callback(self._on_zone_enter)
        handler.on_stay.add_callback(self._on_zone_stay)
        handler.on_exit.add_callback(self._on_zone_exit)

        self.zone_handler = handler
        self.zone_entity = zone
        self.add_entity(zone)

    # --- behaviour -------------------------------------------------------

    def move_target(self, dt: float) -> None:
        """Move the target entity along its route or from the player's input."""
        if self.target is None or self.target.is_freed:
            return

        direction = Vec3(0.0, 0.0, 0.0)
        if self._target_auto:
            goal = self.TARGET_ROUTE[self._route_index]
            to_goal = Vec3(goal.x - self.target.node.getX(), goal.y - self.target.node.getY(), 0.0)
            if to_goal.length() <= 0.4:
                self._route_index = (self._route_index + 1) % len(self.TARGET_ROUTE)
                goal = self.TARGET_ROUTE[self._route_index]
                to_goal = Vec3(
                    goal.x - self.target.node.getX(),
                    goal.y - self.target.node.getY(),
                    0.0,
                )
            if to_goal.length() > 1e-5:
                direction = to_goal.normalized()
        elif self.target_input is not None:
            move = self.target_input.move_vector
            direction = Vec3(move.x, move.y, 0.0)
            if direction.length() > 1.0:
                direction.normalize()

        if direction.length_squared() <= 1e-8:
            return

        position = self.target.node.getPos()
        position += direction * (self.target_speed * dt)
        position.z = self.TARGET_HEIGHT
        self.target.node.setPos(position)

    def npc_position(self) -> Vec3:
        """Return the NPC world position, preferring the character controller node."""
        controller = self.npc_controller
        if controller is not None and controller.controller_np is not None:
            controller_np = controller.controller_np
            if not controller_np.isEmpty():
                return Vec3(controller_np.getPos(self.base.render))
        if self.npc is not None:
            return Vec3(self.npc.node.getPos(self.base.render))
        return Vec3(0.0, 0.0, 0.0)

    def _toggle_line_of_sight(self) -> None:
        """Switch the AI between the real Bullet raycast and an injected callable."""
        if self.ai_handler is None:
            return
        self._los_injected = not self._los_injected
        if self._los_injected:
            self.ai_handler.line_of_sight = self._injected_line_of_sight
            self.p(
                "[AI] Line of sight: INJECTED callable (always visible)",
                color="magenta",
                bold=True,
            )
        else:
            self.ai_handler.line_of_sight = None
            self.p("[AI] Line of sight: REAL Bullet raycast", color="cyan", bold=True)

    def _injected_line_of_sight(self, eye: Vec3, goal: Vec3) -> bool:
        """Injected line of sight that ignores geometry and always reports visibility."""
        return True

    def _toggle_target_control(self) -> None:
        """Switch the target between the automatic route and manual player control."""
        self._target_auto = not self._target_auto
        mode = "AUTO" if self._target_auto else "MANUAL (WASD)"
        self.p(f"[Target] Control mode: {mode}", color="yellow", bold=True)

    def _toggle_obstacle(self) -> None:
        """Toggle a barrier in the central gap and force the AI to replan."""
        self.p("[Obstacle] Toggle requested", color="magenta", bold=True)
        self._obstacle_closed = not self._obstacle_closed
        if self.ai_handler is None or self.ai_handler.nav_grid is None:
            self.p("[Obstacle] No navigation grid available.", color="red")
            return
        grid = self.ai_handler.nav_grid
        cells = [(19, y) for y in (19, 20, 21)] + [(20, y) for y in (19, 20, 21)]
        before = list(grid.blocked)
        if self._obstacle_closed:
            if self._obstacle_entity is None:
                obstacle = Entity("Obstacle")
                obstacle.node.reparentTo(self.base.render)
                obstacle.node.setPos(0.0, 0.0, 1.5)
                obstacle.add_handler(
                    RigidBodyHandler(
                        shape=BulletBoxShape(Vec3(0.3, 1.0, 1.5)),
                        mass=0.0,
                    )
                )
                self._attach_box_visual(
                    obstacle.node,
                    "obstacle_visual",
                    (0.6, 2.0, 3.0),
                    (0.85, 0.25, 0.2, 1.0),
                )
                self._obstacle_entity = obstacle
                self.add_entity(obstacle)
            grid.set_blocked(cells)
            self.p(
                f"[Obstacle] Central gap CLOSED -> blocked {cells}",
                color="yellow",
                bold=True,
            )
        else:
            if self._obstacle_entity is not None:
                self._obstacle_entity.free()
                self._obstacle_entity = None
            for cell in cells:
                grid.unblock(cell)
            self.p(
                f"[Obstacle] Central gap OPEN -> unblocked {cells}",
                color="cyan",
                bold=True,
            )
        after = list(grid.blocked)
        self.p(
            f"[Obstacle] blocked before={len(before)} after={len(after)} "
            f"path={len(self.ai_handler.current_path)} replans={self.ai_handler.replan_count}",
            color="blue",
        )
        self.ai_handler.request_replan()
        self.p(
            f"[Obstacle] replan done -> path={len(self.ai_handler.current_path)} "
            f"replans={self.ai_handler.replan_count}",
            color="green",
        )

    def _toggle_physics_debug(self) -> None:
        """Toggle the Bullet physics debug wireframe and notify via console."""
        active = Physics.toggle_debug()
        state = "ENABLED" if active else "DISABLED"
        self.p(f"[Physics Debug] Bullet Wireframe {state}", color="cyan", bold=True)

    # --- trigger callbacks ------------------------------------------------

    def _on_zone_enter(self, entity: Entity) -> None:
        """Count and report a trigger enter event."""
        self._counters["enter"] += 1
        self.p(f"[Zone] ENTER: {entity.name}", color="green")

    def _on_zone_stay(self, entity: Entity) -> None:
        """Count a trigger stay event."""
        self._counters["stay"] += 1

    def _on_zone_exit(self, entity: Entity) -> None:
        """Count and report a trigger exit event."""
        self._counters["exit"] += 1
        self.p(f"[Zone] EXIT: {entity.name}", color="yellow")

    # --- frame update ----------------------------------------------------

    def _on_frame_update(self, task: Any) -> int:
        """Per-frame update: keep the camera rig on the NPC and refresh the telemetry."""
        if self.camera_rig is not None:
            self.camera_rig.node.setPos(self.npc_position())

        if self.ai_handler is not None:
            state = self.ai_handler.state
            if state != self._last_state:
                self._last_state = state
                self.p(f"[AI] State -> {state.value.upper()}", color="cyan", bold=True)

        self._update_osd(task.time)
        return task.cont

    def _update_osd(self, current_time: float) -> None:
        """Update the live telemetry on the OSD and print it to the terminal."""
        state = self.ai_handler.state.value.upper() if self.ai_handler is not None else "?"
        los_mode = "INJECTED" if self._los_injected else "REAL"
        visible = self.ai_handler.can_see_target() if self.ai_handler is not None else False
        target_mode = "AUTO" if self._target_auto else "MANUAL"
        wireframe = "ON" if Physics.is_debug_enabled() else "OFF"

        distance = 0.0
        if self.target is not None:
            distance = (Vec3(self.target.node.getPos()) - self.npc_position()).length()

        if self.osd_telemetry is not None:
            self.osd_telemetry.setText(
                f"AI state: {state:<7} | LOS: {los_mode:<8} | visible: {'YES' if visible else 'NO ':<3} | "
                f"dist: {distance:5.2f}m\n"
                f"Target: {target_mode:<6} | Trigger(ENEMY): enter={self._counters['enter']:<3} "
                f"stay={self._counters['stay']:<5} exit={self._counters['exit']:<3} | Wireframe: {wireframe}"
            )

        if current_time - self._last_console_telemetry_time >= self._console_interval:
            self._last_console_telemetry_time = current_time
            self.p(
                f"[AI] state={state} | los={los_mode} | visible={visible} | dist={distance:.2f}m | "
                f"target={target_mode} | trigger enter/stay/exit="
                f"{self._counters['enter']}/{self._counters['stay']}/{self._counters['exit']} | "
                f"wireframe={wireframe}",
                color="blue",
            )

    def _setup_osd(self) -> None:
        """Create the on-screen text overlays for the controls reminder and telemetry."""
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="WASD: Move Target | Mouse: Look | L: Toggle LOS | "
                "T: Target Mode | O: Toggle Obstacle | Esc/P: Pause & Inspector | F12: Wireframe",
                pos=(-1.28, 0.92),
                scale=0.045,
                fg=(1.0, 1.0, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=False,
            )

            self.osd_telemetry = OnscreenText(
                text="Initializing AI telemetry...",
                pos=(-1.28, 0.84),
                scale=0.042,
                fg=(0.2, 0.9, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except (RuntimeError, TypeError, AttributeError, ImportError, ValueError):
            self.p(
                "OSD not available in this environment; skipping telemetry overlay.",
                color="yellow",
            )
            self.osd_instructions = None
            self.osd_telemetry = None


if __name__ == "__main__":
    from src.game import Game

    app = Game()
    sandbox = TestAISandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
