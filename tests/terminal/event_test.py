import pytest

from src.utils import Event


def test_args_and_no_args_callbacks():
    got = []
    ev = Event()
    ev.add_callback(lambda: got.append("none"))
    ev.add_callback(lambda x, y=0: got.append((x, y)))
    ev(1, y=2)
    assert sorted(map(str, got)) == sorted(["none", "(1, 2)"])


def test_priority_order():
    order = []
    ev = Event()
    ev.add_callback(lambda: order.append("low"), priority=0)
    ev.add_callback(lambda: order.append("high"), priority=5)
    ev()
    assert order == ["high", "low"]


def test_add_once():
    count = []
    ev = Event()
    ev.add_once(lambda: count.append(1))
    ev()
    ev()
    assert count == [1]
    assert len(ev) == 0


def test_mutation_during_dispatch():
    ev = Event()
    calls = []

    def first():
        calls.append("first")
        ev.remove_callback(second)
        ev.add_callback(lambda: calls.append("late"))

    def second():
        calls.append("second")

    ev.add_callback(first, priority=1)
    ev.add_callback(second, priority=0)
    ev()
    assert calls == ["first"]
    ev()
    assert calls == ["first", "first", "late"]


def test_check_blocks_and_clear():
    calls = []
    ev = Event(check=lambda: False)
    ev.add_callback(lambda: calls.append(1))
    ev()
    assert calls == []
    ev.clear_callbacks()
    assert len(ev) == 0


def test_add_once_zero_arg_with_event_args():
    calls = []
    ev = Event()
    ev.add_once(lambda: calls.append(1))
    ev(1, 2)
    ev(1, 2)
    assert calls == [1]


def test_add_callback_makes_once_persistent():
    calls = []
    ev = Event()
    cb = lambda: calls.append(1)
    ev.add_once(cb)
    ev.add_callback(cb)
    ev()
    ev()
    assert calls == [1, 1]


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
