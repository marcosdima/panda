from enum import Enum
from src.utils.handler_phase import HandlerPhase
from typing import TYPE_CHECKING

from panda3d.core import BitMask32

if TYPE_CHECKING:
    from src.entities.entity import Entity


class CollisionGroup(Enum):
    phase = HandlerPhase.PHYSICS
    """Semantic collision groups used to classify physics entities.

    Groups are Python-side labels stored on handlers; trigger volumes use
    them to filter which overlapping entities trigger enter/exit events.
    Each group also exposes a corresponding ``BitMask32`` bit via :attr:`bitmask`.
    """

    DEFAULT = 0
    PLAYER = 2
    ENEMY = 3
    INTERACTABLE = 4
    PROP = 5

    @property
    def bitmask(self) -> BitMask32:
        """Return the ``BitMask32`` bit corresponding to this collision group."""
        return BitMask32.bit(int(self.value))


class CameraCollision:
    phase = HandlerPhase.PHYSICS
    """Bit-mask convention used by camera collision queries.

    World geometry keeps Bullet's default ``all_on`` into-collide mask, so it
    blocks the camera. Objects that must never push the camera (the player's own
    character capsule, trigger volumes) clear ``BLOCKER_BIT`` from their
    into-collide mask via ``non_blocking_mask`` and are therefore invisible to
    queries that use ``QUERY_MASK``. Ordinary physical collisions are unaffected
    because Bullet only requires the masks of two bodies to overlap in *any* bit.
    """

    BLOCKER_BIT: BitMask32 = BitMask32.bit(31)
    QUERY_MASK: BitMask32 = BitMask32.bit(31)

    @classmethod
    def non_blocking_mask(cls) -> BitMask32:
        """Return an into-collide mask that collides with everything except camera queries."""
        return BitMask32.all_on() & ~cls.BLOCKER_BIT


class LineOfSight:
    phase = HandlerPhase.PHYSICS
    """Bit-mask convention used by line-of-sight queries.

    A sight ray is cast with :attr:`QUERY_MASK` as its collision mask, so only
    bodies whose *into-collide* mask still carries the blocker bit can occlude
    it. World geometry keeps Bullet's default ``all_on`` mask and therefore
    blocks sight, while character controllers and trigger volumes clear that
    bit (through :meth:`CameraCollision.non_blocking_mask`) and stay invisible
    to the query: a character never hides itself from its own eyes and a
    trigger volume never blocks a view.

    The bit is deliberately the very same one used by :class:`CameraCollision`.
    Both queries answer the same question ("does this body get in the way of a
    camera or eye ray?") and both must ignore the player's own body, so
    sharing a single bit keeps one convention and one source of truth instead
    of two masks that could drift apart.
    """

    BLOCKER_BIT: BitMask32 = CameraCollision.BLOCKER_BIT
    QUERY_MASK: BitMask32 = CameraCollision.QUERY_MASK

    @classmethod
    def non_blocking_mask(cls) -> BitMask32:
        """Return an into-collide mask that never occludes a line-of-sight ray."""
        return CameraCollision.non_blocking_mask()


def resolve_collision_group(entity: "Entity") -> CollisionGroup:
    """Return the semantic collision group of an entity.

    Prefers the rigid body's group, then the character controller's, and falls
    back to ``DEFAULT`` for entities without a physics handler. Trigger zones,
    interactors and any other group-aware query share this single resolver so
    they cannot drift apart.

    Imports are function-local: ``src.handlers.physics`` imports this module and
    the physics handlers import their peers, so a module-level import would
    close the cycle.
    """
    from src.handlers.physics.character import CharacterControllerHandler
    from src.handlers.physics.rigid_body import RigidBodyHandler

    rigid = entity.get_handler(RigidBodyHandler)
    if rigid is not None:
        return rigid.collision_group
    character = entity.get_handler(CharacterControllerHandler)
    if character is not None:
        return character.collision_group
    return CollisionGroup.DEFAULT
