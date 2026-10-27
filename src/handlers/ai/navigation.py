from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import TYPE_CHECKING

from panda3d.core import Vec3

from src.handlers.ai.patrol import AIPatrolHandler
from src.handlers.base import Handler
from src.navigation.graph import NavGraph
from src.navigation.grid import NavGrid
from src.navigation.pathfinder import GridPathfinder
from src.navigation.smoothing import smooth_path
from src.utils.state_machine import StateMachine

if TYPE_CHECKING:
    from src.entities.entity import Entity


class NavigationState(str, Enum):
    PATROL = "patrol"
    WAIT = "wait"
    CHASE = "chase"
    SEARCH = "search"
    BLOCKED = "blocked"


_NAV_TRANSITIONS = {
    NavigationState.PATROL: [
        NavigationState.WAIT,
        NavigationState.CHASE,
        NavigationState.SEARCH,
        NavigationState.BLOCKED,
    ],
    NavigationState.WAIT: [NavigationState.PATROL, NavigationState.CHASE],
    NavigationState.CHASE: [NavigationState.PATROL, NavigationState.SEARCH, NavigationState.BLOCKED],
    NavigationState.SEARCH: [NavigationState.PATROL, NavigationState.CHASE],
    NavigationState.BLOCKED: [NavigationState.PATROL, NavigationState.CHASE],
}


class AINavigationHandler(AIPatrolHandler):
    def __init__(
        self,
        waypoints: Sequence[Vec3] = (),
        arrive_radius: float = 0.5,
        wait_time: float = 1.0,
        ping_pong: bool = False,
        target: Entity | None = None,
        sight_range: float = 8.0,
        lose_range: float | None = None,
        chase_sprint: bool = True,
        obstacle_mask=None,
        eye_height: float = 1.0,
        line_of_sight: Callable[[Vec3, Vec3], bool] | None = None,
        nav_grid: NavGrid | None = None,
        nav_graph: NavGraph | None = None,
        pathfinder: GridPathfinder | None = None,
        avoidance: bool = True,
        avoidance_check: Callable[[Vec3, Vec3], bool] | None = None,
        obstacle_check: Callable[[Vec3, Vec3], bool] | None = None,
        raycast: Callable[[Vec3, Vec3], bool] | None = None,
        clear_check: Callable[[Vec3, Vec3], bool] | None = None,
        search_time: float = 2.0,
    ) -> None:
        super().__init__(
            waypoints=waypoints,
            arrive_radius=arrive_radius,
            wait_time=wait_time,
            ping_pong=ping_pong,
            target=target,
            sight_range=sight_range,
            lose_range=lose_range,
            chase_sprint=chase_sprint,
            obstacle_mask=obstacle_mask,
            eye_height=eye_height,
            line_of_sight=line_of_sight,
        )
        self.machine = StateMachine(NavigationState.PATROL, _NAV_TRANSITIONS)

        self.nav_grid = nav_grid
        self.nav_graph = nav_graph
        self.pathfinder = pathfinder if pathfinder is not None else (GridPathfinder(nav_grid) if nav_grid is not None else None)
        self.avoidance = bool(avoidance)
        self.avoidance_check = avoidance_check or obstacle_check or raycast or clear_check
        self.search_time = float(search_time)

        self._path_goal: Vec3 | None = None
        self._current_path: list[Vec3] = []
        self._path_index: int = 0
        self._replan_count: int = 0
        self._last_known_target: Vec3 | None = None
        self._search_left: float = 0.0
        self._obstacle_detected: bool = False
        self._avoidance_vector: Vec3 = Vec3(0.0, 0.0, 0.0)

    @property
    def state(self) -> NavigationState:
        return self.machine.state  # type: ignore[return-value]

    @property
    def grid(self) -> NavGrid | None:
        return self.nav_grid

    @property
    def current_path(self) -> list[Vec3]:
        return [Vec3(p) for p in self._current_path]
    @property
    def path(self) -> list[Vec3]:
        return self.current_path



    @property
    def has_pathfinding(self) -> bool:
        return self.nav_grid is not None or self.nav_graph is not None

    @property
    def path_index(self) -> int:
        return self._path_index

    @property
    def replan_count(self) -> int:
        return self._replan_count

    @property
    def last_known_target(self) -> Vec3 | None:
        return None if self._last_known_target is None else Vec3(self._last_known_target)

    @property
    def obstacle_detected(self) -> bool:
        return self._obstacle_detected

    @property
    def avoidance_vector(self) -> Vec3:
        return Vec3(self._avoidance_vector)

    def request_replan(self) -> None:
        self._current_path = []
        self._path_index = 0
        self._path_goal = None
        self._replan_count += 1

    def clear_path(self) -> None:
        self._current_path = []
        self._path_index = 0
        self._path_goal = None

    def on_start(self) -> None:
        Handler.on_start(self)
        self.machine.reset(NavigationState.PATROL)
        self._wait_left = 0.0
        self._search_left = 0.0
        self.clear_path()

    def on_stop(self) -> None:
        Handler.on_stop(self)
        self._drive(Vec3(0, 0, 0), sprint=False)

    def on_update(self, dt: float) -> None:
        if self.entity is None:
            return
        self._update_detection()
        state = self.state
        if state == NavigationState.CHASE:
            self._update_chase()
        elif state == NavigationState.WAIT:
            self._update_wait(dt)
        elif state == NavigationState.SEARCH:
            self._update_search(dt)
        elif state == NavigationState.BLOCKED:
            self._update_blocked(dt)
        else:
            self._update_patrol()

    def _update_detection(self) -> None:
        if self.target is None or self.target.is_freed:
            if self.state in (NavigationState.CHASE, NavigationState.SEARCH):
                self.machine.transition(NavigationState.PATROL)
            self._last_known_target = None
            return
        dist = self._distance_to_target()
        if self.state == NavigationState.CHASE:
            if dist > self.lose_range:
                self._last_known_target = self._target_position()
                if self.search_time > 0:
                    self.machine.transition(NavigationState.SEARCH)
                else:
                    self.machine.transition(NavigationState.PATROL)
                self._search_left = self.search_time
                return
            if not self._can_see_target():
                self._last_known_target = self._target_position()
                if self.search_time > 0:
                    self.machine.transition(NavigationState.SEARCH)
                else:
                    self.machine.transition(NavigationState.PATROL)
                self._search_left = self.search_time
            return
        if self.state == NavigationState.SEARCH:
            if dist <= self.sight_range and self._can_see_target():
                self.machine.transition(NavigationState.CHASE)
            return
        if dist > self.sight_range:
            return
        if self._can_see_target():
            self.machine.transition(NavigationState.CHASE)

    def _update_patrol(self) -> None:
        goal = self.current_waypoint
        if goal is None:
            self._drive(Vec3(0, 0, 0), sprint=False)
            return

        if self.has_pathfinding:
            self._ensure_path(goal)
            pt = self._next_path_point()
            if pt is None:
                pt = Vec3(goal)
            to_goal = self._planar(pt - self._position())
            if to_goal.length() <= (self.arrive_radius if self.nav_grid is None else max(self.arrive_radius, self.nav_grid.cell_size * 0.5)):
                self._path_index += 1
                pt = self._next_path_point()
                if pt is None:
                    pt = Vec3(goal)
                to_goal = self._planar(pt - self._position())
            if (pt - goal).length_squared() < 1e-8 and self._planar(goal - self._position()).length() <= self.arrive_radius:
                self._advance_waypoint()
                self._wait_left = self.wait_time
                self._drive(Vec3(0, 0, 0), sprint=False)
                if self._wait_left > 0.0:
                    self.machine.transition(NavigationState.WAIT)
                return
        else:
            to_goal = self._planar(goal - self._position())
            if to_goal.length() <= self.arrive_radius:
                self._advance_waypoint()
                self._wait_left = self.wait_time
                self._drive(Vec3(0, 0, 0), sprint=False)
                if self._wait_left > 0.0:
                    self.machine.transition(NavigationState.WAIT)
                return

        to_goal = self._avoid(to_goal)
        if to_goal.length_squared() <= 1e-8 and self._obstacle_detected and self.has_pathfinding:
            self.machine.transition(NavigationState.BLOCKED)
            self._drive(Vec3(0, 0, 0), sprint=False)
            return
        self._drive(to_goal, sprint=False)

    def _update_wait(self, dt: float) -> None:
        self._drive(Vec3(0, 0, 0), sprint=False)
        self._wait_left -= dt
        if self._wait_left <= 0.0:
            self.machine.transition(NavigationState.PATROL)

    def _update_chase(self) -> None:
        assert self.target is not None
        goal = self._target_position()
        if self.has_pathfinding:
            self._ensure_path(goal)
            pt = self._next_path_point()
            if pt is None:
                pt = Vec3(goal)
            to_target = self._planar(pt - self._position())
            if to_target.length() <= (self.arrive_radius if self.nav_grid is None else max(self.arrive_radius, self.nav_grid.cell_size * 0.5)):
                self._path_index += 1
                pt = self._next_path_point()
                if pt is None:
                    pt = Vec3(goal)
                to_target = self._planar(pt - self._position())
            if self._planar(goal - self._position()).length() <= self.arrive_radius:
                self._drive(Vec3(0, 0, 0), sprint=False)
                return
        else:
            to_target = self._planar(goal - self._position())
            if to_target.length() <= self.arrive_radius:
                self._drive(Vec3(0, 0, 0), sprint=False)
                return

        to_target = self._avoid(to_target)
        if to_target.length_squared() <= 1e-8 and self._obstacle_detected and self.has_pathfinding:
            self.machine.transition(NavigationState.BLOCKED)
            self._drive(Vec3(0, 0, 0), sprint=False)
            return
        self._drive(to_target, sprint=self.chase_sprint)

    def _update_search(self, dt: float) -> None:
        if self._last_known_target is None:
            self.machine.transition(NavigationState.PATROL)
            return
        to_goal = self._planar(self._last_known_target - self._position())
        if to_goal.length() <= self.arrive_radius:
            self.machine.transition(NavigationState.PATROL)
            return
        to_goal = self._avoid(to_goal)
        self._drive(to_goal, sprint=False)
        self._search_left -= dt
        if self._search_left <= 0.0:
            self.machine.transition(NavigationState.PATROL)

    def _update_blocked(self, dt: float) -> None:
        self._drive(Vec3(0, 0, 0), sprint=False)
        self.request_replan()
        self.machine.transition(NavigationState.PATROL)

    def _ensure_path(self, goal: Vec3) -> None:
        if self.nav_graph is not None:
            if (
                self._current_path
                and self._path_index < len(self._current_path)
                and self._path_goal is not None
                and (self._path_goal - goal).length() < 0.25
            ):
                return
            self._path_goal = Vec3(goal)
            from src.navigation.graph import GraphPathfinder

            path = GraphPathfinder(self.nav_graph).find_path(self._position(), goal)
            if path is None:
                self._current_path = []
                self._path_index = 0
                return
            if len(path) > 2:
                path = smooth_path(path, lambda a, b: self._line_clear(a, b))
            self._current_path = [Vec3(p) for p in path]
            self._path_index = 0
            return

        if self.nav_grid is None or self.pathfinder is None:
            return
        if self._current_path and self._path_index < len(self._current_path) and self._path_goal is not None:
            blocked = False
            for pt in self._current_path[self._path_index :]:
                cell = self.nav_grid.world_to_cell(pt)
                if cell is None or not self.nav_grid.is_walkable(cell):
                    blocked = True
                    break
            if not blocked and (self._path_goal - goal).length() < max(0.25, self.nav_grid.cell_size * 0.5):
                return
            if blocked:
                self.request_replan()
        self._path_goal = Vec3(goal)
        path = self.pathfinder.find_path(self._position(), goal)
        if path is None:
            self._current_path = []
            self._path_index = 0
            return
        if len(path) > 2:
            path = smooth_path(path, lambda a, b: self._line_clear(a, b))
        self._current_path = [Vec3(p) for p in path]
        self._path_index = 0

    def _next_path_point(self) -> Vec3 | None:
        if not self._current_path or self._path_index >= len(self._current_path):
            return None
        return Vec3(self._current_path[self._path_index])

    def _line_clear(self, a: Vec3, b: Vec3) -> bool:
        return self._is_clear(a, b)

    def _avoid(self, direction: Vec3) -> Vec3:
        if not self.avoidance or direction.length_squared() <= 1e-8:
            self._obstacle_detected = False
            self._avoidance_vector = Vec3(direction)
            return direction
        d = Vec3(direction)
        if d.length_squared() > 1e-8:
            d.normalize()
        lookahead = max(self.arrive_radius * 2.0, 1.0)
        start = self._position()
        end = start + d * lookahead
        if self._is_clear(start, end):
            self._obstacle_detected = False
            self._avoidance_vector = Vec3(direction)
            return direction
        self._obstacle_detected = True
        left = Vec3(-d.y, d.x, 0.0)
        right = Vec3(d.y, -d.x, 0.0)
        for cand in (left, right):
            cand_end = start + cand * lookahead
            if self._is_clear(start, cand_end):
                self._avoidance_vector = cand
                return cand
        self._avoidance_vector = Vec3(0.0, 0.0, 0.0)
        self.request_replan()
        return Vec3(0.0, 0.0, 0.0)

    def _is_clear(self, a: Vec3, b: Vec3) -> bool:
        if self.avoidance_check is not None:
            try:
                return bool(self.avoidance_check(a, b))
            except (RuntimeError, TypeError, AttributeError, ImportError, ValueError):
                return True
        try:
            from src.globals.physics import Physics

            hit = Physics.raycast_closest(
                a + Vec3(0, 0, self.eye_height),
                b + Vec3(0, 0, self.eye_height),
                self.obstacle_mask,
                step_physics=False,
            )
            return hit is None
        except (RuntimeError, TypeError, AttributeError, ImportError, ValueError):
            return True
