import pytest
from src.utils import StateMachine


def make():
    return StateMachine('idle', {
        'idle': ['walk', 'jump'],
        'walk': ['idle', 'jump'],
        'jump': ['idle'],
    })


def test_transitions_and_validation():
    sm = make()
    assert sm.state == 'idle'
    assert sm.can_transition('walk') and not sm.can_transition('idle')
    assert sm.transition('walk') is True
    assert sm.state == 'walk'
    sm.transition('jump')
    with pytest.raises(ValueError):
        sm.transition('walk')
    assert sm.state == 'jump'


def test_same_state_noop():
    sm = make()
    assert sm.transition('idle') is False


def test_hooks_order():
    sm = make()
    log = []
    sm.on_exit('idle', lambda p, n: log.append(('exit', p, n)))
    sm.on_enter('walk', lambda p, n: log.append(('enter', p, n)))
    sm.transition('walk')
    assert log == [('exit', 'idle', 'walk'), ('enter', 'idle', 'walk')]


def test_open_machine_and_bad_initial():
    sm = StateMachine('a')
    sm.transition('anything')
    assert sm.state == 'anything'
    with pytest.raises(ValueError):
        StateMachine('x', {'a': ['b']})


def test_reentrant_transition_raises_and_recovers():
    sm = make()
    sm.on_enter('walk', lambda p, n: sm.transition('jump'))
    with pytest.raises(RuntimeError):
        sm.transition('walk')
    # guard released: machine usable afterwards
    assert sm.state == 'walk'
    assert sm.transition('idle') is True


def test_reset_keeps_hooks_without_running_them():
    sm = make()
    log = []
    sm.on_exit('walk', lambda p, n: log.append('exit'))
    sm.transition('walk')
    sm.reset('idle')
    assert sm.state == 'idle' and log == []
    sm.transition('walk')
    sm.transition('idle')
    assert log == ['exit']
    with pytest.raises(ValueError):
        sm.reset('nope')


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__]))
