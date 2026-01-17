from abc import ABC, abstractmethod


class Scene(ABC):
    __count: int = 0


    def __init__(self):
        self.id: int = Scene.__count
        Scene.__count += 1


    @abstractmethod
    def on_start(self):
        ''' Called when the scene starts. '''
        pass


    @abstractmethod
    def on_stop(self):
        ''' Called when the scene stops. '''
        pass
    