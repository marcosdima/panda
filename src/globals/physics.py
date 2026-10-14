from panda3d.bullet import (
    BulletWorld,
    BulletRigidBodyNode,
    BulletGhostNode,
    BulletDebugNode,
    BulletCharacterControllerNode,
)
from panda3d.core import Vec3

from .__global import Global
from .clock import GlobalClock


class Physics(Global):
    """A singleton class to manage the Bullet Physics world."""

    _world: BulletWorld | None = None
    _bodies: dict[str, BulletRigidBodyNode] = {}
    _ghosts: dict[str, BulletGhostNode] = {}

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
            Physics._world.setDebugNode(debug_np.node())
        except Exception:
            pass

    def _update_world(self, task):
        dt = GlobalClock.get_dt()
        if Physics._world is not None:
            Physics._world.doPhysics(dt)
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
        return node

    @classmethod
    def create_ghost(cls, name: str) -> BulletGhostNode:
        """Create a ghost body, add it to the world, and return it."""
        world = cls._ensure_world()
        node = BulletGhostNode(name)
        world.attachGhost(node)
        cls._ghosts[name] = node
        return node

    @classmethod
    def remove_body(cls, name_or_node: BulletRigidBodyNode | str) -> None:
        """Remove a rigid body from the world by name or node reference."""
        world = cls._ensure_world()
        if isinstance(name_or_node, str):
            if name_or_node in cls._bodies:
                world.removeRigidBody(cls._bodies[name_or_node])
                del cls._bodies[name_or_node]
        else:
            world.removeRigidBody(name_or_node)
            for k, v in list(cls._bodies.items()):
                if v == name_or_node:
                    del cls._bodies[k]

    @classmethod
    def remove_ghost(cls, name_or_node: BulletGhostNode | str) -> None:
        """Remove a ghost body from the world by name or node reference."""
        world = cls._ensure_world()
        if isinstance(name_or_node, str):
            if name_or_node in cls._ghosts:
                world.removeGhost(cls._ghosts[name_or_node])
                del cls._ghosts[name_or_node]
        else:
            world.removeGhost(name_or_node)
            for k, v in list(cls._ghosts.items()):
                if v == name_or_node:
                    del cls._ghosts[k]

    @classmethod
    def attach_character(cls, node: BulletCharacterControllerNode) -> None:
        """Attach a Bullet character controller to the physics world."""
        world = cls._ensure_world()
        world.attachCharacter(node)

    @classmethod
    def remove_character(cls, node: BulletCharacterControllerNode) -> None:
        """Remove a Bullet character controller from the physics world."""
        world = cls._ensure_world()
        world.removeCharacter(node)

