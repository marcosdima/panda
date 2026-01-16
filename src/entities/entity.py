from .modules import Joint


class Entity(Joint):
    __next = [0]
    __count = 0


    def __init__(self) -> None:
        self.id = self.__next.pop()
        self.__count += 1

        if len(self.__next) == 0:
            self.__next.append(self.__count)
        
        super().__init__()


    def free(self):
        super().free()
        self.__next.append(self.id)
        self.__count -= 1
