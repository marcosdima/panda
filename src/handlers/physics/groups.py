from enum import Enum


class CollisionGroup(Enum):
    """Semantic collision groups used to classify physics entities.

    Groups are Python-side labels stored on handlers; trigger volumes use
    them to filter which overlapping entities trigger enter/exit events.
    """

    DEFAULT = 0
    PLAYER = 2
    ENEMY = 3
