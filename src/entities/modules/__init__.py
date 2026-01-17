from ..handlers.movement import Movement
from .shapes import Shapes


class Joint(Shapes, Movement):
    pass


__all__ = [
    'Joint',
]