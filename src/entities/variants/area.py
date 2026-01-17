from ...globals.physics import Physics
from ..entity import Entity


class Area(Entity):
    def __init__(self) -> None:
        super().__init__()
        self.ghost = Physics.create_ghost(name=self.get_name())


    def get_node(self):
        return self.ghost