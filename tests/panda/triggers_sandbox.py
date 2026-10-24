"""Interactive 3D Trigger Zones sandbox.

Provides a physical test course featuring:
- Static ground and pillars built with RigidBodyHandler entities
- Player character entity driven by WASDInputHandler and CharacterControllerHandler
  with CollisionGroup.PLAYER
- Oscillating enemy box (static RigidBodyHandler, CollisionGroup.ENEMY) moved through
  entity.node every frame to exercise transform auto-sync
- Three translucent trigger volumes wired to TriggerZoneHandler events:
  - Blue zone at (0, 0, 1.1): accepts PLAYER entities (walk in/out)
  - Red zone at (0, 8, 1.1): accepts ENEMY entities (swept automatically)
  - Yellow zone at (0, -6, 1.1): accepts ENEMY only (player entry is rejected)
- Live enter/stay/exit/rejected counters on OSD and terminal, F12 Bullet wireframe
- Clean teardown with zero dangling physics bodies or node leaks
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, TransparencyAttrib, Vec3

from ..__test import Test
from src.entities.entity import Entity
from src.handlers.camera import ThirdPersonCameraHandler
from src.handlers.input.wasd import WASDInputHandler
from src.handlers.physics import (
    CharacterControllerHandler,
    CollisionGroup,
    RigidBodyHandler,
    TriggerZoneHandler,
)

from src.globals.clock import GlobalClock
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText


class TestTriggersSandbox(Test):
    """Interactive visual 3D sandbox scene for evaluating trigger zone and rigid body handlers."""

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        self.player: Entity | None = None
        self.controller: CharacterControllerHandler | None = None
        self.input_handler: WASDInputHandler | None = None
        self.camera_handler: ThirdPersonCameraHandler | None = None

        self.enemy: Entity | None = None
        self.enemy_rigid: RigidBodyHandler | None = None
        self._enemy_time: float = 0.0
        self.enemy_sweep_amplitude: float = 6.0
        self.enemy_sweep_period: float = 8.0

        self.zone_entities: list[Entity] = []
        self.zone_handlers: list[TriggerZoneHandler] = []
        self.static_entities: list[Entity] = []

        self._counters: dict[str, dict[str, int]] = {
            "zone_player": {"enter": 0, "stay": 0, "exit": 0, "rejected": 0},
            "zone_enemy": {"enter": 0, "stay": 0, "exit": 0, "rejected": 0},
            "zone_reject": {"enter": 0, "stay": 0, "exit": 0, "rejected": 0},
        }
        self._frame_count: int = 0
        self._last_rejected_frame: int = -1000

        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._last_console_telemetry_time: float = 0.0
        self._console_interval: float = 1.0

        self._task_name: str = "triggers_sandbox_update_task"

    def on_start(self) -> None:
        """Initialize environment, entities, zones, controls, and telemetry."""
        self.print_title("Trigger Zones Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()

        self._build_environment()
        self._spawn_player()
        self._spawn_enemy()
        self._spawn_zones()

        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)

        self._setup_osd()
        self._setup_inspector()
        self.add_task(self._task_name, self._on_frame_update)

    def _setup_inspector(self) -> None:
        """Register enemy oscillator and player parameters for live editing in the pause inspector."""
        self.expose_field("Enemy Sweep Amp (m)", self, "enemy_sweep_amplitude", 0.0, 12.0, 0.5)
        self.expose_field("Enemy Sweep Period (s)", self, "enemy_sweep_period", 1.0, 20.0, 0.5)

    def _print_controls_banner(self) -> None:
        """Print formatted ANSI startup banner with control and zone instructions."""
        self.print_subtitle("Interactive Controls & Trigger Events", color="yellow")
        self.p(" Controls:   WASD: Move | SPACE: Jump | Mouse: Look | F12: Wireframe", color="cyan", bold=True)
        self.p(" Movement:   [W, A, S, D] or Arrow Keys", color="green", bold=True)
        self.p(" Look:       [Mouse] Look | [Tab/Esc] Cursor | [Mouse Wheel] Zoom", color="green", bold=True)
        self.p(" Wireframe:  [F12] Toggle Bullet debug visualization", color="magenta", bold=True)

        self.space_line()
        self.p("Trigger Layout:", color="cyan", bold=True)
        self.p(" - Blue zone at (0, 0, 1.1): accepts PLAYER, walk in and out", color="cyan")
        self.p(" - Red zone at (0, 8, 1.1): accepts ENEMY, red box sweeps through it", color="cyan")
        self.p(" - Yellow zone at (0, -6, 1.1): accepts ENEMY only, walking in as player is REJECTED", color="yellow")
        self.p(" - Counters update live on OSD and print to the terminal", color="cyan")
        self.space_line()

    def _create_static_box(
        self,
        name: str,
        pos: tuple[float, float, float] | Vec3,
        size: tuple[float, float, float] | Vec3,
        color: tuple[float, float, float, float] = (0.7, 0.7, 0.7, 1.0),
    ) -> Entity:
        """Create a static RigidBodyHandler entity with perfectly aligned visual box geometry."""
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
        """Build the static testing arena: ground and flanking pillars."""
        self._create_static_box(
            name="ground",
            pos=(0.0, 0.0, -0.25),
            size=(60.0, 60.0, 0.5),
            color=(0.24, 0.27, 0.30, 1.0),
        )
        self._create_static_box(
            name="pillar_left_front",
            pos=(-6.0, 4.0, 1.5),
            size=(1.0, 1.0, 3.0),
            color=(0.45, 0.50, 0.55, 1.0),
        )
        self._create_static_box(
            name="pillar_right_front",
            pos=(6.0, 4.0, 1.5),
            size=(1.0, 1.0, 3.0),
            color=(0.45, 0.50, 0.55, 1.0),
        )
        self._create_static_box(
            name="pillar_left_back",
            pos=(-6.0, 12.0, 1.5),
            size=(1.0, 1.0, 3.0),
            color=(0.45, 0.50, 0.55, 1.0),
        )
        self._create_static_box(
            name="pillar_right_back",
            pos=(6.0, 12.0, 1.5),
            size=(1.0, 1.0, 3.0),
            color=(0.45, 0.50, 0.55, 1.0),
        )

    def _spawn_player(self) -> None:
        """Spawn the player Entity with WASD input, camera, character controller, and visual."""
        player = Entity("TriggerPlayer")
        player.node.reparentTo(self.base.render)
        player.node.setPos(0.0, -2.0, 2.0)

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
            collision_group=CollisionGroup.PLAYER,
        )

        player.add_handler(self.input_handler)
        player.add_handler(self.camera_handler)
        player.add_handler(self.controller)

        if self.controller.controller_np is not None and not self.controller.controller_np.isEmpty():
            self._attach_box_visual(
                self.controller.controller_np,
                "player_visual",
                (0.9, 0.9, 1.9),
                (0.2, 0.9, 0.3, 1.0),
            )

        self.player = player
        self.add_entity(player)

    def _spawn_enemy(self) -> None:
        """Spawn the oscillating enemy Entity as a static ENEMY-group rigid body."""
        enemy = Entity("EnemyMover")
        enemy.node.reparentTo(self.base.render)
        enemy.node.setPos(0.0, 8.0, 0.5)
        self.enemy_rigid = enemy.add_handler(
            RigidBodyHandler(
                shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
                mass=0.0,
                collision_group=CollisionGroup.ENEMY,
            )
        )
        self._attach_box_visual(
            enemy.node,
            "enemy_visual",
            (1.0, 1.0, 1.0),
            (0.9, 0.2, 0.2, 1.0),
        )

        self.enemy = enemy
        self.add_entity(enemy)

    def _spawn_zones(self) -> None:
        """Create the three translucent trigger zone entities and wire their events."""
        self._spawn_zone(
            name="ZonePlayer",
            pos=(0.0, 0.0, 1.1),
            color=(0.2, 0.6, 1.0, 0.35),
            targets={CollisionGroup.PLAYER},
            label="zone_player",
        )
        self._spawn_zone(
            name="ZoneEnemy",
            pos=(0.0, 8.0, 1.1),
            color=(1.0, 0.35, 0.25, 0.35),
            targets={CollisionGroup.ENEMY},
            label="zone_enemy",
        )
        self._spawn_zone(
            name="ZoneReject",
            pos=(0.0, -6.0, 1.1),
            color=(1.0, 0.9, 0.2, 0.35),
            targets={CollisionGroup.ENEMY},
            label="zone_reject",
        )

    def _spawn_zone(
        self,
        name: str,
        pos: tuple[float, float, float],
        color: tuple[float, float, float, float],
        targets: set[CollisionGroup],
        label: str,
    ) -> None:
        """Create one trigger zone entity with a translucent visual and wired counters."""
        zone = Entity(name)
        zone.node.reparentTo(self.base.render)
        zone.node.setPos(*pos)
        handler = zone.add_handler(
            TriggerZoneHandler(
                shape=BulletBoxShape(Vec3(1.0, 1.0, 1.0)),
                target_groups=set(targets),
            )
        )
        self._attach_box_visual(
            zone.node,
            f"{name}_visual",
            (2.0, 2.0, 2.0),
            color,
            translucent=True,
        )
        self._wire_zone(label, handler)
        self.zone_entities.append(zone)
        self.zone_handlers.append(handler)
        self.add_entity(zone)

    def _wire_zone(self, label: str, handler: TriggerZoneHandler) -> None:
        """Register counter callbacks on all four events of the given zone handler."""
        handler.on_enter.add_callback(self._make_counter(label, "enter"))
        handler.on_stay.add_callback(self._make_counter(label, "stay"))
        handler.on_exit.add_callback(self._make_counter(label, "exit"))
        handler.on_rejected.add_callback(self._make_counter(label, "rejected"))

    def _make_counter(self, label: str, kind: str) -> Callable[[Entity], None]:
        """Build a callback counting events per zone, printing edge events to the terminal."""

        def _callback(entity: Entity) -> None:
            self._counters[label][kind] += 1
            if kind == "enter":
                self.p(f"[{label}] ENTER: {entity.name}", color="green")
            elif kind == "exit":
                self.p(f"[{label}] EXIT: {entity.name}", color="yellow")
            elif kind == "rejected" and self._frame_count - self._last_rejected_frame >= 60:
                self._last_rejected_frame = self._frame_count
                self.p(f"[{label}] REJECTED: {entity.name} (group filter)", color="magenta")

        return _callback

    def _toggle_physics_debug(self) -> None:
        """Toggle Bullet physics debug wireframe and notify via console."""
        active = Physics.toggle_debug()
        state = "ENABLED" if active else "DISABLED"
        self.p(f"[Physics Debug] Bullet Wireframe {state}", color="cyan", bold=True)

    def _on_frame_update(self, task: Any) -> int:
        """Per-frame update driving the enemy oscillator, scene entities, and telemetry."""
        dt = GlobalClock.get_dt() if hasattr(GlobalClock, "get_dt") else 0.016
        self._frame_count += 1

        if self.enemy is not None and not self.enemy.is_freed:
            self._enemy_time += dt
            period = max(0.5, float(self.enemy_sweep_period))
            x = float(self.enemy_sweep_amplitude) * math.sin(math.tau * self._enemy_time / period)
            self.enemy.node.setPos(x, 8.0, 0.5)

        self._update_osd(task.time)
        return task.cont

    def _update_osd(self, current_time: float) -> None:
        """Update live counters on OSD and periodic console logs."""
        wireframe = "ON" if Physics.is_debug_enabled() else "OFF"
        player_c = self._counters["zone_player"]
        enemy_c = self._counters["zone_enemy"]
        reject_c = self._counters["zone_reject"]

        if self.osd_telemetry is not None:
            self.osd_telemetry.setText(
                f"zone_player  (PLAYER): enter={player_c['enter']:<5} stay={player_c['stay']:<6} exit={player_c['exit']:<5}\n"
                f"zone_enemy   (ENEMY):  enter={enemy_c['enter']:<5} stay={enemy_c['stay']:<6} exit={enemy_c['exit']:<5}\n"
                f"zone_reject  (ENEMY):  rejected={reject_c['rejected']:<6} | Debug: {wireframe}"
            )

        if current_time - self._last_console_telemetry_time >= self._console_interval:
            self._last_console_telemetry_time = current_time
            self.p(
                f"[Counters] player(E/S/X)={player_c['enter']}/{player_c['stay']}/{player_c['exit']} | "
                f"enemy(E/S/X)={enemy_c['enter']}/{enemy_c['stay']}/{enemy_c['exit']} | "
                f"rejected={reject_c['rejected']} | Wireframe={wireframe}",
                color="blue",
            )

    def _setup_osd(self) -> None:
        """Create on-screen text overlays for controls reminder and live counters."""
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="WASD: Move | SPACE: Jump | Mouse: Look | Esc/P: Pause & Inspector | F12: Wireframe",
                pos=(-1.28, 0.92),
                scale=0.045,
                fg=(1.0, 1.0, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=False,
            )

            self.osd_telemetry = OnscreenText(
                text="Initializing Counters...",
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

    def on_stop(self) -> None:
        """Clean teardown: remove tasks, listeners, entities, nodes, and lights."""
        self.print_subtitle("Trigger Zones Sandbox stopping...")

        self.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            self.base.ignore("f12")

        if self.osd_telemetry is not None:
            self.osd_telemetry.destroy()
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            self.osd_instructions.destroy()
            self.osd_instructions = None

        entities = [self.player, self.enemy, *self.zone_entities, *self.static_entities]
        for entity in entities:
            if entity is not None:
                entity.free()
        self.zone_entities.clear()
        self.static_entities.clear()
        self.zone_handlers.clear()
        self.enemy = None
        self.enemy_rigid = None
        self.player = None
        self.controller = None
        self.input_handler = None
        self.camera_handler = None

        GlobalLights.clear_lights()

        super().on_stop()

        self.p("Clean teardown completed: zero dangling physics bodies.", color="green")
        self.print_subtitle("Trigger Zones Sandbox stopped.")


if __name__ == "__main__":
    from src.game import Game

    app = Game()
    sandbox = TestTriggersSandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
