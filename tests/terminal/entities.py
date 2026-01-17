from .__terminal import TerminalTest
from src.entities import Solid


class TestEntities(TerminalTest):
    def on_start(self):
        self.print_title('TestEntities started.', color='green')
        super().on_start()


    def test_id_allocation(self):
        self.print_subtitle('Testing id allocation.')
        e1 = Solid()
        e2 = Solid()
        self.p(f'Solid 1 id: {e1.id}')
        self.p(f'Solid 2 id: {e2.id}')
        self.space_line()


    def test_id_reuse_after_free(self):
        self.print_subtitle('Testing id reuse after free.')
        e1 = Solid()
        e2 = Solid()
        ids_before = (e1.id, e2.id)
        self.p(f'Created ids: {ids_before[0]}, {ids_before[1]}')

        # Free the second entity and create a new one, expecting the freed id to be reused.
        e2.free()
        e3 = Solid()
        self.p(f'Freed id {ids_before[1]}; new entity id: {e3.id}')
        reused = e3.id == ids_before[1]
        self.p(f'ID reused: {reused}')
        self.space_line()


    def test_multiple_free_and_reuse(self):
        self.print_subtitle('Testing multiple frees and reuse behavior.')
        a = Solid()
        b = Solid()
        c = Solid()
        self.p(f'Initial ids: {a.id}, {b.id}, {c.id}')

        # Free b and a (order matters for reuse stack behavior)
        b.free()
        a.free()
        d = Solid()
        e = Solid()
        self.p(f'New entities: d -> {d.id} e -> {e.id}')
        self.p(f'Expected reuse for first new: a -> d ({a.id == d.id}) | b -> e ({b.id == e.id})')
        self.space_line()


    def on_stop(self):
        self.print_subtitle('TestEntities stopped.')
