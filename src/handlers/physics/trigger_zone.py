from __future__ import annotations

from panda3d.bullet import BulletGhostNode, BulletShape
from panda3d.core import NodePath, TransformState

from src.entities.entity import Entity
from src.globals.physics import Physics
from src.handlers.base import Handler
from src.utils.event import Event
from .character import CharacterControllerHandler
from .groups import CameraCollision, CollisionGroup
from .rigid_body import RigidBodyHandler


class TriggerZoneHandler(Handler):
    """Modular physics handler encapsulating a BulletGhostNode trigger volume.

    Detects overlapping physics entities each frame and emits edge-triggered
    `on_enter` / `on_exit` events plus per-frame `on_stay` and `on_rejected`
    events. Entities are filtered by their handler's `CollisionGroup`
    (`target_groups` / `avoid_groups`); selective zones skip ambient
    `CollisionGroup.DEFAULT` environment overlaps (see `_is_ambient`).
    The ghost has collision response
    disabled so bodies and characters pass through the volume unimpeded.

    The trigger's own ghost node is intentionally not tagged with its entity,
    so triggers detect physical bodies and characters but never each other.
    """

    def __init__(
        self,
        shape: BulletShape,
        target_groups: set[CollisionGroup] | None = None,
        avoid_groups: set[CollisionGroup] | None = None,
    ) -> None:
        super().__init__()
        self.shape: BulletShape = shape
        self.target_groups: set[CollisionGroup] = set(target_groups) if target_groups else set()
        self.avoid_groups: set[CollisionGroup] = set(avoid_groups) if avoid_groups else set()
        self.ghost_node: BulletGhostNode | None = None
        self.ghost_np: NodePath | None = None
        self._is_attached_to_world: bool = False
        self._overlapping: dict[Entity, CollisionGroup] = {}
        self._last_parent_net: TransformState | None = None

        self.on_enter: Event[Entity] = Event()
        self.on_stay: Event[Entity] = Event()
        self.on_exit: Event[Entity] = Event()
        self.on_rejected: Event[Entity] = Event()

    @property
    def overlapping_entities(self) -> list[Entity]:
        """Return the entities currently overlapping this trigger (accepted by filters)."""
        return list(self._overlapping.keys())

    def is_overlapping(self, entity: Entity) -> bool:
        """Return True if the given entity is currently overlapping this trigger."""
        return entity in self._overlapping

    def _attach_to_world(self) -> None:
        """Attach the ghost node to the active Bullet physics world."""
        if not self._is_attached_to_world and self.ghost_node is not None:
            Physics.get_world().attachGhost(self.ghost_node)
            self._is_attached_to_world = True

    def _detach_from_world(self) -> None:
        """Remove the ghost node cleanly from the active Bullet physics world."""
        if self._is_attached_to_world and self.ghost_node is not None:
            Physics.get_world().removeGhost(self.ghost_node)
            self._is_attached_to_world = False

    def on_attach(self, entity: Entity) -> None:
        """Create the ghost node, parent it to the entity, and join the world."""
        super().on_attach(entity)
        if self.ghost_node is None:
            self.ghost_node = BulletGhostNode(entity.name)
            self.ghost_node.addShape(self.shape)
            self.ghost_node.setCollisionResponse(False)
            # Trigger volumes are not solid: camera queries must pass through them.
            self.ghost_node.setIntoCollideMask(CameraCollision.non_blocking_mask())
        else:
            self.ghost_node.setName(entity.name)

        if self.ghost_np is None or self.ghost_np.isEmpty():
            self.ghost_np = entity.node.attachNewNode(self.ghost_node)
        if self.ghost_np is not None and not self.ghost_np.isEmpty():
            self._last_parent_net = self.ghost_np.getParent().getNetTransform()

        self._attach_to_world()

    def on_start(self) -> None:
        """Called when active scene or entity starts."""
        super().on_start()
        if self.entity is not None and (self.ghost_np is None or self.ghost_np.isEmpty()):
            if self.ghost_node is not None:
                self.ghost_np = self.entity.node.attachNewNode(self.ghost_node)
                self._last_parent_net = self.ghost_np.getParent().getNetTransform()
        self._attach_to_world()

    def on_update(self, dt: float) -> None:
        """Propagate moves of `entity.node`, then check overlaps and fire edge events.

        Parent transform changes since the last frame flag the ghost as
        authoritative so the next physics step adopts the new entity
        transform (same semantics as `RigidBodyHandler`). Untouched ghosts
        stay under Bullet's control.
        """
        super().on_update(dt)
        if self.ghost_node is None:
            return
        if self.ghost_np is not None and not self.ghost_np.isEmpty():
            parent_net = self.ghost_np.getParent().getNetTransform()
            if parent_net != self._last_parent_net:
                self.ghost_node.setTransformDirty()
                self._last_parent_net = parent_net
        self._check_overlaps()

    def _check_overlaps(self) -> None:
        """Diff ghost overlaps against the previous frame and emit events."""
        if self.ghost_node is None:
            return

        accepted: dict[Entity, CollisionGroup] = {}
        rejected: set[Entity] = set()

        for node in self.ghost_node.getOverlappingNodes():
            if not node.hasPythonTag("entity"):
                continue
            entity = node.getPythonTag("entity")
            if not isinstance(entity, Entity):
                continue
            group = self._resolve_group(entity)
            if self._is_ambient(group):
                continue
            if self._validate(group):
                accepted[entity] = group
            else:
                rejected.add(entity)

        for entity in accepted:
            if entity not in self._overlapping:
                self.on_enter(entity)
        for entity in accepted:
            self.on_stay(entity)
        for entity in self._overlapping:
            if entity not in accepted:
                self.on_exit(entity)
        for entity in rejected:
            self.on_rejected(entity)

        self._overlapping = accepted

    def _validate(self, group: CollisionGroup) -> bool:
        """Return True if an overlap from the given group should be accepted."""
        if self.target_groups and group not in self.target_groups:
            return False
        if self.avoid_groups and group in self.avoid_groups:
            return False
        return True

    def _is_ambient(self, group: CollisionGroup) -> bool:
        """Return True for ungrouped environment overlaps of a selective zone.

        Broadphase AABBs are inflated by Bullet's collision margins, so static
        environment bodies (e.g. the ground under a floating zone) report an
        overlap even when their geometry does not touch the ghost. Selective
        zones (with explicit `target_groups`) treat `CollisionGroup.DEFAULT`
        entities as ambient environment and skip them entirely, so static
        scenery never emits enter/exit/rejected noise. Zones without filters
        and zones that explicitly list `DEFAULT` keep their usual behavior.
        """
        if group is not CollisionGroup.DEFAULT:
            return False
        if not self.target_groups:
            return False
        return (
            CollisionGroup.DEFAULT not in self.target_groups
            and CollisionGroup.DEFAULT not in self.avoid_groups
        )

    @staticmethod
    def _resolve_group(entity: Entity) -> CollisionGroup:
        """Resolve the collision group of an entity via its physics handlers."""
        rigid = entity.get_handler(RigidBodyHandler)
        if rigid is not None:
            return rigid.collision_group
        character = entity.get_handler(CharacterControllerHandler)
        if character is not None:
            return character.collision_group
        return CollisionGroup.DEFAULT

    def on_stop(self) -> None:
        """Detach the ghost from the world, remove its NodePath, and reset state."""
        super().on_stop()
        self._detach_from_world()
        if self.ghost_np is not None and not self.ghost_np.isEmpty():
            self.ghost_np.removeNode()
        self.ghost_np = None
        self._overlapping.clear()
        self._last_parent_net = None

    def on_detach(self) -> None:
        """Fully release the ghost node when the handler is removed from its entity."""
        self._detach_from_world()
        if self.ghost_np is not None and not self.ghost_np.isEmpty():
            self.ghost_np.removeNode()
        self.ghost_np = None
        self.ghost_node = None
        self._overlapping.clear()
        self._last_parent_net = None
        super().on_detach()
