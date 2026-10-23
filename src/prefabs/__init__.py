"""High-level prefabs and fluent entity builder."""

from .builder import EntityBuilder
from .common import (
    NpcRig,
    PlayerRig,
    create_patrol_npc,
    create_player,
    create_static_prop,
)

__all__ = [
    "EntityBuilder",
    "PlayerRig",
    "NpcRig",
    "create_player",
    "create_patrol_npc",
    "create_static_prop",
]