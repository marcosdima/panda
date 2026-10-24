"""Interactive 3D Animation Blending sandbox.

Demonstrates smooth crossfading between locomotion animations (Idle/Walk/Run/Jump)
using ActorAnimationHandler with blending enabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec3

from ..__test import Test
from src.globals.lights import GlobalLights
from src.globals.loader import GlobalLoader
from src.globals.physics import Physics
from src.prefabs.common import create_player

if TYPE_CHECKING:
    from direct.gui.OnscreenText import OnscreenText


class TestAnimationBlendSandbox(Test):
    """Visual sandbox to evaluate animation blending transitions."""

    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base

        self.player_rig = None
        self.osd_instructions: OnscreenText | None = None
        self.osd_telemetry: OnscreenText | None = None
        self._task_name: str = "animation_blend_sandbox_update_task"

        self.static_bodies: list[str] = []
        self.static_nodes: list[NodePath] = []

    def on_start(self) -> None:
        self.print_title("Animation Blending Sandbox", color="cyan")
        self._print_controls_banner()

        super().on_start()
        GlobalLights.setup_default_lights()

        if self.base is None or getattr(self.base, "render", None) is None:
            self.p("No graphics context available; animation blend sandbox needs a window.", color="yellow")
            return

        self._build_environment()
        self._spawn_player()

        if self.base is not None and hasattr(self.base, "accept"):
            self.base.accept("f12", self._toggle_physics_debug)

        self._setup_osd()
        self.add_task(self._task_name, self._on_frame_update)

    def _print_controls_banner(self) -> None:
        self.print_subtitle("Controls", color="yellow")
        self.p(" Move:      WASD / Arrows", color="green")
        self.p(" Jump:      Space", color="green")
        self.p(" Sprint:    Left Shift", color="green")
        self.p(" Mouse:     Look around", color="green")
        self.p(" Zoom:      Mouse Wheel", color="green")
        self.p(" Wireframe: F12", color="magenta")
        self.space_line()
        self.p("Testing smooth crossfades between Idle/Walk/Run/Jump", color="cyan", bold=True)
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
            size=(80.0, 80.0, 0.5),
            color=(0.24, 0.27, 0.30, 1.0),
        )
        self._create_static_box(
            name="platform1",
            pos=(10.0, 5.0, 0.5),
            size=(4.0, 4.0, 1.0),
            color=(0.35, 0.40, 0.45, 1.0),
        )
        self._create_static_box(
            name="ramp",
            pos=(0.0, -10.0, 0.25),
            size=(3.0, 6.0, 0.1),
            color=(0.40, 0.45, 0.50, 1.0),
        )

    def _spawn_player(self) -> None:
        parent = None
        if self.base is not None and hasattr(self.base, "render"):
            parent = self.base.render
        self.player_rig = create_player(
            scene=self,
            name="BlendDemoPlayer",
            model="Knight",
            camera="third_person",
            position=(0.0, 0.0, 2.0),
            parent=parent,
            animation_kwargs={"blend_duration": 0.25},
            camera_kwargs={"distance": 8.0, "target_offset": Vec3(0.0, 0.0, 2.0)},
        )

    def _setup_osd(self) -> None:
        try:
            from direct.gui.OnscreenText import OnscreenText
            from panda3d.core import TextNode

            self.osd_instructions = OnscreenText(
                text=(
                    "WASD Move | Space Jump | LShift Sprint | F12 Wireframe\n"
                    "Move/stop/run/jump to see smooth blends"
                ),
                pos=(-1.3, 0.9),
                scale=0.05,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )
            self.osd_telemetry = OnscreenText(
                text="Animation: -",
                pos=(-1.3, -0.9),
                scale=0.05,
                fg=(1, 1, 1, 1),
                align=TextNode.ALeft,
                mayChange=True,
            )
        except Exception:
            self.osd_instructions = None
            self.osd_telemetry = None

    def _on_frame_update(self, task):
        try:
            if self.player_rig is not None and self.player_rig.animation is not None and self.osd_telemetry is not None:
                anim_name = getattr(self.player_rig.animation, "current_animation", None)
                state = getattr(self.player_rig.animation.locomotion, "state", None)
                blending = getattr(self.player_rig.animation, "_blend_active", False)
                self.osd_telemetry.setText(f"State: {state} | Anim: {anim_name} | Blending: {blending}")
        except Exception:
            pass
        return task.cont

    def _toggle_physics_debug(self) -> None:
        try:
            Physics.get_instance().toggle_debug()
        except Exception:
            try:
                if self.base is not None and hasattr(self.base, "toggleBulletDebug"):
                    self.base.toggleBulletDebug()
            except Exception:
                pass

    def on_stop(self) -> None:
        self.print_subtitle("Animation Blending Sandbox stopping...")
        self.remove_task(self._task_name)

        if self.base is not None and hasattr(self.base, "ignore"):
            try:
                self.base.ignore("f12")
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

        if self.player_rig is not None and getattr(self.player_rig, "entity", None) is not None:
            try:
                self.player_rig.entity.free()
            except Exception:
                try:
                    self.remove_entity(self.player_rig.entity)
                except Exception:
                    pass
        self.player_rig = None

        super().on_stop()


if __name__ == "__main__":
    from src import game
    from tests import Tests

    app = game.Game()
    test = Tests().get_target()
    if test is not None:
        app.add_scene(test, set_as_main=True)
    app.run()
