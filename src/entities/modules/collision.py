from enum import Enum


from calendar import c
from .__module import Module



class CollisionGroupEnum(Enum):
    ''' Enumeration for collision groups. '''
    DEFAULT = 0
    PLAYER = 2
    ENEMY = 3


class Collision(Module):
    ''' Module for handling collision groups of entities. '''
    CollisionGroup = CollisionGroupEnum


    def __init__(self):
        super().__init__()
        self.group: CollisionGroupEnum = CollisionGroupEnum.DEFAULT 


    def set_collision_group(self, group: CollisionGroupEnum):
        ''' Sets the collision group for the entity. '''
        self.group = group


    def get_collision_group(self) -> CollisionGroupEnum:
        ''' Gets the collision group of the entity. '''
        return self.group

