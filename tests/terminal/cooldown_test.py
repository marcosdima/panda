import pytest

from src.utils.cooldown import Cooldown


def test_initial_state_and_invalid_duration():
    # Positive duration
    cd = Cooldown(1.5)
    assert cd.ready
    assert cd.remaining == 0.0
    # Zero duration
    cd0 = Cooldown(0)
    assert cd0.ready
    # Negative duration should raise
    with pytest.raises(ValueError):
        Cooldown(-1)


def test_start_and_tick_behaviour():
    cd = Cooldown(2.0)
    cd.start()
    assert not cd.ready
    assert cd.remaining == 2.0
    cd.tick(0.5)
    assert cd.remaining == 1.5
    assert not cd.ready
    cd.tick(1.5)
    assert cd.ready
    assert cd.remaining == 0.0


def test_reset_and_trigger():
    cd = Cooldown(1.0)
    cd.start()
    assert not cd.trigger()  # already active
    cd.reset()
    assert cd.ready
    assert cd.trigger()  # starts and returns True
    assert not cd.ready
    # after tick to finish
    cd.tick(1.0)
    assert cd.ready
    # trigger again
    assert cd.trigger()
    cd.tick(0.5)
    assert not cd.ready
    assert not cd.trigger()


def test_duration_is_float():
    cd = Cooldown(3)  # int input
    assert isinstance(cd.duration, float)
    cd.start()
    cd.tick(1)
    assert cd.remaining == 2.0


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
