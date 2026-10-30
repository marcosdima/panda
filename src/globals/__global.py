import builtins
from typing import TYPE_CHECKING

from direct.showbase.ShowBase import ShowBase

if TYPE_CHECKING:
    base: ShowBase


class Global:
    """Base class for global managers."""

    _instance: "Global"

    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self._base: ShowBase | None = getattr(builtins, "base", None)

    @property
    def base(self) -> ShowBase | None:
        if hasattr(self, "_base") and self._base is not None:
            return self._base
        return getattr(builtins, "base", None)

    @base.setter
    def base(self, value: ShowBase | None) -> None:
        self._base = value

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            cls()
        return cls._instance
