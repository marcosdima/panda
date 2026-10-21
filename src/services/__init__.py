# src/services/__init__.py
"""Service Locator for global singleton-like objects.

This module provides a simple, type‑annotated way to register and retrieve
services (e.g., physics world, loader, camera manager) without relying on
module‑level globals. It enables easy dependency injection for handlers and
facilitates testing with mock services.

Typical usage:
```python
from src.services import services

# Register a service (once, usually during engine start‑up)
services.register('physics', physics_world)

# Retrieve a service elsewhere
physics = services.get('physics')
```
"""

from __future__ import annotations

from typing import Any, Dict, TypeVar, cast

_T = TypeVar("_T")
_SENTINEL = object()


class _ServiceLocator:
    """Internal singleton that holds registered services.

    The locator stores services in a dictionary keyed by a string name. When a
    service is requested, the caller can optionally provide the expected type to
    get a properly typed result, or provide a default fallback value.
    """

    __slots__ = ("_services",)

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """Register *service* under *name*.

        If a service with the same name already exists, it will be overwritten.
        This mirrors typical singleton registration patterns where the final
        configuration wins.
        """
        self._services[name] = service

    def has(self, name: str) -> bool:
        """Check if a service is registered under *name*."""
        return name in self._services

    def __contains__(self, name: str) -> bool:
        """Check if a service is registered using the `in` operator."""
        return name in self._services

    def get(
        self,
        name: str,
        typ: type[_T] | None = None,
        default: Any = _SENTINEL,
    ) -> Any:
        """Retrieve a registered service.

        Args:
            name: The service identifier used during registration.
            typ: Optional type hint for static type checkers.
            default: Optional default value returned if *name* is not registered.
                If not specified, a KeyError is raised.

        Returns:
            The registered service instance or *default*.

        Raises:
            KeyError: If *name* is not found in the registry and no default is provided.
        """
        if name not in self._services:
            if default is not _SENTINEL:
                return default
            raise KeyError(f"Service '{name}' not registered.")
        service = self._services[name]
        return cast(_T, service) if typ is not None else service

    def clear(self) -> None:
        """Remove all registered services. Useful for test teardown."""
        self._services.clear()

# Export a module‑level singleton instance for convenient import
services = _ServiceLocator()

__all__ = ["services", "_ServiceLocator"]
