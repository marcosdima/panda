import inspect
from typing import TypeVar, Generic, Callable, TypeAlias


T = TypeVar('T')  # annotation-only payload type, e.g. Event[Entity]
CallbackMap: TypeAlias = dict[Callable[..., None], int]


class Event(Generic[T]):
    def __init__(
            self,
            check: Callable[[], bool] = lambda: True,
        ):
        self.__callback: CallbackMap = {}
        self.__takes_args: dict[Callable[..., None], bool] = {}
        self.__once: set[Callable[..., None]] = set()
        self.__check = check

    
    @staticmethod
    def __accepts_args(cb: Callable[..., None]) -> bool:
        ''' True unless the callback declares no parameters at all. '''
        try:
            return len(inspect.signature(cb).parameters) > 0
        except (TypeError, ValueError):
            return True


    def clear_callbacks(self) -> None:
        ''' Clear all callbacks. '''
        self.__callback.clear()
        self.__takes_args.clear()
        self.__once.clear()


    def add_callback(
        self,
        cb: Callable[..., None],
        priority: int = 0
    ) -> None:
        ''' Add a callback with an optional priority. '''
        self.__callback[cb] = priority
        self.__once.discard(cb)
        self.__takes_args[cb] = self.__accepts_args(cb)
        
        self.__callback = dict(
            sorted(
                self.__callback.items(),
                key=lambda item: item[1],
                reverse=True
            )
        )   


    def add_once(
        self,
        cb: Callable[..., None],
        priority: int = 0
    ) -> None:
        ''' Add a callback that is removed after its first execution. '''
        self.add_callback(cb, priority)
        self.__once.add(cb)


    def remove_callback(self, cb: Callable[..., None]) -> None:
        ''' Remove a callback. '''
        self.__callback.pop(cb, None)
        self.__takes_args.pop(cb, None)
        self.__once.discard(cb)


    def set_check(self, check: Callable[[], bool]) -> None:
        ''' Set the check function. '''
        self.__check = check


    def working(self) -> bool:
        ''' Check if the event is working. '''
        return self.__check()


    def debug(self) -> None:
        ''' Add a debug callback that prints when the event is triggered. '''
        self.add_callback(lambda *args, **kwargs: print("Event triggered with args:", args, "and kwargs:", kwargs))


    def __call__(self, *args, **kwargs) -> None:
        '''Call the event, executing all callbacks if working.'''
        if not self.working():
            return

        # Snapshot so callbacks may add/remove callbacks while dispatching.
        for cb in list(self.__callback):
            if cb not in self.__callback:
                continue
            takes_args = self.__takes_args.get(cb, True)
            if cb in self.__once:
                self.remove_callback(cb)
            if takes_args:
                cb(*args, **kwargs)
            else:
                cb()


    def __len__(self) -> int:
        return len(self.__callback)