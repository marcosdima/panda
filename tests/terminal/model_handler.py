try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

import builtins
from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.globals.loader import GlobalLoader
from src.handlers.graphics.model import ModelHandler


class TestModelHandler(TerminalTest):
    """Terminal test suite for ModelHandler static geometry loading and lifecycle."""

    def on_start(self) -> None:
        self.print_title("TestModelHandler started.", color="cyan")
        super().on_start()

    def test_model_handler_parameters(self) -> None:
        self.print_subtitle("Testing ModelHandler default & custom parameters.")
        handler = ModelHandler(model_path="props/box.glb")

        assert handler.model_path == "props/box.glb"
        assert handler.scale == 1.0
        assert handler.offset == Vec3(0.0, 0.0, 0.0)
        assert handler.hpr == Vec3(0.0, 0.0, 0.0)
        assert handler.from_assets is True
        assert handler.model_np is None

        custom = ModelHandler(
            model_path="levels/arena.glb",
            scale=2.5,
            offset=Vec3(1.0, -2.0, 0.5),
            hpr=Vec3(90.0, 0.0, 45.0),
            from_assets=False,
        )
        assert custom.scale == 2.5
        assert custom.offset == Vec3(1.0, -2.0, 0.5)
        assert custom.hpr == Vec3(90.0, 0.0, 45.0)
        assert custom.from_assets is False

        self.p("ModelHandler parameters verified successfully.", color="green")
        self.space_line()

    def test_model_attachment_and_transform(self) -> None:
        self.print_subtitle("Testing ModelHandler entity attachment and transform application.")
        entity = Entity("StaticPropHero")
        handler = ModelHandler(
            model_path="box",
            from_assets=False,
            scale=3.0,
            offset=Vec3(0.0, 0.0, 1.0),
            hpr=Vec3(45.0, 0.0, 0.0),
        )
        entity.add_handler(handler)
        assert entity.get_handler(ModelHandler) is handler

        # Model instance exists, parented to entity.node with transforms applied
        assert handler.model_np is not None
        assert not handler.model_np.isEmpty()
        assert handler.model_np.getParent() == entity.node
        assert handler.model_np.getScale() == Vec3(3.0, 3.0, 3.0)
        assert handler.model_np.getPos() == Vec3(0.0, 0.0, 1.0)
        assert handler.model_np.getHpr() == Vec3(45.0, 0.0, 0.0)

        # Instance is a deep copy: it must not share nodes with the cached template
        template = GlobalLoader.load("models/box")
        assert handler.model_np.getNode(0) is not template.getNode(0)

        entity.start()
        entity.update(0.016)

        entity.stop()
        entity.remove_handler(handler)
        assert entity.get_handler(ModelHandler) is None
        assert handler.entity is None

        entity.free()
        self.p("ModelHandler attachment and transform verified successfully.", color="green")
        self.space_line()

    def test_template_caching_and_distinct_instances(self) -> None:
        self.print_subtitle("Testing GlobalLoader template caching and per-entity instances.")
        template_a = GlobalLoader.load("models/box")
        template_b = GlobalLoader.load("models/box")
        assert template_a is template_b, "GlobalLoader must return the same cached template."

        entity_a = Entity("PropA")
        entity_b = Entity("PropB")
        handler_a = ModelHandler(model_path="box", from_assets=False)
        handler_b = ModelHandler(model_path="box", from_assets=False)
        entity_a.add_handler(handler_a)
        entity_b.add_handler(handler_b)
        entity_a.start()
        entity_b.start()

        # Distinct instance nodes under distinct parents
        assert handler_a.model_np.getNode(0) is not handler_b.model_np.getNode(0)
        assert handler_a.model_np.getParent() == entity_a.node
        assert handler_b.model_np.getParent() == entity_b.node

        # Instances never share the cached template node either
        assert handler_a.model_np.getNode(0) is not template_a.getNode(0)
        assert handler_b.model_np.getNode(0) is not template_a.getNode(0)

        # Stopping one entity must not steal the other's model
        entity_a.stop()
        assert handler_a.model_np is None
        assert handler_b.model_np is not None
        assert not handler_b.model_np.isEmpty()
        assert handler_b.model_np.getParent() == entity_b.node

        entity_b.stop()
        entity_a.free()
        entity_b.free()
        self.p("Template caching and distinct instances verified successfully.", color="green")
        self.space_line()

    def test_lifecycle_symmetry_and_leak_prevention(self) -> None:
        self.print_subtitle("Testing clean lifecycle, restart symmetry, and leak prevention.")
        entity = Entity("LifecyclePropHero")
        handler = ModelHandler(model_path="box", from_assets=False)
        entity.add_handler(handler)

        assert handler.model_np is not None
        model_np = handler.model_np
        assert model_np.getParent() == entity.node

        # Start -> model remains in place
        entity.start()
        assert handler.model_np is not None
        assert not handler.model_np.isEmpty()

        # Stop -> instance removed, template untouched
        entity.stop()
        assert handler.model_np is None
        assert model_np.isEmpty()

        # Restart -> cleanly restores the model instance
        entity.start()
        assert handler.model_np is not None
        assert not handler.model_np.isEmpty()
        assert handler.model_np.getParent() == entity.node
        restored = handler.model_np

        # Detach handler -> instance removed again
        entity.remove_handler(handler)
        assert handler.model_np is None
        assert restored.isEmpty()

        entity.stop()
        entity.free()
        assert entity.is_freed

        # Cached template still usable after full teardown
        template = GlobalLoader.load("models/box")
        assert template is not None and not template.isEmpty()

        self.p("Lifecycle symmetry and leak prevention verified successfully.", color="green")
        self.space_line()

    def test_missing_model_is_graceful(self) -> None:
        self.print_subtitle("Testing graceful handling of a missing model asset.")
        entity = Entity("MissingModelHero")
        handler = ModelHandler(model_path="does_not_exist/missing.glb", from_assets=False)
        entity.add_handler(handler)

        # Missing asset falls back to an empty placeholder without raising
        assert handler.model_np is not None
        assert handler.model_np.getParent() == entity.node

        entity.start()
        entity.update(0.016)
        entity.stop()
        entity.free()

        self.p("Missing model handled gracefully without exceptions.", color="green")
        self.space_line()

    def test_headless_safety(self) -> None:
        self.print_subtitle("Testing ModelHandler headless safety without graphical window.")
        entity = Entity("HeadlessPropHero")
        handler = ModelHandler(model_path="box", from_assets=False)
        entity.add_handler(handler)

        entity.start()
        entity.update(0.016)
        entity.update(0.033)

        assert handler.model_np is not None
        assert not handler.model_np.isEmpty()

        entity.stop()
        entity.free()
        self.p("Headless safety verified successfully.", color="green")
        self.space_line()

    def on_stop(self) -> None:
        self.print_subtitle("TestModelHandler completed.")


if __name__ == "__main__":
    # Bootstrap a headless ShowBase for Loader support when running standalone.
    if not hasattr(builtins, "base") or builtins.base is None:
        from direct.showbase.ShowBase import ShowBase

        ShowBase(windowType="none")

    test = TestModelHandler()
    test.on_start()
    test.on_stop()
