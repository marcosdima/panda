from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from src.handlers.base import Handler
from src.handlers.physics.trigger_zone import TriggerZoneHandler

if TYPE_CHECKING:
    from src.entities.entity import Entity
    from src.scenes import Scene

logger = logging.getLogger(__name__)


class SpawnerHandler(Handler):
    """Spawn entities in reaction to its own entity's trigger zone.

    Reacts to the entity's :class:`TriggerZoneHandler.on_enter` event and
    builds a new entity through a caller-supplied factory, adding it to a
    :class:`Scene`. Every live tracked spawn is freed on ``on_stop``,
    ``on_detach`` or :meth:`clear_spawned`, so spawning never leaks entities
    or ids.

    This is the engine's first runtime entity-spawning mechanism. Detection
    (``TriggerZoneHandler``) and reaction (``SpawnerHandler``) live on the
    same entity, a clean split of concerns: the trigger only reports
    overlaps, the spawner only decides what to build and when.

    Degrades gracefully headless: it touches no graphics, physics or window
    API beyond reading the trigger event.
    """

    def __init__(
        self,
        entity_factory: Callable[[], "Entity"],
        scene: "Scene | None" = None,
        spawn_on_enter: bool = True,
        max_spawns: int | None = None,
        cooldown: float = 0.0,
    ) -> None:
        super().__init__()
        self.entity_factory: Callable[[], "Entity"] = entity_factory
        self.scene: "Scene | None" = scene
        self.spawn_on_enter: bool = bool(spawn_on_enter)
        self.max_spawns: int | None = max_spawns
        self.cooldown: float = float(cooldown)
        self._cooldown_left: float = 0.0

        self._spawned: list["Entity"] = []
        self._spawn_count: int = 0

        self._trigger: TriggerZoneHandler | None = None
        self._enter_cb: "Callable[[Entity], None] | None" = None

    @property
    def spawned_entities(self) -> list["Entity"]:
        """Alive entities currently tracked by this spawner.

        Spawns freed elsewhere (for example by ``HealthHandler``) are skipped
        instead of being reported as live.
        """
        return [entity for entity in self._spawned if not entity.is_freed]

    @property
    def spawn_count(self) -> int:
        """Total number of entities spawned since creation."""
        return self._spawn_count

    # ------------------------------------------------------------------
    # Spawning
    # ------------------------------------------------------------------

    def spawn(self) -> "Entity | None":
        """Build an entity via the factory, add it to the scene and track it.

        Returns the spawned entity, or ``None`` when ``max_spawns`` has been
        reached or the cooldown window is open.
        """
        if self.max_spawns is not None and self._spawn_count >= self.max_spawns:
            return None
        if self._cooldown_left > 0.0:
            return None

        entity = self.entity_factory()
        if self.scene is not None:
            self.scene.add_entity(entity)

        self._spawned.append(entity)
        self._spawn_count += 1
        self._cooldown_left = self.cooldown
        return entity

    def clear_spawned(self) -> None:
        """Free every tracked spawned entity and clear the tracking list.

        Each spawn is deregistered from the scene before being freed, but only
        when the registry still maps its id to that exact entity: ``Entity.free``
        recycles ids, so a stale entry could otherwise remove (and stop) an
        unrelated live entity that inherited the id. Spawns freed elsewhere are
        deregistered too — ``Entity.free`` does not touch the scene registry —
        and their ``free()`` is skipped because it is idempotent.
        """
        for entity in list(self._spawned):
            if self.scene is not None and self.scene.get_entity(entity.id) is entity:
                self.scene.remove_entity(entity)
            if not entity.is_freed:
                entity.free()
        self._spawned.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_attach(self, entity: "Entity") -> None:
        """Store the entity; locate the trigger on :meth:`on_start`."""
        super().on_attach(entity)
        self._trigger = None

    def on_start(self) -> None:
        """Subscribe to the entity's ``TriggerZoneHandler.on_enter``.

        The cooldown window restarts on every start, so a paused/stopped
        spawner does not resume with a stale remainder.
        """
        super().on_start()
        self._cooldown_left = 0.0
        if self.entity is None:
            return
        self._trigger = self.entity.get_handler(TriggerZoneHandler)
        if self._trigger is None:
            if self.spawn_on_enter:
                logger.warning(
                    "%s has no TriggerZoneHandler on entity %r; automatic "
                    "spawning is disabled (attach the trigger first).",
                    type(self).__name__,
                    self.entity,
                )
            return
        self._enter_cb = lambda entered: self._on_enter(entered)
        self._trigger.on_enter.add_callback(self._enter_cb)

    def on_stop(self) -> None:
        """Unsubscribe from the trigger and free all tracked spawns."""
        super().on_stop()
        self._unsubscribe()
        self.clear_spawned()

    def on_detach(self) -> None:
        """Unsubscribe, free all tracked spawns, and drop the entity reference.

        ``clear_spawned()`` runs here (not only in :meth:`on_stop`) because
        :meth:`Entity.free` skips :meth:`on_stop` for an entity that was
        never started — :meth:`on_detach` is the only cleanup hook that runs
        in that path.
        """
        self._unsubscribe()
        self.clear_spawned()
        super().on_detach()

    def on_update(self, dt: float) -> None:
        """Tick the cooldown window."""
        super().on_update(dt)
        if self._cooldown_left > 0.0:
            self._cooldown_left = max(0.0, self._cooldown_left - dt)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_enter(self, _entered: "Entity") -> None:
        """React to a trigger enter: spawn if armed, enabled and allowed.

        The entering entity is intentionally unused: the spawner does not
        filter or adapt to *who* entered, only *that* something entered.
        """
        if not self.is_enabled or not self.spawn_on_enter:
            return
        self.spawn()

    def _unsubscribe(self) -> None:
        """Remove the enter callback from the trigger, if subscribed."""
        if self._trigger is not None and self._enter_cb is not None:
            self._trigger.on_enter.remove_callback(self._enter_cb)
            self._enter_cb = None
        self._trigger = None
