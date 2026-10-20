from __future__ import annotations

from typing import TYPE_CHECKING

from panda3d.bullet import BulletRigidBodyNode, BulletShape
from panda3d.core import NodePath, TransformState, Vec3

from src.globals.physics import Physics
from src.handlers.base import Handler
from .groups import CollisionGroup

if TYPE_CHECKING:
    from src.entities.entity import Entity


class RigidBodyHandler(Handler):
    """Modular physics handler encapsulating a BulletRigidBodyNode.

    Supports static terrain (mass=0) and dynamic props (mass>0). The body
    node is parented under the entity's NodePath so transforms stay composed,
    and is tagged with its entity so trigger volumes can resolve overlaps.
    """

    def __init__(
        self,
        shape: BulletShape | None = None,
        mass: float = 0.0,
        collision_group: CollisionGroup = CollisionGroup.DEFAULT,
    ) -> None:
        super().__init__()
        self.shape: BulletShape | None = shape
        self.mass: float = mass
        self.collision_group: CollisionGroup = collision_group
        self.body_node: BulletRigidBodyNode | None = None
        self.body_np: NodePath | None = None
        self._is_attached_to_world: bool = False
        self._last_parent_net: TransformState | None = None

    @property
    def is_dynamic(self) -> bool:
        """Return True if this body has mass and is affected by forces."""
        return self.mass > 0.0

    @property
    def linear_velocity(self) -> Vec3:
        """Return the body's current linear velocity."""
        if self.body_node is None:
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(self.body_node.getLinearVelocity())

    @linear_velocity.setter
    def linear_velocity(self, velocity: Vec3) -> None:
        """Set the body's linear velocity (zero for static/kinematic moves)."""
        if self.body_node is not None:
            self.body_node.setLinearVelocity(velocity)

    def add_shape(self, shape: BulletShape) -> None:
        """Add a collision shape to the rigid body node."""
        if self.body_node is None:
            self.shape = shape
        else:
            self.body_node.addShape(shape)

    def apply_impulse(self, impulse: Vec3) -> None:
        """Apply a one-shot central impulse to a dynamic body."""
        if self.body_node is not None and self.is_dynamic:
            self.body_node.setActive(True)
            self.body_node.applyCentralImpulse(impulse)

    def apply_force(self, force: Vec3) -> None:
        """Apply a persistent central force for the next physics step (dynamic bodies only)."""
        if self.body_node is not None and self.is_dynamic:
            self.body_node.setActive(True)
            self.body_node.applyCentralForce(force)

    def _attach_to_world(self) -> None:
        """Attach the rigid body node to the active Bullet physics world."""
        if not self._is_attached_to_world and self.body_node is not None:
            Physics.get_world().attachRigidBody(self.body_node)
            self._is_attached_to_world = True

    def _detach_from_world(self) -> None:
        """Remove the rigid body node cleanly from the active Bullet physics world."""
        if self._is_attached_to_world and self.body_node is not None:
            Physics.get_world().removeRigidBody(self.body_node)
            self._is_attached_to_world = False

    def on_attach(self, entity: Entity) -> None:
        """Create the rigid body node, parent it to the entity, and join the world."""
        super().on_attach(entity)
        if self.body_node is None:
            self.body_node = BulletRigidBodyNode(entity.name)
            self.body_node.setMass(self.mass)
            if self.shape is not None:
                self.body_node.addShape(self.shape)
        else:
            self.body_node.setName(entity.name)
        self.body_node.setPythonTag("entity", entity)

        if self.body_np is None or self.body_np.isEmpty():
            self.body_np = entity.node.attachNewNode(self.body_node)
        if self.body_np is not None and not self.body_np.isEmpty():
            self._last_parent_net = self.body_np.getParent().getNetTransform()

        self._attach_to_world()

    def on_start(self) -> None:
        """Called when active scene or entity starts."""
        super().on_start()
        if self.entity is not None and (self.body_np is None or self.body_np.isEmpty()):
            if self.body_node is not None:
                self.body_np = self.entity.node.attachNewNode(self.body_node)
                self._last_parent_net = self.body_np.getParent().getNetTransform()
        self._attach_to_world()

    def on_update(self, dt: float) -> None:
        """Propagate moves of `entity.node` into the Bullet simulation.

        Panda3D only pushes a node's net transform into Bullet when its own
        transform is flagged as authoritative; moving an ancestor (like
        `entity.node`) never flags it. This method detects parent transform
        changes since the last frame and flags the body exactly then, so the
        next `doPhysics` call adopts the new entity transform. Untouched
        bodies stay under Bullet's control (gravity, impulses, write-backs).
        """
        super().on_update(dt)
        if self.body_node is None or self.body_np is None or self.body_np.isEmpty():
            return
        parent_net = self.body_np.getParent().getNetTransform()
        if parent_net != self._last_parent_net:
            self.body_node.setTransformDirty()
            self._last_parent_net = parent_net

    def on_stop(self) -> None:
        """Detach the body from the world and remove its NodePath."""
        super().on_stop()
        self._detach_from_world()
        if self.body_np is not None and not self.body_np.isEmpty():
            self.body_np.removeNode()
        self.body_np = None
        self._last_parent_net = None

    def on_detach(self) -> None:
        """Fully release the body node when the handler is removed from its entity."""
        self._detach_from_world()
        if self.body_np is not None and not self.body_np.isEmpty():
            self.body_np.removeNode()
        self.body_np = None
        self.body_node = None
        self._last_parent_net = None
        super().on_detach()
