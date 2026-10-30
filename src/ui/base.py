"""Base class shared by all reusable UI components."""

from __future__ import annotations

from typing import Any


class UIComponent:
    """Common lifecycle and visibility helpers for UI primitives."""

    def __init__(self, node: Any = None, theme: Any = None, owner: Any = None) -> None:
        self.node = node
        self.theme = theme
        self.owner = owner
        self._destroyed: bool = False

        if owner is not None and hasattr(owner, "_ui_components"):
            try:
                owner._ui_components.append(self)
            except Exception:  # noqa: BLE001, S110
                pass

    @property
    def destroyed(self) -> bool:
        return self._destroyed

    def is_valid(self) -> bool:
        return not self._destroyed and self.node is not None

    def set_visible(self, visible: bool) -> None:
        if self._destroyed or self.node is None:
            return
        try:
            if visible:
                self.node.show()
            else:
                self.node.hide()
        except Exception:  # noqa: BLE001, S110
            pass

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        node = self.node
        self.node = None
        if node is not None:
            try:
                node.destroy()
            except Exception:  # noqa: BLE001
                try:
                    node.removeNode()
                except Exception:  # noqa: BLE001, S110
                    pass
        if self.owner is not None and hasattr(self.owner, "_ui_components"):
            try:
                owner_components = self.owner._ui_components
                if self in owner_components:
                    owner_components.remove(self)
            except Exception:  # noqa: BLE001, S110
                pass
