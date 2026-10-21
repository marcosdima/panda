from enum import Enum

from panda3d.core import BitMask32


class CollisionGroup(Enum):
    """Semantic collision groups used to classify physics entities.

    Groups are Python-side labels stored on handlers; trigger volumes use
    them to filter which overlapping entities trigger enter/exit events.
    """

    DEFAULT = 0
    PLAYER = 2
    ENEMY = 3


class CameraCollision:
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
