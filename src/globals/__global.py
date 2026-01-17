from typing import TYPE_CHECKING
from direct.showbase.ShowBase import ShowBase


if TYPE_CHECKING:
    base: ShowBase


class Global:
    ''' Base class for global managers. '''
    _instance: 'Global'


    def __new__(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        return cls._instance
    

    def __init__(self):
        self.base = base


    @classmethod
    def get_instance(cls):
        return cls._instance