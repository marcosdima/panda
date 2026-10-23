import pytest
from src.utils.math import clamp, lerp, smoothstep, normalize_angle, lerp_angle, remap

def test_clamp_basic():
    assert clamp(5, 0, 10) == 5.0
    assert clamp(-1, 0, 10) == 0.0
    assert clamp(15, 0, 10) == 10.0
    # Float inputs
    assert clamp(2.5, 1.0, 3.0) == 2.5
    # Inverted bounds raise; equal bounds are valid
    with pytest.raises(ValueError):
        clamp(5, 10, 0)
    assert clamp(5, 3, 3) == 3.0

def test_lerp_basic():
    assert lerp(0, 10, 0.0) == 0.0
    assert lerp(0, 10, 1.0) == 10.0
    assert lerp(5, 15, 0.5) == 10.0
    # Out‑of‑range t works (no clamping)
    assert lerp(0, 10, -0.5) == -5.0
    assert lerp(0, 10, 1.5) == 15.0

def test_smoothstep_basic():
    # Classic smoothstep from 0 to 1
    assert smoothstep(0.0, 1.0, -0.5) == 0.0
    assert smoothstep(0.0, 1.0, 0.0) == 0.0
    assert smoothstep(0.0, 1.0, 0.5) == 0.5
    assert smoothstep(0.0, 1.0, 1.0) == 1.0
    assert smoothstep(0.0, 1.0, 1.5) == 1.0
    # Edge validation
    with pytest.raises(ValueError):
        smoothstep(1.0, 1.0, 0.5)


def test_normalize_angle():
    assert normalize_angle(190) == -170.0
    assert normalize_angle(-190) == 170.0
    assert normalize_angle(360) == 0.0
    assert normalize_angle(-90, 0) == 270.0
    assert normalize_angle(720, 0) == 0.0


def test_lerp_angle_shortest_arc():
    assert lerp_angle(350, 10, 0.5) == 360.0
    assert lerp_angle(10, 350, 0.5) == 0.0
    assert lerp_angle(0, 90, 0.5) == 45.0


def test_remap():
    assert remap(5, 0, 10, 0, 100) == 50.0
    assert remap(15, 0, 10, 0, 100) == 150.0
    assert remap(15, 0, 10, 0, 100, clamp_result=True) == 100.0
    assert remap(0, 0, 10, 1, 0) == 1.0
    with pytest.raises(ValueError):
        remap(1, 2, 2, 0, 1)


def test_smoothstep_inverted_edges():
    assert smoothstep(1.0, 0.0, 1.0) == 0.0
    assert smoothstep(1.0, 0.0, 0.0) == 1.0
    assert smoothstep(1.0, 0.0, 0.5) == 0.5


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__]))
