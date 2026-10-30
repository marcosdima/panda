from __future__ import annotations
from src.utils.handler_phase import HandlerPhase

from enum import Enum
from typing import TYPE_CHECKING

from panda3d.core import Vec2, Vec3

from src.handlers.base import Handler
from src.handlers.input.action_map import SPRINT
from src.handlers.input.base import InputHandler
from src.utils.position import world_position

if TYPE_CHECKING:
    from src.entities.entity import Entity


class FollowState(str, Enum):
    phase = HandlerPhase.DECISION
    """Behavior states of :class:`FollowHandler`."""

    STOPPED = "stopped"
    FOLLOWING = "following"
    OUT_OF_RANGE = "out_of_range"


class FollowHandler(Handler):
    phase = HandlerPhase.DECISION
    """Lightweight "follow at distance" AI as a virtual input source.

    Each frame it computes the planar direction from its entity to a target
    entity and writes a move vector (and optional sprint flag) into the
    entity's :class:`InputHandler`, so any movement consumer (e.g.
    :class:`~src.handlers.physics.character.CharacterControllerHandler`)
    drives the follower exactly like a player.

    The follower moves toward the target when farther than ``stop_radius``
    and stops when within it. If ``max_distance`` is set and the target is
    beyond it, the handler gives up (``out_of_range``). The follower resumes
    following as soon as the target comes back within range.

    No waypoints and no state machine — a lightweight alternative to
    :class:`~src.handlers.ai.patrol.AIPatrolHandler` for companions, pets
    and escorts.

    The brain only reads world positions, which keeps it testable headless.
    Attach it **before** the movement handler so intent is fresh each tick.

    Constraints:

    - The written vector is **world-space**: it points straight at the target
      regardless of any camera on the follower entity. A follower that also
      carries a camera handler will walk along the camera's forward axis,
      not toward the target, because
      :class:`~src.handlers.physics.character.CharacterControllerHandler`
      interprets `(x, y)` as camera-relative when a camera handler is present
      on the same entity. Do not attach a camera handler to the follower.
    - Prefer one intent source per entity: if the follower also carries a
      :class:`~src.handlers.input.wasd.WASDInputHandler` (or another intent
      writer), the last writer in attach order wins each frame.
    - ``speed_factor`` scales the unit direction; the written vector is
      capped at unit length, so values above ``1.0`` have no further effect,
      and a negative value walks away from the target. When both
      ``stop_radius`` and ``max_distance`` apply, ``OUT_OF_RANGE`` takes
      precedence (the range check is evaluated before the stop check).
    """

    def __init__(
        self,
        target: "Entity | None" = None,
        min_distance: float = 1.5,
        max_distance: float | None = None,
        stop_radius: float | None = None,
        speed_factor: float = 1.0,
        chase_sprint: bool = False,
    ) -> None:
        super().__init__()
        self._target: "Entity | None" = target
        self._min_distance: float = float(min_distance)
        self._stop_radius: float = (
            self._min_distance if stop_radius is None else float(stop_radius)
        )
        self._stop_radius_is_explicit: bool = stop_radius is not None
        self.max_distance: float | None = (
            None if max_distance is None else float(max_distance)
        )
        self.speed_factor: float = float(speed_factor)
        self.chase_sprint: bool = bool(chase_sprint)
        self._last_move_vector: Vec2 = Vec2(0.0, 0.0)

    @property
    def target(self) -> "Entity | None":
        """Current follow target, or None."""
        return self._target

    @property
    def state(self) -> FollowState:
        """Current behavior state: ``STOPPED``, ``FOLLOWING`` or ``OUT_OF_RANGE``."""
        if self._target is None or self._target.is_freed:
            return FollowState.STOPPED
        distance = self._distance_to_target()
        if self.max_distance is not None and distance > self.max_distance:
            return FollowState.OUT_OF_RANGE
        if distance <= self.stop_radius:
            return FollowState.STOPPED
        return FollowState.FOLLOWING

    @property
    def min_distance(self) -> float:
        """Stop distance that mirrors ``stop_radius`` when it was not set explicitly.

        This property returns the value last assigned to ``min_distance``
        (the construction value by default). ``stop_radius`` is the only mutable stop-distance knob read at runtime. Assigning to ``min_distance``
        rewrites ``stop_radius`` too — unless ``stop_radius`` was set
        explicitly, in which case the write is inert and ``stop_radius``
        keeps its explicit value.
        """
        return self._min_distance

    @min_distance.setter
    def min_distance(self, value: float) -> None:
        self._min_distance = float(value)
        if not self._stop_radius_is_explicit:
            self._stop_radius = self._min_distance

    @property
    def stop_radius(self) -> float:
        """Effective stop distance (defaults to ``min_distance``)."""
        return self._stop_radius

    @stop_radius.setter
    def stop_radius(self, value: float) -> None:
        self._stop_radius = float(value)
        self._stop_radius_is_explicit = True

    @property
    def move_vector(self) -> Vec2:
        """Last movement intent written to the entity's InputHandler."""
        return Vec2(self._last_move_vector)

    def set_target(self, target: "Entity | None") -> None:
        """Set or clear the follow target."""
        self._target = target

    # --- lifecycle -------------------------------------------------------

    def on_start(self) -> None:
        super().on_start()
        self._write_intent(Vec2(0.0, 0.0), sprint=False)

    def on_stop(self) -> None:
        super().on_stop()
        self._write_intent(Vec2(0.0, 0.0), sprint=False)

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        if self.entity is None:
            return

        state = self.state
        if state == FollowState.FOLLOWING:
            direction = self._planar(self._target_position() - self._position())
            if direction.length_squared() > 1e-8:
                direction.normalize()
            direction *= self.speed_factor
            if direction.length_squared() > 1.0:
                direction.normalize()
            self._write_intent(Vec2(direction.x, direction.y), sprint=self.chase_sprint)
        else:
            self._write_intent(Vec2(0.0, 0.0), sprint=False)

    # --- intent ----------------------------------------------------------

    def _write_intent(self, vector: Vec2, sprint: bool) -> None:
        self._last_move_vector = Vec2(vector)
        if self.entity is None:
            return
        input_handler = self.entity.get_handler(InputHandler)
        if input_handler is None:
            return
        input_handler.set_move_vector(vector.x, vector.y)
        input_handler.set_action_state(SPRINT, sprint)

    # --- position resolution ---------------------------------------------

    def _position(self) -> Vec3:
        assert self.entity is not None
        return self._world_position(self.entity)

    def _target_position(self) -> Vec3:
        assert self._target is not None
        return self._world_position(self._target)

    @staticmethod
    def _world_position(entity: "Entity") -> Vec3:
        """Return the world position of an entity (delegates to ``utils.position``)."""
        return world_position(entity)

    @staticmethod
    def _planar(vec: Vec3) -> Vec3:
        return Vec3(vec.x, vec.y, 0.0)

    def _distance_to_target(self) -> float:
        assert self._target is not None
        return self._planar(self._target_position() - self._position()).length()
