"""Interactive 3D proximity sensor sandbox.

Visual testbed for :class:`ProximitySensorHandler`:

- A stationary sensor marker at the origin, with the enter radius drawn in
  cyan and the exit (hysteresis) radius drawn in magenta
- A target cube orbiting the sensor, so it repeatedly enters, stays inside
  and leaves the sensed area while the telemetry shows the live state
- Keys to pause the orbit, disable the sensor and reset the phase
- Live OSD telemetry with state, distance, nearest entity and event counters,
  plus a periodic console line
- Clean teardown with zero dangling tasks or NodePaths
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from panda3d.core import LineSegs, NodePath

from src.entities.entity import Entity
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.handlers.sensors import ProximitySensorHandler
from src.ui import UIButton, UIColumn, UIPanel, UITheme

from ..__test import Test

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText


class TestProximitySandbox(Test):
    """Visual sandbox for distance-based sensing without physics."""

    ENTER_RADIUS = 4.0
    EXIT_RADIUS = 6.0
    ORBIT_RADIUS = 8.5
    ORBIT_SPEED = 0.55  # radians per second
    TARGET_HEIGHT = 0.75

    def __init__(self) -> None:
        super().__init__()
        self.base = GlobalLoader.get_instance().base

        self.sensor: Entity | None = None
        self.sensor_handler: ProximitySensorHandler | None = None
        self.target: Entity | None = None
        self.ground: Entity | None = None
        self._rings: list[NodePath] = []

        self._orbit_angle: float = 0.0
        self._orbiting: bool = True
        self.orbit_radius: float = float(self.ORBIT_RADIUS)
        self.orbit_speed: float = float(self.ORBIT_SPEED)
        self._enter_count: int = 0
        self._exit_count: int = 0
        self._last_inside: bool = False

        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._last_console_telemetry_time: float = 0.0
        self._console_interval: float = 1.0

        self._ui_components: list = []
        self._ui_theme = UITheme()

        self._task_name: str = "proximity_sandbox_update_task"

    # --- lifecycle -------------------------------------------------------

    def on_start(self) -> None:
        """Build the arena, the sensor, the orbiting target and the overlays."""
        self.print_title("Proximity Sensor Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()

        if self.base is None or getattr(self.base, "render", None) is None:
            self.p(
                "No graphics context available; the proximity sandbox needs a window.",
                color="yellow",
            )
            return

        self._setup_camera()
        self._build_environment()
        self._spawn_target()
        self._spawn_sensor()
        self._create_ring(self.ENTER_RADIUS, (0.2, 0.9, 1.0, 1.0))
        self._create_ring(self.EXIT_RADIUS, (0.95, 0.35, 0.95, 1.0))

        if hasattr(self.base, "accept"):
            self.base.accept("space", self._toggle_orbit)
            self.base.accept("l", self._toggle_sensor)
            self.base.accept("r", self._reset_phase)

        self._setup_osd()
        self._setup_ui()
        self._setup_inspector()
        self.add_task(self._task_name, self._on_frame_update)

    def _rebuild_rings(self, _val: Any = None) -> None:
        """Rebuild the cyan and magenta visual radius rings when sensor radii change."""
        for ring in self._rings:
            if not ring.isEmpty():
                ring.removeNode()
        self._rings.clear()
        enter_r = self.sensor_handler.radius if self.sensor_handler is not None else self.ENTER_RADIUS
        exit_r = (
            self.sensor_handler.exit_radius
            if self.sensor_handler is not None and self.sensor_handler.exit_radius is not None
            else self.EXIT_RADIUS
        )
        self._create_ring(enter_r, (0.2, 0.9, 1.0, 1.0))
        self._create_ring(exit_r, (0.95, 0.35, 0.95, 1.0))

    def _setup_inspector(self) -> None:
        """Register proximity sensor and orbit fields for live editing in the pause inspector."""
        self.expose_toggle(
            "Orbit Running (Space)",
            lambda: self._orbiting,
            lambda _v: self._toggle_orbit(),
        )
        if self.sensor_handler is not None:
            self.expose_toggle(
                "Sensor Enabled (L)",
                lambda: self.sensor_handler.is_enabled if self.sensor_handler else False,
                lambda _v: self._toggle_sensor(),
            )
            self.expose_field(
                "Enter Radius (m)",
                self.sensor_handler,
                "radius",
                1.0,
                14.0,
                0.5,
                on_change=self._rebuild_rings,
            )
            self.expose_field(
                "Exit Radius (m)",
                self.sensor_handler,
                "exit_radius",
                1.5,
                18.0,
                0.5,
                on_change=self._rebuild_rings,
            )
        self.expose_field("Orbit Radius (m)", self, "orbit_radius", 1.5, 14.0, 0.5)
        self.expose_field("Orbit Speed (rad/s)", self, "orbit_speed", 0.1, 3.0, 0.1)
        self.expose_action("Reset Phase (R)", self._reset_phase)

    def on_stop(self) -> None:
        """Remove tasks, listeners, overlays, rings, entities and lights."""
        self.print_subtitle("Proximity Sensor Sandbox stopping...")

        self.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            self.base.ignore("space")
            self.base.ignore("l")
            self.base.ignore("r")

        if self.osd_telemetry is not None:
            self.osd_telemetry.destroy()
            self.osd_telemetry = None
        if self.osd_instructions is not None:
            self.osd_instructions.destroy()
            self.osd_instructions = None

        for ring in self._rings:
            if not ring.isEmpty():
                ring.removeNode()
        self._rings.clear()

        for entity in (self.sensor, self.target, self.ground):
            if entity is not None:
                entity.free()

        self.sensor_handler = None
        self.sensor = None
        self.target = None
        self.ground = None

        for component in list(self._ui_components):
            try:
                component.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._ui_components.clear()

        if self.base is not None:
            GlobalLights.clear_lights()

        super().on_stop()

        self.p("Clean teardown completed: zero dangling nodes.", color="green")
        self.print_subtitle("Proximity Sensor Sandbox stopped.")

    def _print_controls_banner(self) -> None:
        """Print the startup banner with the sandbox controls and layout."""
        self.print_subtitle("Interactive Controls & Sensing Behaviour", color="yellow")
        self.p(
            " Controls:   SPACE: Pause/Resume orbit | L: Enable/Disable sensor | R: Reset phase",
            color="cyan",
            bold=True,
        )
        self.p(
            " Sensor:     pure distance observer; it never touches Bullet",
            color="green",
            bold=True,
        )
        self.p(
            f" Enter ring: {self.ENTER_RADIUS:.1f}m (cyan) | Exit ring: {self.EXIT_RADIUS:.1f}m (magenta, hysteresis)",
            color="green",
            bold=True,
        )
        self.p(
            " Target:     orbits automatically, so it repeatedly enters, stays and exits",
            color="green",
            bold=True,
        )
        self.p(
            " Predicate:  only the target is sensed; the ground and marker are filtered out",
            color="green",
            bold=True,
        )
        self.space_line()
        self.p("Arena Layout:", color="cyan", bold=True)
        self.p(" - The sensor marker sits at the origin, on a small platform", color="cyan")
        self.p(
            f" - The target orbits at {self.ORBIT_RADIUS:.1f}m, crossing both rings every lap",
            color="cyan",
        )
        self.p(
            " - Between the rings the target stays sensed: that is the hysteresis window",
            color="cyan",
        )
        self.space_line()

    # --- environment -----------------------------------------------------

    def _setup_camera(self) -> None:
        """Place a static camera that frames the whole orbit."""
        camera = getattr(self.base, "camera", None)
        if camera is None:
            return
        camera.setPos(0.0, -24.0, 16.0)
        camera.lookAt(0.0, 0.0, 0.0)

    def _attach_box_visual(
        self,
        parent: NodePath,
        name: str,
        size: tuple[float, float, float],
        color: tuple[float, float, float, float],
    ) -> NodePath:
        """Instance the cached box template under ``parent`` and style it.

        ``GlobalLoader`` returns the same cached NodePath on every call, so the
        template must be copied instead of reparented, or every entity would
        alias one node.
        """
        template = GlobalLoader.load_panda_asset("box")
        visual = parent.attachNewNode(name)
        template.copyTo(visual)
        visual.setScale(size[0], size[1], size[2])
        visual.setPos(-size[0] / 2.0, -size[1] / 2.0, -size[2] / 2.0)
        visual.setColor(*color)
        return visual

    def _build_environment(self) -> None:
        """Create the ground platform."""
        ground = Entity("Ground")
        ground.node.reparentTo(self.base.render)
        ground.node.setPos(0.0, 0.0, -0.25)
        self._attach_box_visual(
            ground.node,
            "ground_visual",
            (26.0, 26.0, 0.5),
            (0.22, 0.25, 0.28, 1.0),
        )
        self.ground = ground
        self.add_entity(ground)

    def _spawn_target(self) -> None:
        """Create the orbiting target entity."""
        target = Entity("Target")
        target.node.reparentTo(self.base.render)
        target.node.setPos(self.ORBIT_RADIUS, 0.0, self.TARGET_HEIGHT)
        self._attach_box_visual(
            target.node,
            "target_visual",
            (1.2, 1.2, 1.2),
            (0.95, 0.75, 0.20, 1.0),
        )
        self.target = target
        self.add_entity(target)

    def _spawn_sensor(self) -> None:
        """Create the sensor entity and attach the proximity handler."""
        sensor = Entity("Sensor")
        sensor.node.reparentTo(self.base.render)
        sensor.node.setPos(0.0, 0.0, 0.0)
        self._attach_box_visual(
            sensor.node,
            "sensor_visual",
            (1.0, 1.0, 1.0),
            (0.2, 0.9, 1.0, 1.0),
        )

        handler = ProximitySensorHandler(
            radius=self.ENTER_RADIUS,
            exit_radius=self.EXIT_RADIUS,
            scene=self,
            predicate=lambda entity: entity is self.target,
        )
        handler.on_enter.add_callback(self._on_enter)
        handler.on_exit.add_callback(self._on_exit)
        sensor.add_handler(handler)

        self.sensor = sensor
        self.sensor_handler = handler
        # Registration order only decides update order; the sensor reads the
        # scene registry, so any registration order sees the same entities.
        self.add_entity(sensor)

    def _create_ring(self, radius: float, color: tuple[float, float, float, float]) -> None:
        """Draw a horizontal ring at ``radius`` around the origin."""
        segments = LineSegs(f"ring_{radius:.1f}")
        segments.setThickness(2.0)
        segments.setColor(*color)
        steps = 96
        segments.moveTo(radius, 0.0, 0.04)
        for index in range(1, steps + 1):
            angle = 2.0 * math.pi * index / steps
            segments.drawTo(radius * math.cos(angle), radius * math.sin(angle), 0.04)
        ring = NodePath(segments.create())
        ring.reparentTo(self.base.render)
        self._rings.append(ring)

    # --- behaviour -------------------------------------------------------

    def _on_enter(self, entity: Entity, distance: float) -> None:
        """Count and announce an enter event."""
        self._enter_count += 1
        self.p(
            f"[Proximity] ENTER {entity.name} at {distance:.2f}m",
            color="green",
            bold=True,
        )

    def _on_exit(self, entity: Entity, distance: float) -> None:
        """Count and announce an exit event."""
        self._exit_count += 1
        self.p(
            f"[Proximity] EXIT {entity.name} at {distance:.2f}m",
            color="magenta",
            bold=True,
        )

    def _toggle_orbit(self) -> None:
        """Pause or resume the automatic orbit."""
        self._orbiting = not self._orbiting
        state = "RUNNING" if self._orbiting else "PAUSED"
        self.p(f"[Proximity] Orbit {state}", color="yellow", bold=True)
        self.record_replay_event("action", name="toggle_orbit")

    def _toggle_sensor(self) -> None:
        """Enable or disable the sensor handler."""
        handler = self.sensor_handler
        if handler is None:
            return
        handler.set_enabled(not handler.is_enabled)
        state = "ENABLED" if handler.is_enabled else "DISABLED"
        self.p(f"[Proximity] Sensor {state}", color="yellow", bold=True)
        self.record_replay_event("action", name="toggle_sensor")

    def _reset_phase(self) -> None:
        """Reset the target to the right side of the orbit and clear counters."""
        self._orbit_angle = 0.0
        self._enter_count = 0
        self._exit_count = 0
        self._last_inside = False
        if self.sensor_handler is not None:
            self.sensor_handler.clear()
        if self.target is not None:
            self.target.node.setPos(self.ORBIT_RADIUS, 0.0, self.TARGET_HEIGHT)
        self.p("[Proximity] Phase reset", color="yellow", bold=True)
        self.record_replay_event("action", name="reset_phase")

    # --- frame update ----------------------------------------------------

    def _on_frame_update(self, task: Any) -> int:
        """Advance the orbit, then refresh the telemetry."""
        dt = self._replay_dt() if self._replay_mode is not None else float(task.dt or (1.0 / 60.0))
        if self._replay_mode is not None:
            self._replay_elapsed += dt
            if self._replay_mode == "record" and self._replay_recorder is not None:
                self._replay_recorder.tick(dt)
            elif self._replay_mode == "replay" and self._replay_player is not None:
                self._replay_player.tick(dt, self)

        if self._orbiting and self.target is not None and not self.target.is_freed:
            self._orbit_angle += self.orbit_speed * dt
            self._orbit_angle %= 2.0 * math.pi
            self.target.node.setPos(
                self.orbit_radius * math.cos(self._orbit_angle),
                self.orbit_radius * math.sin(self._orbit_angle),
                self.TARGET_HEIGHT,
            )

        self._update_osd(task.time)
        if self._replay_mode is not None and self._replay_elapsed >= self._replay_duration:
            self.finalize_replay()
            import builtins

            base = getattr(builtins, "base", None)
            if base is not None and hasattr(base, "userExit"):
                base.userExit()
            return task.done
        return task.cont

    def _update_osd(self, current_time: float) -> None:
        """Update the OSD telemetry and print a periodic console line."""
        handler = self.sensor_handler
        inside = handler is not None and bool(handler.sensed_entities)
        if inside != self._last_inside:
            self._last_inside = inside
            self.p(
                f"[Proximity] State -> {'INSIDE' if inside else 'OUTSIDE'}",
                color="cyan",
                bold=True,
            )

        distance: float | None = None
        if handler is not None and self.target is not None:
            distance = handler.distance_to(self.target)
        nearest = handler.nearest if handler is not None else None
        nearest_name = nearest.name if nearest is not None else "-"
        enabled = "ON" if handler is not None and handler.is_enabled else "OFF"
        orbiting = "RUNNING" if self._orbiting else "PAUSED"
        distance_text = f"{distance:5.2f}m" if distance is not None else "  ?  "

        if self.osd_telemetry is not None:
            self.osd_telemetry.setText(
                f"Sensor: {enabled:<3} | Orbit: {orbiting:<8} | dist: {distance_text} | "
                f"state: {'INSIDE ' if inside else 'OUTSIDE'}\n"
                f"Nearest: {nearest_name:<12} | sensed: {len(handler.sensed_entities) if handler else 0} | "
                f"enter: {self._enter_count} | exit: {self._exit_count}"
            )

        if current_time - self._last_console_telemetry_time >= self._console_interval:
            self._last_console_telemetry_time = current_time
            self.p(
                f"[Proximity] enabled={enabled} | orbit={orbiting} | dist={distance_text} | "
                f"inside={inside} | nearest={nearest_name} | enter={self._enter_count} | "
                f"exit={self._exit_count}",
                color="blue",
            )

    def capture_replay_state(self) -> dict:
        handler = self.sensor_handler
        phase = "orbiting" if self._orbiting else "paused"
        self._replay_phase = phase
        return {
            "orbit_angle": round(self._orbit_angle, 6),
            "orbiting": bool(self._orbiting),
            "orbit_radius": float(self.orbit_radius),
            "orbit_speed": float(self.orbit_speed),
            "sensor_enabled": bool(handler.is_enabled) if handler is not None else False,
            "enter_count": int(self._enter_count),
            "exit_count": int(self._exit_count),
            "last_inside": bool(self._last_inside),
        }

    def apply_replay_event(self, event: dict) -> None:
        if event.get("type") != "action":
            return
        name = event.get("name")
        if name == "toggle_orbit":
            self._toggle_orbit()
        elif name == "toggle_sensor":
            self._toggle_sensor()
        elif name == "reset_phase":
            self._reset_phase()

    def _replay_dt(self) -> float:
        if self._replay_mode is not None and self._replay_recorder is not None:
            return float(self._replay_recorder.fixed_dt)
        if self._replay_mode is not None and self._replay_player is not None:
            return float(self._replay_player.fixed_dt)
        try:
            import builtins

            base = getattr(builtins, "base", None)
            if base is not None and hasattr(base, "globalClock"):
                return float(base.globalClock.getDt())
        except Exception:  # noqa: BLE001
            pass
        return 1.0 / 60.0

    def _setup_ui(self) -> None:
        """Create reusable UI controls for the sandbox."""
        if self.base is None or getattr(self.base, "aspect2d", None) is None:
            return
        try:
            panel = UIPanel(
                parent=self.base.aspect2d,
                title="Controls",
                width=0.42,
                height=0.42,
                theme=self._ui_theme,
                owner=self,
                pos=(-1.05, 0.0, -0.55),
            )
            column = UIColumn(parent=panel.content_parent, spacing=0.02, owner=self, pos=(0.0, 0.05))
            column.add(
                UIButton(
                    parent=column.node,
                    text="Space: Pause",
                    command=self._toggle_orbit,
                    theme=self._ui_theme,
                    owner=self,
                    scale=0.05,
                )
            )
            column.add(
                UIButton(
                    parent=column.node,
                    text="L: Toggle Sensor",
                    command=self._toggle_sensor,
                    theme=self._ui_theme,
                    owner=self,
                    scale=0.05,
                )
            )
            column.add(
                UIButton(
                    parent=column.node,
                    text="R: Reset Phase",
                    command=self._reset_phase,
                    theme=self._ui_theme,
                    owner=self,
                    scale=0.05,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.p(f"UI not available ({exc}); skipping controls.", color="yellow")

    def _setup_osd(self) -> None:
        """Create the controls reminder and the live telemetry overlay."""
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text="SPACE: Pause Orbit | L: Toggle Sensor | R: Reset Phase | Esc/P: Pause & Inspector",
                pos=(-1.28, 0.92),
                scale=0.045,
                fg=(1.0, 1.0, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=False,
            )
            self.osd_telemetry = OnscreenText(
                text="Initializing proximity telemetry...",
                pos=(-1.28, 0.83),
                scale=0.042,
                fg=(0.2, 0.9, 1.0, 1.0),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except Exception as exc:  # OSD is optional in constrained environments  # noqa: BLE001
            self.p(
                f"OSD not available ({exc}); skipping telemetry overlay.",
                color="yellow",
            )
            self.osd_instructions = None
            self.osd_telemetry = None


if __name__ == "__main__":
    import argparse
    import sys

    from src.game import Game

    parser = argparse.ArgumentParser(description="Proximity Sensor Sandbox")
    parser.add_argument("--record", metavar="PATH", help="Record a replay to PATH.")
    parser.add_argument("--replay", metavar="PATH", help="Replay a recorded scenario from PATH.")
    parser.add_argument("--duration", type=float, default=5.0, help="Replay/record duration in seconds.")
    args = parser.parse_args()

    app = Game()
    sandbox = TestProximitySandbox()
    sandbox._replay_scene_name = "proximity_state"
    if args.record:
        sandbox.enable_replay_record(args.record, duration=args.duration)
    elif args.replay:
        sandbox.enable_replay_replay(args.replay, duration=args.duration)
    app.add_scene(sandbox, set_as_main=True)
    app.run()
    sys.exit(getattr(sandbox, "_replay_exit_code", 0))
