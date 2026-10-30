import logging
from typing import ClassVar

from direct.task import Task
from panda3d.bullet import (
    BulletCharacterControllerNode,
    BulletDebugNode,
    BulletGhostNode,
    BulletRigidBodyNode,
    BulletSphereShape,
    BulletWorld,
)
from panda3d.core import BitMask32, NodePath, TransformState, Vec3

from .__global import Global
from .clock import GlobalClock

logger = logging.getLogger(__name__)


class Physics(Global):
    """A singleton class to manage the Bullet Physics world."""

    FIXED_TIMESTEP: float = 1.0 / 60.0
    MAX_SUBSTEPS: int = 10

    _world: BulletWorld | None = None
    _bodies: ClassVar[dict[str, BulletRigidBodyNode]] = {}
    _ghosts: ClassVar[dict[str, BulletGhostNode]] = {}
    _debug_np: NodePath | None = None
    _paused: bool = False
    _registry: ClassVar[dict[str, set]] = {
        "bodies": set(),
        "ghosts": set(),
        "constraints": set(),
    }
    _constraints: ClassVar[dict[str, object]] = {}

    def __init__(self) -> None:
        super().__init__()
        Physics._ensure_world()
        self._setup_debug_and_tasks()

    @classmethod
    def _ensure_world(cls) -> BulletWorld:
        """Ensure BulletWorld is created and gravity is configured."""
        if cls._world is None:
            cls._world = BulletWorld()
            cls._world.setGravity(Vec3(0, 0, -9.81))
        return cls._world

    def _setup_debug_and_tasks(self) -> None:
        """Initialize debug visualization and physics world update task if engine is active."""
        self._debug()
        if self.base is not None and getattr(self.base, "task_mgr", None) is not None:
            if not self.base.task_mgr.hasTaskNamed("physics_world_updater"):
                self.base.task_mgr.add(self._update_world, "physics_world_updater")

    def _debug(self) -> None:
        """Set up debug visualization for Bullet Physics bodies and ghosts if display is active."""
        if Physics._world is None:
            return
        if self.base is None or getattr(self.base, "render", None) is None:
            return
        # Headless check: if no graphics window (e.g., windowType='none'), do not attach debug visualization
        if getattr(self.base, "win", None) is None:
            return

        try:
            debug_node = BulletDebugNode("Physics_Debug")
            debug_node.showWireframe(True)
            debug_node.showConstraints(True)
            debug_node.showBoundingBoxes(False)
            debug_node.showNormals(False)

            debug_np = self.base.render.attachNewNode(debug_node)
            debug_np.show()
            Physics._debug_np = debug_np
            Physics._world.setDebugNode(debug_np.node())
        except Exception:
            logger.warning(
                "Failed to set up Bullet debug visualization.", exc_info=True
            )

    @classmethod
    def toggle_debug(cls) -> bool:
        """Toggle Bullet debug wireframe visualization."""
        if cls._debug_np is not None and not cls._debug_np.isEmpty():
            if cls._debug_np.isHidden():
                cls._debug_np.show()
                return True
            else:
                cls._debug_np.hide()
                return False

        # If debug node hasn't been attached yet, attempt to initialize it
        base = (
            getattr(cls.get_instance(), "base", None)
            if hasattr(cls, "_instance")
            else None
        )
        if base is None:
            import builtins

            base = getattr(builtins, "base", None)
        if base is not None and getattr(base, "render", None) is not None:
            try:
                debug_node = BulletDebugNode("Physics_Debug")
                debug_node.showWireframe(True)
                debug_node.showConstraints(True)
                debug_node.showBoundingBoxes(False)
                debug_node.showNormals(False)

                debug_np = base.render.attachNewNode(debug_node)
                debug_np.show()
                cls._debug_np = debug_np
                cls.get_world().setDebugNode(debug_np.node())
                return True
            except Exception:
                logger.warning(
                    "Failed to enable Bullet debug visualization.", exc_info=True
                )
                return False
        return False

    @classmethod
    def is_debug_enabled(cls) -> bool:
        """Return True if physics debug wireframe is currently enabled and visible."""
        if cls._debug_np is not None and not cls._debug_np.isEmpty():
            return not cls._debug_np.isHidden()
        return False

    @classmethod
    def set_paused(cls, paused: bool) -> None:
        """Pause or resume the Bullet physics simulation step."""
        cls._paused = bool(paused)

    @classmethod
    def is_paused(cls) -> bool:
        """Return True if the Bullet physics simulation is paused."""
        return cls._paused

    def _update_world(self, task: Task) -> int:
        dt = GlobalClock.get_dt()
        paused = Physics._paused or bool(getattr(self.base, "paused", False))
        if not paused and Physics._world is not None:
            Physics._world.doPhysics(dt, Physics.MAX_SUBSTEPS, Physics.FIXED_TIMESTEP)
        return task.cont

    @classmethod
    def get_world(cls) -> BulletWorld:
        """Get the Bullet Physics world, initializing it if necessary."""
        return cls._ensure_world()

    @classmethod
    def create_body(cls, name: str, mass: float = 0.0) -> BulletRigidBodyNode:
        """Create a rigid body, add it to the world, and return it."""
        world = cls._ensure_world()
        node = BulletRigidBodyNode(name)
        node.setMass(mass)
        world.attachRigidBody(node)
        cls._bodies[name] = node
        cls._registry["bodies"].add(node)
        return node

    @classmethod
    def create_ghost(cls, name: str) -> BulletGhostNode:
        """Create a ghost body, add it to the world, and return it."""
        world = cls._ensure_world()
        node = BulletGhostNode(name)
        world.attachGhost(node)
        cls._ghosts[name] = node
        cls._registry["ghosts"].add(node)
        return node

    @classmethod
    def remove_body(cls, name_or_node: BulletRigidBodyNode | str) -> None:
        """Remove a rigid body from the world by name or node reference."""
        world = cls._ensure_world()
        node: BulletRigidBodyNode | None = None
        if isinstance(name_or_node, str):
            node = cls._bodies.pop(name_or_node, None)
        else:
            node = name_or_node
            for key, value in list(cls._bodies.items()):
                if value == node:
                    cls._bodies.pop(key, None)
        if node is None and not isinstance(name_or_node, str):
            node = name_or_node
        if node is not None:
            cls._registry["bodies"].discard(node)
            try:
                world.removeRigidBody(node)
            except Exception:  # noqa: BLE001, S110
                pass

    @classmethod
    def remove_ghost(cls, name_or_node: BulletGhostNode | str) -> None:
        """Remove a ghost body from the world by name or node reference."""
        world = cls._ensure_world()
        node: BulletGhostNode | None = None
        if isinstance(name_or_node, str):
            node = cls._ghosts.pop(name_or_node, None)
        else:
            node = name_or_node
            for key, value in list(cls._ghosts.items()):
                if value == node:
                    cls._ghosts.pop(key, None)
        if node is None and not isinstance(name_or_node, str):
            node = name_or_node
        if node is not None:
            cls._registry["ghosts"].discard(node)
            try:
                world.removeGhost(node)
            except Exception:  # noqa: BLE001, S110
                pass

    @classmethod
    def clear_all(cls) -> dict[str, int]:
        """Remove all tracked and untracked bodies, ghosts and constraints from the world.

        Returns a dict with the number of removed objects by category. The method is
        idempotent and tolerates objects that were destroyed already.
        """
        world = cls._ensure_world()
        removed = {"bodies": 0, "ghosts": 0, "constraints": 0}

        all_bodies = set(cls._registry["bodies"]) | set(world.getRigidBodies())
        cls._registry["bodies"].clear()
        for node in all_bodies:
            try:
                world.removeRigidBody(node)
            except Exception:  # noqa: BLE001, S110
                pass
            removed["bodies"] += 1

        all_ghosts = set(cls._registry["ghosts"]) | set(world.getGhosts())
        cls._registry["ghosts"].clear()
        for node in all_ghosts:
            try:
                world.removeGhost(node)
            except Exception:  # noqa: BLE001, S110
                pass
            removed["ghosts"] += 1

        all_constraints = set(cls._registry["constraints"]) | set(
            world.getConstraints()
        )
        cls._registry["constraints"].clear()
        for node in all_constraints:
            try:
                world.removeConstraint(node)
            except Exception:  # noqa: BLE001, S110
                pass
            removed["constraints"] += 1

        cls._bodies.clear()
        cls._ghosts.clear()
        cls._constraints.clear()
        return removed

    @classmethod
    def clear_all_bodies(cls) -> None:
        """Backward-compatible alias for :meth:`clear_all`."""
        cls.clear_all()

    @classmethod
    def _detect_orphans(cls) -> int:
        world = cls._ensure_world()
        orphan_count = 0
        for node in world.getRigidBodies():
            if node not in cls._registry["bodies"]:
                orphan_count += 1
        for node in world.getGhosts():
            if node not in cls._registry["ghosts"]:
                orphan_count += 1
        for node in world.getConstraints():
            if node not in cls._registry["constraints"]:
                orphan_count += 1
        return orphan_count

    @classmethod
    def debug_dump(cls) -> dict[str, object]:
        """Return a small diagnostic snapshot of the physics world."""
        cls._ensure_world()
        return {
            "bodies": len(cls._registry["bodies"]),
            "ghosts": len(cls._registry["ghosts"]),
            "constraints": len(cls._registry["constraints"]),
            "orphan_nodes": cls._detect_orphans(),
        }

    @classmethod
    def attach_character(cls, node: BulletCharacterControllerNode) -> None:
        """Attach a Bullet character controller to the physics world."""
        world = cls._ensure_world()
        world.attachCharacter(node)

    @classmethod
    def raycast_closest(
        cls,
        from_pos: Vec3,
        to_pos: Vec3,
        mask: "BitMask32 | None" = None,
        step_physics: bool = False,
    ) -> tuple[Vec3, NodePath | None] | None:
        """Cast a ray and return the closest hit position and node, or None if unobstructed.

        By default `step_physics` is False so spatial queries never mutate simulation
        state. Set `step_physics=True` only in standalone setups where the caller has
        modified body transforms without stepping the world yet.
        """
        world = cls._ensure_world()
        if mask is None:
            mask = BitMask32.all_on()
        if step_physics:
            try:
                world.doPhysics(1e-6)
            except Exception:  # noqa: BLE001, S110
                pass
        result = world.rayTestClosest(from_pos, to_pos, mask)
        if result is None or not result.hasHit():
            return None

        hit_pos = Vec3(result.getHitPos())
        hit_node = result.getNode()
        hit_np = NodePath(hit_node) if hit_node is not None else None
        return hit_pos, hit_np

    @classmethod
    def sweep_sphere_closest(
        cls,
        from_pos: Vec3,
        to_pos: Vec3,
        radius: float,
        mask: "BitMask32 | None" = None,
    ) -> tuple[float, Vec3, Vec3] | None:
        """Sweep a sphere from `from_pos` to `to_pos` and return the first impact.

        Returns ``(fraction, hit_pos, hit_normal)`` where ``fraction`` in [0, 1] is the
        portion of the path travelled before touching geometry (the sphere centre is
        ``from_pos + (to_pos - from_pos) * fraction`` at contact), or None when the
        whole path is clear. A ``fraction`` of ~0 means the sphere already overlaps
        geometry at its starting point. Never advances the simulation.
        """
        world = cls._ensure_world()
        if mask is None:
            mask = BitMask32.all_on()
        shape = BulletSphereShape(max(float(radius), 1e-4))
        result = world.sweepTestClosest(
            shape,
            TransformState.makePos(from_pos),
            TransformState.makePos(to_pos),
            mask,
            0.0,
        )
        if result is None or not result.hasHit():
            return None
        return (
            float(result.getHitFraction()),
            Vec3(result.getHitPos()),
            Vec3(result.getHitNormal()),
        )

    @classmethod
    def remove_character(cls, node: BulletCharacterControllerNode) -> None:
        """Remove a Bullet character controller from the physics world."""
        world = cls._ensure_world()
        world.removeCharacter(node)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Physics diagnostics")
    parser.add_argument(
        "--dump", action="store_true", help="Print a JSON diagnostic snapshot and exit."
    )
    args = parser.parse_args()

    if args.dump:
        print(json.dumps(Physics.debug_dump(), indent=2, default=str))
