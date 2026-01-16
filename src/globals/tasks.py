import panda3d
from typing import Callable
from .__global import Global


class Tasks(Global):
    ''' A singleton class to manage global tasks. '''
    _tasks = {}


    @classmethod
    def add_task(cls, name: str, task: Callable):
        task = cls._instance.base.taskMgr.add(task, name)
        cls._tasks[name] = task
        return task


    @classmethod
    def remove_task(cls, name: str):
        if name in cls._tasks:
            cls._instance.base.taskMgr.remove(cls._tasks[name])
            del cls._tasks[name]