"""Mini-game sandbox demonstrating the prefab API.

Builds a tiny playable scene in ~40 lines using ``src.prefabs`` instead of
hand-composing handlers. Compare with ``character_sandbox.py``.
"""

from __future__ import annotations

from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3

from ..__test import Test
from src.entities.entity import Entity
from src.globals.lights import GlobalLights
from src.globals.physics import Physics
from src.prefabs import create_player, create_patrol_npc, create_static_prop


class TestMiniGameSandbox(Test):
    def __init__(self) -> None:
        super().__init__()
        self.base = Physics.get_instance().base
        self.player = None
        self.npcs = []

    def on_start(self) -> None:
        self.print_title("Mini-Game Sandbox (prefabs)", color="cyan")
        super().on_start()
        GlobalLights.setup_default_lights()
        self._build_ground()
        self._spawn_entities()

    def _build_ground(self) -> None:
        body = Physics.create_body("ground", mass=0.0)
        body.addShape(BulletBoxShape(Vec3(30.0, 30.0, 0.25)))
        np = self.base.render.attachNewNode(body)
        np.setPos(0.0, 0.0, -0.25)
        Physics.get_world().attachRigidBody(body)

    def _spawn_entities(self) -> None:
        rig = create_player(position=(0.0, 0.0, 2.0))
        self.player = rig.entity
        self.player.node.reparentTo(self.base.render)
        self.add_entity(self.player)

        waypoints = [Vec3(5.0, 5.0, 0.0), Vec3(-5.0, 5.0, 0.0)]
        npc = create_patrol_npc(waypoints=waypoints, position=(5.0, 5.0, 0.0))
        npc.entity.node.reparentTo(self.base.render)
        self.add_entity(npc.entity)
        self.npcs.append(npc)

        prop = create_static_prop(
            model_path="models/box",
            from_assets=False,
            position=(3.0, 0.0, 0.5),
            scale=1.0,
            offset=Vec3(-0.5, -0.5, -0.5),
            shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
        )
        prop.node.reparentTo(self.base.render)
        self.add_entity(prop)

    def on_stop(self) -> None:
        self.print_subtitle("Mini-Game Sandbox stopped.")


if __name__ == "__main__":
    from src.game import Game

    app = Game()
    sandbox = TestMiniGameSandbox()
    app.add_scene(sandbox, set_as_main=True)
    app.run()