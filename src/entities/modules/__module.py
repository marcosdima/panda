from ...utils import Event

class Module:
    def __init__(self) -> None:
        self.on_free = Event()


    def free(self) -> None:
        ''' Frees the module and triggers the on_free event. '''
        self.on_free()