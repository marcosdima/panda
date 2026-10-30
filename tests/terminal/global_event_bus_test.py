import pytest

from src.utils import GlobalEventBus, bus


def test_subscribe_and_publish_with_args():
    got = []
    bus_ = GlobalEventBus()
    bus_.subscribe("item_picked", lambda item, amount=1: got.append((item, amount)))
    bus_.publish("item_picked", "coin", amount=5)
    assert got == [("coin", 5)]


def test_zero_arg_callback_ignores_publish_args():
    calls = []
    bus_ = GlobalEventBus()
    bus_.subscribe("tick", lambda: calls.append("tick"))
    bus_.publish("tick", 1, 2, three=3)
    assert calls == ["tick"]


def test_priority_order():
    order = []
    bus_ = GlobalEventBus()
    bus_.subscribe("e", lambda: order.append("low"), priority=0)
    bus_.subscribe("e", lambda: order.append("high"), priority=10)
    bus_.subscribe("e", lambda: order.append("mid"), priority=5)
    bus_.publish("e")
    assert order == ["high", "mid", "low"]


def test_unsubscribe_removes_listener():
    calls = []
    bus_ = GlobalEventBus()

    def _cb() -> None:
        calls.append("x")

    bus_.subscribe("e", _cb)
    bus_.publish("e")
    bus_.unsubscribe("e", _cb)
    bus_.publish("e")
    assert calls == ["x"]


def test_has_listeners():
    bus_ = GlobalEventBus()
    assert not bus_.has_listeners("e")

    def _cb() -> None:
        return None

    bus_.subscribe("e", _cb)
    assert bus_.has_listeners("e")
    bus_.unsubscribe("e", _cb)
    assert not bus_.has_listeners("e")


def test_publish_unknown_event_does_not_crash():
    bus_ = GlobalEventBus()
    bus_.publish("no_such_event", 1, 2, three=3)


def test_subscribe_once_fires_once():
    calls = []
    bus_ = GlobalEventBus()
    bus_.subscribe_once("e", lambda: calls.append("once"))
    bus_.publish("e")
    bus_.publish("e")
    assert calls == ["once"]
    assert not bus_.has_listeners("e")


def test_clear_removes_all():
    bus_ = GlobalEventBus()
    bus_.subscribe("a", lambda: None)
    bus_.subscribe("b", lambda: None)
    assert bus_.has_listeners("a") and bus_.has_listeners("b")
    bus_.clear()
    assert not bus_.has_listeners("a") and not bus_.has_listeners("b")


def test_clear_named_event_only():
    bus_ = GlobalEventBus()
    bus_.subscribe("a", lambda: None)
    bus_.subscribe("b", lambda: None)
    bus_.clear("a")
    assert not bus_.has_listeners("a")
    assert bus_.has_listeners("b")


def test_independent_event_names():
    got_a, got_b = [], []
    bus_ = GlobalEventBus()
    bus_.subscribe("a", lambda: got_a.append(1))
    bus_.subscribe("b", lambda: got_b.append(2))
    bus_.publish("a")
    bus_.publish("b")
    bus_.publish("a")
    assert got_a == [1, 1]
    assert got_b == [2]


def test_global_bus_is_shared():
    from src.utils.global_event_bus import bus as module_bus

    assert bus is module_bus


def test_subscribe_returns_none():
    bus_ = GlobalEventBus()
    assert bus_.subscribe("e", lambda: None) is None


def test_unsubscribe_with_fresh_lambda_does_not_remove_listener():
    """Subscribers are matched by callable equality: a new lambda never matches."""
    calls = []
    bus_ = GlobalEventBus()
    bus_.subscribe("e", lambda: calls.append("kept"))
    bus_.unsubscribe("e", lambda: calls.append("kept"))
    assert bus_.has_listeners("e")
    bus_.publish("e")
    assert calls == ["kept"]


def test_unsubscribe_with_equivalent_bound_method_removes_listener():
    """Bound methods of the same instance compare equal, so they do match."""

    class Listener:
        def __init__(self) -> None:
            self.calls = 0

        def on_event(self) -> None:
            self.calls += 1

    listener = Listener()
    bus_ = GlobalEventBus()
    bus_.subscribe("e", listener.on_event)
    bus_.unsubscribe("e", listener.on_event)
    assert not bus_.has_listeners("e")
    bus_.publish("e")
    assert listener.calls == 0


def test_unsubscribe_during_dispatch_skips_removed_listener():
    """Dispatch iterates over a snapshot, so a listener removed mid-publish is skipped."""
    calls = []

    def second() -> None:
        calls.append("second")

    def first() -> None:
        calls.append("first")
        bus_.unsubscribe("e", second)

    bus_ = GlobalEventBus()
    bus_.subscribe("e", first, priority=10)
    bus_.subscribe("e", second, priority=0)
    bus_.publish("e")
    assert calls == ["first"]


def test_unsubscribe_releases_the_subscriber():
    """The bus holds a strong reference: unsubscribing must release the handler."""
    import gc
    import weakref

    class Subscriber:
        def __init__(self) -> None:
            self.calls = 0

        def on_event(self) -> None:
            self.calls += 1

    bus_ = GlobalEventBus()
    subscriber = Subscriber()
    ref = weakref.ref(subscriber)
    bus_.subscribe("e", subscriber.on_event)
    bus_.unsubscribe("e", subscriber.on_event)
    del subscriber
    gc.collect()
    assert ref() is None


def test_handler_must_unsubscribe_on_stop():
    """A handler subscribed to the global bus must unsubscribe in on_stop."""
    from src.handlers.base import Handler

    class SubscriberHandler(Handler):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def on_start(self) -> None:
            bus.subscribe("level_completed", self._on_level_completed)

        def _on_level_completed(self, level: int) -> None:
            self.calls += 1

        def on_stop(self) -> None:
            bus.unsubscribe("level_completed", self._on_level_completed)

    handler = SubscriberHandler()
    try:
        handler.on_start()
        assert bus.has_listeners("level_completed")
        bus.publish("level_completed", 1)
        assert handler.calls == 1
        handler.on_stop()
        assert not bus.has_listeners("level_completed")
        bus.publish("level_completed", 2)
        assert handler.calls == 1
    finally:
        bus.unsubscribe("level_completed", handler._on_level_completed)


def test_services_registry_exposes_the_bus():
    """`initialize_services` registers the engine-wide bus under "events"."""
    from src.services import services
    from src.services.initializers import initialize_services

    saved = dict(services._services)
    try:
        initialize_services()
        assert services.get("events") is bus
    finally:
        services._services.clear()
        services._services.update(saved)


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
