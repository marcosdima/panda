from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

from src.handlers.base import Handler
from src.utils.event import Event
from src.utils.position import world_position

if TYPE_CHECKING:
    from src.entities.entity import Entity
    from src.scenes import Scene


class ProximitySensorHandler(Handler):
    """Detect nearby entities by distance and emit enter/stay/exit events.

    Every frame it measures the distance from its own entity to every entity
    in ``scene.entities`` and maintains a set of *sensed* entities. It fires
    ``on_enter(entity, distance)`` when an entity enters the radius,
    ``on_stay(entity, distance)`` on every frame it stays inside, and
    ``on_exit(entity, distance)`` when it leaves. The payload carries the
    distance measured in that frame; when the entity can no longer be
    measured (it was freed), the last sensed distance is used instead.

    The sensor is a pure observer: it touches no Bullet world, writes no
    intent and moves nothing. That keeps it fully usable headless and lets it
    sit on any entity — a character, a trigger volume or an invisible marker.

    Hysteresis: ``exit_radius`` (defaults to ``radius``) is the threshold used
    for entities already inside. Set it above ``radius`` so a body hovering at
    the edge does not flicker between enter and exit.

    Constraints:

    - It scans ``scene.entities`` every frame, so it is O(n) in the number of
      entities in the scene. Use ``predicate`` to cheaply skip most of them.
    - Only entities registered in the scene are considered; a spawn that lives
      outside the scene is invisible to the sensor.
    - When the sensor is stopped or detached, ``clear()`` drops the sensed set
      without firing exit events (the world is going away, not the targets).
    - The sensor needs a ``scene``; without one it stays inert but keeps its
      configuration, which makes it safe to attach before the scene exists.
    """

    def __init__(
        self,
        radius: float,
        *,
        exit_radius: float | None = None,
        scene: "Scene | None" = None,
        predicate: "Callable[[Entity], bool] | None" = None,
    ) -> None:
        super().__init__()
        self._radius: float = self._validate_radius(radius, "radius")
        self._exit_radius: float = (
            self._radius
            if exit_radius is None
            else self._validate_radius(exit_radius, "exit_radius")
        )
        if self._exit_radius < self._radius:
            raise ValueError(
                f"exit_radius ({self._exit_radius}) must be >= radius ({self._radius})"
            )
        self._scene: "Scene | None" = scene
        self.predicate: "Callable[[Entity], bool] | None" = predicate

        self.on_enter: Event[tuple["Entity", float]] = Event()
        self.on_stay: Event[tuple["Entity", float]] = Event()
        self.on_exit: Event[tuple["Entity", float]] = Event()

        self._sensed: dict["Entity", float] = {}
        self._generation: int = 0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_radius(value: float, name: str) -> float:
        value = float(value)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be a finite positive number, got {value}")
        return value

    @property
    def scene(self) -> "Scene | None":
        """Scene whose registry is scanned; assigning a new scene clears the set."""
        return self._scene

    @scene.setter
    def scene(self, value: "Scene | None") -> None:
        if value is self._scene:
            return
        self._scene = value
        self.clear()

    @property
    def radius(self) -> float:
        """Outer range at which a new entity is sensed."""
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        radius = self._validate_radius(value, "radius")
        if self._exit_radius < radius:
            raise ValueError(
                f"radius ({radius}) must be <= exit_radius ({self._exit_radius})"
            )
        self._radius = radius

    @property
    def exit_radius(self) -> float:
        """Range an already-sensed entity must exceed to leave (hysteresis)."""
        return self._exit_radius

    @exit_radius.setter
    def exit_radius(self, value: float) -> None:
        exit_radius = self._validate_radius(value, "exit_radius")
        if exit_radius < self._radius:
            raise ValueError(
                f"exit_radius ({exit_radius}) must be >= radius ({self._radius})"
            )
        self._exit_radius = exit_radius

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def sensed_entities(self) -> list["Entity"]:
        """Currently sensed alive entities, nearest first."""
        alive = [
            (entity, distance)
            for entity, distance in self._sensed.items()
            if not entity.is_freed
        ]
        return [entity for entity, _distance in sorted(alive, key=lambda item: item[1])]

    @property
    def nearest(self) -> "Entity | None":
        """Closest sensed alive entity, or ``None`` when nothing is in range."""
        alive = [
            (entity, distance)
            for entity, distance in self._sensed.items()
            if not entity.is_freed
        ]
        if not alive:
            return None
        return min(alive, key=lambda item: item[1])[0]

    def distance_to(self, entity: "Entity") -> float | None:
        """Distance to ``entity``, or ``None`` when either side is unavailable."""
        if self.entity is None or entity.is_freed:
            return None
        return (world_position(entity) - world_position(self.entity)).length()

    def is_in_range(self, entity: "Entity") -> bool:
        """Return whether ``entity`` is currently sensed and alive."""
        return entity in self._sensed and not entity.is_freed

    def clear(self) -> None:
        """Drop every sensed entity without firing exit events.

        Bumping the generation also aborts the events still pending for the
        current frame, so a callback that clears the sensor does not receive
        the rest of the batch.
        """
        self._sensed.clear()
        self._generation += 1

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """Start with an empty sensed set (no stale entities across restarts)."""
        super().on_start()
        self.clear()

    def on_update(self, dt: float) -> None:
        """Recompute distances and dispatch enter/stay/exit events."""
        super().on_update(dt)
        scene = self._scene
        if self.entity is None or scene is None:
            return

        origin = world_position(self.entity)
        distances: dict["Entity", float] = {}
        for candidate in list(scene.entities.values()):
            if candidate is self.entity or candidate.is_freed:
                continue
            if self.predicate is not None and not self.predicate(candidate):
                continue
            distances[candidate] = (world_position(candidate) - origin).length()

        detected: dict["Entity", float] = {}
        for candidate, distance in distances.items():
            threshold = (
                self._exit_radius if candidate in self._sensed else self._radius
            )
            if distance <= threshold:
                detected[candidate] = distance

        previous = self._sensed
        self._sensed = detected
        generation = self._generation

        for entity, last_distance in list(previous.items()):
            if generation != self._generation:
                return  # a callback cleared the sensor during dispatch
            if entity in self._sensed:
                continue
            self.on_exit(entity, distances.get(entity, last_distance))

        for entity, distance in list(detected.items()):
            if generation != self._generation:
                return  # a callback cleared the sensor during dispatch
            if entity in previous:
                self.on_stay(entity, distance)
            else:
                self.on_enter(entity, distance)

    def on_stop(self) -> None:
        """Drop the sensed set when the entity deactivates."""
        super().on_stop()
        self.clear()

    def on_detach(self) -> None:
        """Drop the sensed set when the handler is removed."""
        super().on_detach()
        self.clear()


__all__ = ["ProximitySensorHandler"]
