try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

from src.entities.entity import Entity


class TestEvents(TerminalTest):
    def on_start(self):
        self.print_title("TestEvents started.", color="cyan")
        super().on_start()

    def test_free_callback(self):
        self.print_subtitle("Entity is being freed.")
        entity = Entity()
        entity.on_free.add_callback(lambda: self.p("Free callback executed."))
        entity.free()
        self.space_line()

    def test_free_callback_priority(self):
        self.print_subtitle("Testing free callback priority.")
        entity = Entity()
        entity.on_free.add_callback(lambda: self.p("Low priority callback."), priority=1)
        entity.on_free.add_callback(lambda: self.p("High priority callback."), priority=10)
        entity.free()
        self.space_line()

    def test_call_with_false_check(self):
        self.print_subtitle("Testing event with false check.")
        no_print = Entity()
        printed_entity = Entity()

        no_print.on_free.set_check(lambda: False)
        no_print.on_free.add_callback(lambda: self.p("This should not be printed!"))
        printed_entity.on_free.add_callback(lambda: self.p("Successful print callback."))

        no_print.free()
        printed_entity.free()

        self.space_line()

    def on_stop(self):
        self.print_subtitle("TestEvents stopped.")


if __name__ == "__main__":
    test = TestEvents()
    test.on_start()
    test.on_stop()
