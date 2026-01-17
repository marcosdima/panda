from ...globals.physics import Physics
from ..entity import Entity


class Solid(Entity):
    def __init__(self, mass: float = 0.0) -> None:
        super().__init__()
        self.body = Physics.create_body(name=self.get_name(), mass=mass)


    def get_node(self):
        return self.body