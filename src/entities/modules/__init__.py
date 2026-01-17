from ..handlers.movement import Movement
from .shapes import Shapes
from .collision import Collision


class Joint(Shapes, Movement, Collision):
    pass


__all__ = [
    'Joint',
]