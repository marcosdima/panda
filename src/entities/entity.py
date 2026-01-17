from abc import ABC, abstractmethod
from panda3d.core import NodePath


from .modules import Joint


class Entity(ABC, Joint):
    __next = [0]
    __count = 0


    def __init__(self) -> None:
        # Id assignment.
        self.id = self.__next.pop()
        self.__count += 1

        if len(self.__next) == 0:
            self.__next.append(self.__count)
        
        super().__init__()

        # Set main node.
        self.node = self.get_node()
        self.node.setName(self.get_name())


    def free(self):
        super().free()
        self.__next.append(self.id)
        self.__count -= 1


    def get_name(self) -> str:
        return f'Entity-{self.id}'
    

    def setup(self) -> None:
        ''' Method to setup the entity after all modules are initialized. '''
        for shape in self.get_shapes().values():
            self.node.addShape(shape)
    

    @abstractmethod
    def get_node(self) -> NodePath:
        ''''''
        pass
    
