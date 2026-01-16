import inspect
from typing import TypeVar, Generic, Callable, TypeAlias


T = TypeVar('T')
CallbackMap: TypeAlias = dict[Callable[..., None], int]


class Event(Generic[T]):
    def __init__(
            self,
            check: Callable[[], bool] = lambda: True,
        ):
        self.__callback: CallbackMap = {}
        self.__check = check

    
    def clear_callbacks(self):
        ''' Clear all callbacks. '''
        self.__callback.clear()


    def add_callback(
        self,
        cb: Callable[..., None],
        priority: int = 0
    ):
        ''' Add a callback with an optional priority. '''
        self.__callback[cb] = priority
        
        self.__callback = dict(
            sorted(
                self.__callback.items(),
                key=lambda item: item[1],
                reverse=True
            )
        )   


    def remove_callback(self, cb: Callable[..., None]):
        ''' Remove a callback. '''
        self.__callback.pop(cb, None)


    def set_check(self, check: Callable[[], bool]):
        ''' Set the check function. '''
        self.__check = check


    def working(self) -> bool:
        ''' Check if the event is working. '''
        return self.__check()


    def debug(self):
        ''' Add a debug callback that prints when the event is triggered. '''
        self.add_callback(lambda *args, **kwargs: print("Event triggered with args:", args, "and kwargs:", kwargs))


    def __call__(self, *args, **kwargs):
        '''Call the event, executing all callbacks if working.'''
        if not self.working():
            return

        for cb in self.__callback:
            sig = inspect.signature(cb)
            if len(sig.parameters) == 0:
                cb()
            else:
                cb(*args, **kwargs)


    def __len__(self) -> int:
        return len(self.__callback)