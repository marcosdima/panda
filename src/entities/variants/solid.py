from ...globals.physics import Physics
from ..entity import Entity


class Solid(Entity):
    def __init__(self, mass: float = 0.0, name: str | None = None):
        super().__init__(name=name)
        self.body = Physics.create_body(name=self.name, mass=mass)

    def free(self):
        Physics.remove_body(self.body)
        super().free()

    def _get_node(self):
        return self.body