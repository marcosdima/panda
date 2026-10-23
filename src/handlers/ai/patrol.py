from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Callable, Sequence

from panda3d.core import BitMask32, Vec3

from src.globals.physics import Physics
from src.handlers.base import Handler
from src.handlers.input.base import InputHandler
from src.handlers.input.action_map import SPRINT
from src.handlers.physics.groups import LineOfSight
from src.utils.position import world_position
from src.utils.state_machine import StateMachine

if TYPE_CHECKING:
    from src.entities.entity import Entity


class PatrolState(str, Enum):
    """Behavior states of :class:`AIPatrolHandler`."""

    PATROL = "patrol"
    WAIT = "wait"
    CHASE = "chase"


_TRANSITIONS = {
    PatrolState.PATROL: [PatrolState.WAIT, PatrolState.CHASE],
    PatrolState.WAIT: [PatrolState.PATROL, PatrolState.CHASE],
    PatrolState.CHASE: [PatrolState.PATROL],
}


class AIPatrolHandler(Handler):
    """Waypoint patrol with optional target detection and chase.

    The handler is a *virtual input source*: each frame it writes a horizontal
    movement intent (and the ``sprint`` action while chasing) into the
    entity's :class:`InputHandler`, so any consumer of that interface (e.g.
    ``CharacterControllerHandler``) moves the NPC exactly like a player.
    Attach it **before** the movement handler so intent is fresh each tick.

    Decision making only reads world positions, which keeps it testable
    headless. Line of sight defaults to a Bullet raycast and can be replaced
    through ``line_of_sight``.

    **Line of sight semantics:** a ray is cast from the observer's eye to the
    target's eye and the *first hit decides*. A hit on world geometry blocks
    the sight, while a hit on the observer's or the target's own body does
    not: a body never hides its owner from itself. ``arrive_radius`` plays no
    role in that test, it only governs waypoint arrival and how close the NPC
    stops while chasing.

    The ray is cast with :attr:`LineOfSight.QUERY_MASK`, so world geometry
    occludes it while character controllers and trigger volumes (which clear
    the shared blocker bit) never do.
    """

    def __init__(
        self,
        waypoints: Sequence[Vec3] = (),
        arrive_radius: float = 0.5,
        wait_time: float = 1.0,
        ping_pong: bool = False,
        target: "Entity | None" = None,
        sight_range: float = 8.0,
        lose_range: float | None = None,
        chase_sprint: bool = True,
        obstacle_mask: BitMask32 | None = None,
        eye_height: float = 1.0,
        line_of_sight: Callable[[Vec3, Vec3], bool] | None = None,
    ) -> None:
        super().__init__()
        self.waypoints: list[Vec3] = [Vec3(w) for w in waypoints]
        self.arrive_radius = arrive_radius
        self.wait_time = wait_time
        self.ping_pong = ping_pong
        self.target = target
        self.sight_range = sight_range
        self.lose_range = lose_range if lose_range is not None else sight_range * 1.5
        self.chase_sprint = chase_sprint
        self.obstacle_mask = (
            obstacle_mask if obstacle_mask is not None else LineOfSight.QUERY_MASK
        )
        self.eye_height = eye_height
        self._line_of_sight = line_of_sight

        self.machine = StateMachine(PatrolState.PATROL, _TRANSITIONS)
        self._index = 0
        self._direction = 1
        self._wait_left = 0.0

    @property
    def state(self) -> PatrolState:
        """Current behavior state."""
        return self.machine.state  # type: ignore[return-value]

    @property
    def current_waypoint(self) -> Vec3 | None:
        """Waypoint currently being approached, or None when there are none."""
        if not self.waypoints:
            return None
        return self.waypoints[self._index]

    @property
    def line_of_sight(self) -> Callable[[Vec3, Vec3], bool] | None:
        """Injected line-of-sight callable, or None to use the Bullet raycast."""
        return self._line_of_sight

    @line_of_sight.setter
    def line_of_sight(self, value: Callable[[Vec3, Vec3], bool] | None) -> None:
        """Replace the line-of-sight source at runtime (None restores the raycast)."""
        self._line_of_sight = value

    def can_see_target(self) -> bool:
        """Return True when the target is currently visible to the observer."""
        if self.entity is None or self.target is None or self.target.is_freed:
            return False
        return self._can_see_target()

    # --- lifecycle -------------------------------------------------------

    def on_start(self) -> None:
        super().on_start()
        self.machine.reset(PatrolState.PATROL)
        self._wait_left = 0.0

    def on_stop(self) -> None:
        super().on_stop()
        self._drive(Vec3(0, 0, 0), sprint=False)

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        if self.entity is None:
            return

        self._update_detection()

        state = self.state
        if state == PatrolState.CHASE:
            self._update_chase()
        elif state == PatrolState.WAIT:
            self._update_wait(dt)
        else:
            self._update_patrol()

    # --- states ----------------------------------------------------------

    def _update_detection(self) -> None:
        if self.target is None or self.target.is_freed:
            if self.state == PatrolState.CHASE:
                self.machine.transition(PatrolState.PATROL)
            return
        dist = self._distance_to_target()
        if self.state == PatrolState.CHASE:
            # The target is already lost when it goes out of range, so the
            # sight ray is only cast while the target is still reachable.
            if dist > self.lose_range:
                self.machine.transition(PatrolState.PATROL)
                return
            if not self._can_see_target():
                self.machine.transition(PatrolState.PATROL)
            return
        if dist > self.sight_range:
            return
        if self._can_see_target():
            self.machine.transition(PatrolState.CHASE)

    def _update_patrol(self) -> None:
        goal = self.current_waypoint
        if goal is None:
            self._drive(Vec3(0, 0, 0), sprint=False)
            return
        to_goal = self._planar(goal - self._position())
        if to_goal.length() <= self.arrive_radius:
            self._advance_waypoint()
            self._wait_left = self.wait_time
            self._drive(Vec3(0, 0, 0), sprint=False)
            if self._wait_left > 0.0:
                self.machine.transition(PatrolState.WAIT)
            return
        self._drive(to_goal, sprint=False)

    def _update_wait(self, dt: float) -> None:
        self._drive(Vec3(0, 0, 0), sprint=False)
        self._wait_left -= dt
        if self._wait_left <= 0.0:
            self.machine.transition(PatrolState.PATROL)

    def _update_chase(self) -> None:
        assert self.target is not None
        to_target = self._planar(self._target_position() - self._position())
        stop_at = self.arrive_radius
        if to_target.length() <= stop_at:
            self._drive(Vec3(0, 0, 0), sprint=False)
        else:
            self._drive(to_target, sprint=self.chase_sprint)

    # --- helpers ---------------------------------------------------------

    def _advance_waypoint(self) -> None:
        count = len(self.waypoints)
        if count <= 1:
            return
        if self.ping_pong:
            if not 0 <= self._index + self._direction < count:
                self._direction = -self._direction
            self._index += self._direction
        else:
            self._index = (self._index + 1) % count

    def _position(self) -> Vec3:
        assert self.entity is not None
        return self._world_position(self.entity)

    def _target_position(self) -> Vec3:
        assert self.target is not None
        return self._world_position(self.target)

    @staticmethod
    def _world_position(entity: "Entity") -> Vec3:
        """Return the world position of an entity (delegates to ``utils.position``)."""
        return world_position(entity)

    @staticmethod
    def _planar(vec: Vec3) -> Vec3:
        return Vec3(vec.x, vec.y, 0.0)

    def _distance_to_target(self) -> float:
        assert self.target is not None
        return self._planar(self._target_position() - self._position()).length()

    def _can_see_target(self) -> bool:
        """Return True when nothing blocks the eye-to-eye ray towards the target.

        The first hit decides: world geometry blocks the sight, while a hit on
        the observer's or the target's own body does not, because a body never
        hides its owner from itself.
        """
        assert self.entity is not None
        assert self.target is not None
        eye = self._position() + Vec3(0, 0, self.eye_height)
        goal = self._target_position() + Vec3(0, 0, self.eye_height)
        if self._line_of_sight is not None:
            return bool(self._line_of_sight(eye, goal))
        hit = Physics.raycast_closest(eye, goal, self.obstacle_mask, step_physics=False)
        if hit is None:
            return True
        _, hit_node = hit
        if hit_node is None:
            return False
        hit_entity = hit_node.getPythonTag("entity")
        if hit_entity is None:
            return False
        return hit_entity is self.entity or hit_entity is self.target

    def _drive(self, direction: Vec3, sprint: bool) -> None:
        """Write movement intent into the entity's InputHandler."""
        if self.entity is None:
            return
        input_handler = self.entity.get_handler(InputHandler)
        if input_handler is None:
            return
        if direction.length_squared() > 1e-8:
            direction = Vec3(direction)
            direction.normalize()
        input_handler.set_move_vector(direction.x, direction.y)
        input_handler.set_action_state(SPRINT, sprint)
