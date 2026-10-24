"""Authoritative world-position resolution for entities.

A handler that reads positions (AI brains, sensors, cameras) must agree on
*where* an entity is. A ``CharacterControllerHandler`` moves its own Bullet
node, so the entity node stays where it was authored and is not authoritative.
This module owns that rule so every consumer resolves positions the same way.

Layering note: this module lives in ``src/utils`` but needs the character
controller type. The import is function-local on purpose: ``src.handlers``
imports ``src.utils`` and ``src.handlers.physics.character`` imports
``src.utils.math``, so a module-level import would close the cycle. Keep it
inside the function unless the dependency moves out of ``src/utils``.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from panda3d.core import NodePath, Vec3

if TYPE_CHECKING:
    from src.entities.entity import Entity


def _resolve(node: NodePath, render: NodePath | None) -> Vec3:
    """Return ``node`` in ``render`` space, or in its graph-root space headless.

    Headless scenes have no ``render``. Resolving against the top-most ancestor
    keeps the result world-like even when entity nodes are parented to each
    other, which a plain ``getPos()`` would report as a parent-local offset.
    """
    if render is not None and node.hasParent():
        return Vec3(node.getPos(render))

    root = node
    while root.hasParent():
        root = root.getParent()
    if root is node:
        return Vec3(node.getPos())
    return Vec3(root.getMat().xformPoint(node.getPos(root)))


def world_position(entity: "Entity") -> Vec3:
    """Return the authoritative world position of an entity.

    Prefers the character controller's node when one is attached and valid,
    then a rigid body's node when one is attached and valid, because physics
    handlers move their own Bullet nodes instead of ``entity.node``. Falls
    back to ``entity.node`` for every other entity. Returns the origin for an
    entity whose node is empty.
    """
    from src.handlers.physics.character import CharacterControllerHandler
    from src.handlers.physics.rigid_body import RigidBodyHandler

    base = getattr(builtins, "base", None)
    render = getattr(base, "render", None) if base is not None else None

    controller = entity.get_handler(CharacterControllerHandler)
    if controller is not None and controller.controller_np is not None:
        controller_np = controller.controller_np
        if not controller_np.isEmpty():
            return _resolve(controller_np, render)

    rigid = entity.get_handler(RigidBodyHandler)
    if rigid is not None and rigid.body_np is not None:
        body_np = rigid.body_np
        if not body_np.isEmpty():
            return _resolve(body_np, render)

    node = entity.node
    if node is None or node.isEmpty():
        return Vec3(0.0, 0.0, 0.0)
    return _resolve(node, render)


__all__ = ["world_position"]
