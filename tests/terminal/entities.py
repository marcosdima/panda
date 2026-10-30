try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

from src.entities.entity import Entity
from src.handlers.base import Handler
from src.scenes import Scene


class LifecycleSpyHandler(Handler):
    """Handler used to spy on lifecycle hook invocations."""

    def __init__(self, tag: str = "spy") -> None:
        super().__init__()
        self.tag: str = tag
        self.log: list[str] = []

    def on_attach(self, entity: Entity) -> None:
        super().on_attach(entity)
        self.log.append("on_attach")

    def on_detach(self) -> None:
        super().on_detach()
        self.log.append("on_detach")

    def on_start(self) -> None:
        super().on_start()
        self.log.append("on_start")

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        self.log.append(f"on_update:{dt:.3f}")

    def on_stop(self) -> None:
        super().on_stop()
        self.log.append("on_stop")


class ExtraTestHandler(Handler):
    """Secondary handler type for multi-handler querying tests."""


class TestEntities(TerminalTest):
    def on_start(self):
        self.print_title("TestEntities started.", color="green")
        super().on_start()

    def test_id_allocation(self):
        self.print_subtitle("Testing ID allocation.")
        Entity.reset_ids()

        e1 = Entity()
        e2 = Entity("CustomNamed")
        e3 = Entity()

        self.p(f"Entity 1 id: {e1.id}, name: {e1.name}")
        self.p(f"Entity 2 id: {e2.id}, name: {e2.name}")
        self.p(f"Entity 3 id: {e3.id}, name: {e3.name}")

        assert e1.id == 0, f"Expected 0, got {e1.id}"
        assert e2.id == 1, f"Expected 1, got {e2.id}"
        assert e3.id == 2, f"Expected 2, got {e3.id}"
        assert e1.name == "Entity-0"
        assert e2.name == "CustomNamed"
        assert e1.node.getPythonTag("entity") is e1
        assert e2.node.getPythonTag("entity") is e2

        self.p("ID allocation and naming verified successfully.", color="green")
        self.space_line()

    def test_id_reuse_after_free(self):
        self.print_subtitle("Testing ID reuse after free.")
        Entity.reset_ids()

        e1 = Entity()
        e2 = Entity()
        ids_before = (e1.id, e2.id)
        self.p(f"Created initial IDs: {ids_before[0]}, {ids_before[1]}")
        assert ids_before == (0, 1)

        # Free the second entity and create a new one, expecting the freed ID to be reused.
        e2.free()
        assert e2.is_freed
        assert e2.node.isEmpty()

        e3 = Entity()
        self.p(f"Freed ID {ids_before[1]}; newly created Entity ID: {e3.id}")
        reused = e3.id == ids_before[1]
        self.p(f"ID reused: {reused}")
        assert reused, f"Expected reused ID {ids_before[1]}, got {e3.id}"

        self.p("Single ID reuse verified successfully.", color="green")
        self.space_line()

    def test_multiple_free_and_reuse(self):
        self.print_subtitle("Testing multiple frees and LIFO reuse behavior.")
        Entity.reset_ids()

        a = Entity("A")
        b = Entity("B")
        c = Entity("C")
        self.p(f"Initial IDs: a={a.id}, b={b.id}, c={c.id}")
        assert (a.id, b.id, c.id) == (0, 1, 2)

        # Free b and a (order matters for reuse stack behavior: LIFO)
        b.free()
        a.free()

        # Double free attempt should be safely ignored
        a.free()

        d = Entity("D")
        e = Entity("E")
        self.p(f"New entities: d={d.id}, e={e.id}")
        self.p(f"Expected reuse: a->d ({a.id == d.id}) | b->e ({b.id == e.id})")

        assert d.id == a.id, f"Expected d.id == a.id ({a.id}), got {d.id}"
        assert e.id == b.id, f"Expected e.id == b.id ({b.id}), got {e.id}"

        # Verify next allocation gets a fresh ID
        f = Entity("F")
        self.p(f"Subsequent allocation: f={f.id}")
        assert f.id == 3, f"Expected 3, got {f.id}"

        self.p("Multiple free and LIFO reuse verified successfully.", color="green")
        self.space_line()

    def test_handler_attachment_and_queries(self):
        self.print_subtitle("Testing handler attachment, queries, and removal.")
        Entity.reset_ids()

        entity = Entity("TestEntity")
        h1 = LifecycleSpyHandler("spy1")
        h2 = ExtraTestHandler()

        # Add handlers
        added1 = entity.add_handler(h1)
        added2 = entity.add_handler(h2)
        assert added1 is h1
        assert added2 is h2
        assert h1.entity is entity
        assert h2.entity is entity

        # Check has_handler
        assert entity.has_handler(LifecycleSpyHandler)
        assert entity.has_handler(ExtraTestHandler)
        assert not entity.has_handler(Scene)

        # Query single handler
        found_spy = entity.get_handler(LifecycleSpyHandler)
        assert found_spy is h1
        found_extra = entity.get_handler(ExtraTestHandler)
        assert found_extra is h2
        assert entity.get_handler(Scene) is None

        # Query multiple handlers by base type
        all_handlers = entity.get_handlers(Handler)
        assert len(all_handlers) == 2
        assert h1 in all_handlers
        assert h2 in all_handlers

        # Remove handler
        removed = entity.remove_handler(h1)
        assert removed is True
        assert entity.has_handler(LifecycleSpyHandler) is False
        assert h1.entity is None
        assert "on_detach" in h1.log

        # Removing already removed handler returns False
        removed_again = entity.remove_handler(h1)
        assert removed_again is False

        self.p(
            "Handler attachment, query, and removal verified successfully.",
            color="green",
        )
        self.space_line()

    def test_lifecycle_hooks_order(self):
        self.print_subtitle("Testing lifecycle hooks execution order.")
        Entity.reset_ids()

        entity = Entity("LifecycleSubject")
        spy = LifecycleSpyHandler("subject_spy")

        # 1. Attachment hook
        entity.add_handler(spy)
        assert spy.log == ["on_attach"]
        self.p(f"Log after add_handler: {spy.log}")

        # 2. Start hook
        entity.on_start()
        assert spy.log == ["on_attach", "on_start"]
        self.p(f"Log after on_start: {spy.log}")

        # 3. Update hook while enabled
        entity.on_update(0.016)
        assert spy.log == ["on_attach", "on_start", "on_update:0.016"]
        self.p(f"Log after on_update: {spy.log}")

        # 4. Disable handler and verify on_update is skipped
        spy.set_enabled(False)
        assert not spy.is_enabled
        entity.on_update(0.016)
        assert len(spy.log) == 3, "Disabled handler should not receive update"

        # 5. Re-enable handler and verify on_update resumes
        spy.set_enabled(True)
        assert spy.is_enabled
        entity.on_update(0.033)
        assert spy.log == [
            "on_attach",
            "on_start",
            "on_update:0.016",
            "on_update:0.033",
        ]

        # 6. Stop hook
        entity.on_stop()
        assert spy.log == [
            "on_attach",
            "on_start",
            "on_update:0.016",
            "on_update:0.033",
            "on_stop",
        ]
        self.p(f"Log after on_stop: {spy.log}")

        # 7. Free entity (detaches handler and cleans up)
        entity.free()
        assert spy.log == [
            "on_attach",
            "on_start",
            "on_update:0.016",
            "on_update:0.033",
            "on_stop",
            "on_detach",
        ]
        assert spy.entity is None
        assert entity.is_freed

        self.p("Lifecycle hooks order verified successfully.", color="green")
        self.space_line()

    def test_scene_entity_lifecycle(self):
        self.print_subtitle("Testing Scene entity lifecycle propagation.")
        Entity.reset_ids()

        class MockScene(Scene):
            pass

        scene = MockScene()
        entity = Entity("SceneHero")
        spy = LifecycleSpyHandler("hero_spy")
        entity.add_handler(spy)

        scene.add_entity(entity)
        assert scene.get_entity(entity.id) is entity

        # Scene start should propagate to entities
        scene.on_start()
        assert "on_start" in spy.log

        # Scene update should propagate to entities
        scene.on_update(0.016)
        assert "on_update:0.016" in spy.log

        # Scene stop should cleanly free entities
        scene.on_stop()
        assert "on_stop" in spy.log
        assert "on_detach" in spy.log
        assert entity.is_freed
        assert len(scene.entities) == 0

        self.p("Scene lifecycle propagation verified successfully.", color="green")
        self.space_line()

    def on_stop(self):
        self.print_subtitle("TestEntities completed.")


if __name__ == "__main__":
    test = TestEntities()
    test.on_start()
    test.on_stop()
