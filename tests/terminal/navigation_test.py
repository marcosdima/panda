"""Headless tests for AINavigationHandler and grid navigation."""
import pytest
from panda3d.core import Vec3

from src.entities.entity import Entity
from src.handlers.ai import AINavigationHandler, NavigationState
from src.handlers.input.base import InputHandler
from src.navigation.grid import NavGrid
from src.navigation.smoothing import smooth_path


def make_nav(**kwargs):
    grid = kwargs.pop("grid", None)
    entity = Entity("Npc")
    inp = InputHandler()
    entity.add_handler(inp)
    kwargs.setdefault("line_of_sight", lambda a, b: True)
    if "nav_grid" in kwargs:
        chosen_grid = kwargs.pop("nav_grid")
    elif grid is not None:
        chosen_grid = grid
    else:
        chosen_grid = NavGrid(40, 40, 1.0, origin=Vec3(-20, -20, 0))
    filtered = {k: v for k, v in kwargs.items()}
    ai = AINavigationHandler(nav_grid=chosen_grid, **filtered)
    entity.add_handler(ai)
    entity.start()
    return entity, inp, ai, chosen_grid


def test_grid_direct_path():
    grid = NavGrid(10, 10, 1.0)
    from src.navigation.pathfinder import GridPathfinder

    pf = GridPathfinder(grid)
    path = pf.find_path(Vec3(0.5, 0.5, 0), Vec3(3.5, 0.5, 0))
    assert path is not None
    assert len(path) == 4


def test_grid_path_around_obstacle():
    grid = NavGrid(20, 20, 1.0, origin=Vec3(-10, -10, 0))
    for y in range(5, 16):
        grid.block((10, y))
    grid.unblock((10, 10))
    from src.navigation.pathfinder import GridPathfinder

    pf = GridPathfinder(grid)
    path = pf.find_path(Vec3(-5, 0, 0), Vec3(5, 0, 0))
    assert path is not None
    assert len(path) >= 2


def test_grid_no_path():
    grid = NavGrid(5, 5, 1.0)
    grid.set_blocked([(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)])
    from src.navigation.pathfinder import GridPathfinder

    pf = GridPathfinder(grid)
    path = pf.find_path(Vec3(0.5, 2.5, 0), Vec3(4.5, 2.5, 0))
    assert path is None


def test_smooth_path():
    pts = [Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(2, 0, 0), Vec3(2, 2, 0)]
    out = smooth_path(pts, lambda a, b: True)
    assert out[0] == pts[0]
    assert out[-1] == pts[-1]
    assert len(out) <= len(pts)


def test_navigation_without_grid_moves_toward_waypoint():
    entity, inp, ai, _ = make_nav(waypoints=[Vec3(10, 0, 0)], nav_grid=None)
    entity.update(0.1)
    assert inp.move_vector.x == pytest.approx(1.0)
    assert ai.state == NavigationState.PATROL


def test_navigation_with_grid_creates_path():
    grid = NavGrid(40, 40, 1.0, origin=Vec3(-20, -20, 0))
    entity, _, ai, _ = make_nav(waypoints=[Vec3(5, 0, 0)], grid=grid)
    entity.update(0.1)
    assert ai.current_path is not None


def test_navigation_avoidance_detects_obstacle():
    entity, _, ai, _ = make_nav(
        waypoints=[Vec3(10, 0, 0)],
        nav_grid=None,
        avoidance_check=lambda a, b: False,
    )
    entity.update(0.1)
    assert ai.obstacle_detected is True


def test_navigation_search_state():
    target = Entity("Player")
    target.node.setPos(3, 0, 0)
    entity, _, ai, _ = make_nav(
        waypoints=[Vec3(-10, 0, 0)],
        target=target,
        sight_range=8.0,
        search_time=1.0,
    )
    entity.update(0.1)
    assert ai.state == NavigationState.CHASE
    target.node.setPos(50, 0, 0)
    entity.update(0.1)
    assert ai.state == NavigationState.SEARCH


def test_navigation_state_export():
    import src.handlers as h

    assert "AINavigationHandler" in h.__all__
    assert "NavigationState" in h.__all__


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
