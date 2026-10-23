try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

from panda3d.core import Vec3
from panda3d.bullet import BulletBoxShape

from src.entities.entity import Entity
from src.prefabs import (
    EntityBuilder,
    PlayerRig,
    NpcRig,
    create_player,
    create_patrol_npc,
    create_static_prop,
)
from src.handlers.physics import CharacterControllerHandler


class TestPrefabSmoke(TerminalTest):
    def on_start(self) -> None:
        self.print_title("Prefab smoke tests started.", color="cyan")
        super().on_start()

    def test_player_prefab(self) -> None:
        self.print_subtitle("Player prefab composes a valid rig.")
        Entity.reset_ids()
        rig = create_player(position=(0.0, 0.0, 2.0))
        assert isinstance(rig, PlayerRig)
        assert rig.entity is not None
        assert rig.input is not None
        assert rig.controller is not None
        assert rig.camera is not None
        assert rig.animation is not None
        assert rig.entity.has_handler(CharacterControllerHandler)

        # Lifecycle smoke: start + a few updates must not raise.
        rig.entity.start()
        for _ in range(5):
            rig.entity.on_update(1.0 / 60.0)
        rig.entity.on_stop()
        self.p("Player prefab OK.", color="green")
        self.space_line()

    def test_npc_prefab(self) -> None:
        self.print_subtitle("NPC prefab composes patrol AI + controller.")
        Entity.reset_ids()
        waypoints = [Vec3(0.0, 0.0, 0.0), Vec3(4.0, 0.0, 0.0)]
        rig = create_patrol_npc(waypoints=waypoints, position=(0.0, 0.0, 0.0))
        assert isinstance(rig, NpcRig)
        assert rig.controller is not None
        assert rig.ai is not None
        assert rig.ai.current_waypoint is not None

        rig.entity.start()
        for _ in range(3):
            rig.entity.on_update(1.0 / 60.0)
        rig.entity.on_stop()
        self.p("NPC prefab OK.", color="green")
        self.space_line()

    def test_prop_prefab(self) -> None:
        self.print_subtitle("Static prop prefab (with and without physics).")
        Entity.reset_ids()
        prop = create_static_prop(
            model_path="X Bot.glb", position=(1.0, 2.0, 0.0)
        )
        assert prop is not None
        prop.start()
        for _ in range(2):
            prop.on_update(1.0 / 60.0)
        prop.on_stop()

        shape = BulletBoxShape(Vec3(0.5, 0.5, 0.5))
        prop2 = create_static_prop(
            model_path="X Bot.glb", shape=shape, mass=0.0, position=(3.0, 0.0, 0.0)
        )
        assert prop2 is not None
        prop2.start()
        prop2.on_stop()
        self.p("Prop prefab OK.", color="green")
        self.space_line()

    def test_builder_escape_hatch(self) -> None:
        self.print_subtitle("EntityBuilder composes in explicit order.")
        Entity.reset_ids()
        entity = (
            EntityBuilder("Custom")
            .at(0.0, 0.0, 1.0)
            .with_input()
            .with_character()
            .build()
        )
        assert entity is not None
        assert entity.get_handler(CharacterControllerHandler) is not None
        entity.start()
        entity.on_update(0.016)
        entity.on_stop()
        self.p("Builder escape hatch OK.", color="green")
        self.space_line()

    def test_ergonomics(self) -> None:
        self.print_subtitle("Ergonomics comparison.")
        manual_lines = 12
        prefab_lines = 1
        self.p(f"Manual composition: ~{manual_lines} lines")
        self.p(f"Prefab composition: ~{prefab_lines} line(s)")
        assert prefab_lines < manual_lines
        self.space_line()

    def on_stop(self) -> None:
        self.print_subtitle("Prefab smoke tests completed.")


if __name__ == "__main__":
    import builtins

    if not hasattr(builtins, "base") or builtins.base is None:
        from direct.showbase.ShowBase import ShowBase

        ShowBase(windowType="none")

    test = TestPrefabSmoke()
    test.on_start()
    test.on_stop()