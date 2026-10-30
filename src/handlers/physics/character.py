from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

from panda3d.bullet import (
    BulletCapsuleShape,
    BulletCharacterControllerNode,
)
from panda3d.core import NodePath, Vec3

from src.globals.physics import Physics
from src.handlers.base import Handler
from src.handlers.capabilities import Mover
from src.handlers.input.action_map import JUMP, SPRINT
from src.handlers.input.base import InputHandler
from src.utils.handler_phase import HandlerPhase
from src.utils.math import clamp, normalize_angle

from .groups import CameraCollision, CollisionGroup

if TYPE_CHECKING:
    from src.entities.entity import Entity


class CharacterOrientationMode(str, Enum):
    phase = HandlerPhase.PHYSICS
    """Visual rotation mode for the character controller.

    - MOVE_DIRECTION: Character rotates to face the direction of movement (Adventure / RPG style).
    - CAMERA_LOOK: Character rotates to face the horizontal look direction of the camera (Shooter / Strafe style).
    - NONE: Character visual node does not rotate automatically.
    """

    MOVE_DIRECTION = "move_direction"
    CAMERA_LOOK = "camera_look"
    NONE = "none"


class _CharacterControllerNode(BulletCharacterControllerNode):
    phase = HandlerPhase.PHYSICS
    """BulletCharacterControllerNode subclass providing jump() as an alias for doJump()."""

    def jump(self) -> None:
        """Alias for doJump() to satisfy standard controller node interfaces."""
        self.doJump()


class CharacterControllerHandler(Handler):
    phase = HandlerPhase.PHYSICS
    provides = (Mover,)
    """Modular physics handler managing a Bullet Character Controller for responsive 3D movement."""

    def __init__(
        self,
        radius: float = 0.5,
        height: float = 1.0,
        step_height: float = 0.4,
        walk_speed: float = 5.0,
        sprint_speed: float = 10.0,
        jump_speed: float = 7.0,
        gravity: float = 14.0,
        visual_node: NodePath | None = None,
        turn_speed: float = 12.0,
        camera_handler: Any = None,
        acceleration: float = 0.0,
        deceleration: float = 0.0,
        collision_group: CollisionGroup = CollisionGroup.DEFAULT,
        orientation_mode: CharacterOrientationMode
        | str = CharacterOrientationMode.MOVE_DIRECTION,
        body_follows_camera_yaw: bool | None = None,
    ) -> None:
        super().__init__()
        self.radius: float = radius
        self.height: float = height
        self.step_height: float = step_height
        self.walk_speed: float = walk_speed
        self.sprint_speed: float = sprint_speed
        self._jump_speed: float = float(jump_speed)
        self._gravity: float = float(gravity)
        self._visual_node: NodePath | None = visual_node
        self.turn_speed: float = turn_speed
        self.camera_handler: Any = camera_handler
        self.acceleration: float = float(acceleration)
        self.deceleration: float = float(deceleration)
        self.collision_group: CollisionGroup = collision_group

        if body_follows_camera_yaw is not None:
            self.orientation_mode: CharacterOrientationMode = (
                CharacterOrientationMode.CAMERA_LOOK
                if body_follows_camera_yaw
                else CharacterOrientationMode.MOVE_DIRECTION
            )
        elif isinstance(orientation_mode, str):
            self.orientation_mode = CharacterOrientationMode(orientation_mode)
        else:
            self.orientation_mode = orientation_mode

        # Uses BulletCapsuleShape(radius, height, 2) (Z-up axis)
        self.shape: BulletCapsuleShape = BulletCapsuleShape(self.radius, self.height, 2)
        self.controller_node: BulletCharacterControllerNode | None = None
        self.controller_np: NodePath | None = None
        self._linear_velocity: Vec3 = Vec3(0.0, 0.0, 0.0)
        self._is_attached_to_world: bool = False

    @property
    def body_follows_camera_yaw(self) -> bool:
        """Backwards compatibility alias: True if orientation_mode is CAMERA_LOOK."""
        return self.orientation_mode == CharacterOrientationMode.CAMERA_LOOK

    @body_follows_camera_yaw.setter
    def body_follows_camera_yaw(self, value: bool) -> None:
        self.orientation_mode = (
            CharacterOrientationMode.CAMERA_LOOK
            if value
            else CharacterOrientationMode.MOVE_DIRECTION
        )

    @property
    def jump_speed(self) -> float:
        """Return the character jump speed."""
        return self._jump_speed

    @jump_speed.setter
    def jump_speed(self, value: float) -> None:
        self._jump_speed = float(value)
        if self.controller_node is not None:
            self.controller_node.setJumpSpeed(self._jump_speed)

    @property
    def gravity(self) -> float:
        """Return the character controller downward gravity."""
        return self._gravity

    @gravity.setter
    def gravity(self, value: float) -> None:
        self._gravity = float(value)
        if self.controller_node is not None:
            self.controller_node.setGravity(self._gravity)

    @property
    def visual_node(self) -> NodePath | None:
        """Return the visual NodePath being rotated, or None."""
        return self._visual_node

    @visual_node.setter
    def visual_node(self, node: NodePath | None) -> None:
        """Set the visual NodePath to rotate towards movement direction."""
        self._visual_node = node

    def _attach_to_world(self) -> None:
        """Attach the controller node to the active Bullet physics world."""
        if not self._is_attached_to_world and self.controller_node is not None:
            Physics.get_world().attachCharacter(self.controller_node)
            self._is_attached_to_world = True

    def _detach_from_world(self) -> None:
        """Remove the controller node cleanly from the active Bullet physics world."""
        if self._is_attached_to_world and self.controller_node is not None:
            Physics.get_world().removeCharacter(self.controller_node)
            self._is_attached_to_world = False

    def on_attach(self, entity: Entity) -> None:
        """Attach controller node to entity.node and register with BulletWorld."""
        super().on_attach(entity)
        if self.controller_node is None:
            self.controller_node = _CharacterControllerNode(
                self.shape, self.step_height, entity.name
            )
            self.controller_node.setGravity(self.gravity)
            self.controller_node.setJumpSpeed(self.jump_speed)
            # Camera queries must never hit the character's own capsule.
            self.controller_node.setIntoCollideMask(CameraCollision.non_blocking_mask())
        else:
            self.controller_node.setName(entity.name)
        self.controller_node.setPythonTag("entity", entity)

        if self.controller_np is None or self.controller_np.isEmpty():
            self.controller_np = entity.node.attachNewNode(self.controller_node)

        self._attach_to_world()

    def on_start(self) -> None:
        """Called when active scene or entity starts."""
        super().on_start()
        if self.entity is not None and (
            self.controller_np is None or self.controller_np.isEmpty()
        ):
            if self.controller_node is not None:
                self.controller_np = self.entity.node.attachNewNode(
                    self.controller_node
                )
        self._attach_to_world()

    def on_update(self, dt: float) -> None:
        """Per-frame update hook consuming InputHandler and updating linear movement & jump."""
        super().on_update(dt)
        if self.controller_node is None:
            return

        # Check for attached InputHandler on self.entity
        input_handler: InputHandler | None = None
        if self.entity is not None:
            input_handler = self.entity.get_handler(InputHandler)

        # Check for camera handler
        camera_handler = self.camera_handler
        if camera_handler is None and self.entity is not None:
            from src.handlers.camera.first_person import FirstPersonCameraHandler
            from src.handlers.camera.third_person import ThirdPersonCameraHandler

            camera_handler = self.entity.get_handler(
                ThirdPersonCameraHandler
            ) or self.entity.get_handler(FirstPersonCameraHandler)

        is_local = True
        # Read movement vector, scale by current speed (walk vs sprint)
        if input_handler is not None:
            is_sprinting = input_handler.is_action_down(SPRINT)
            current_speed = self.sprint_speed if is_sprinting else self.walk_speed
            move_vec = input_handler.move_vector

            if camera_handler is not None and hasattr(
                camera_handler, "get_forward_vector"
            ):
                # Horizontal projection of camera's forward vector
                cam_fwd = camera_handler.get_forward_vector()
                fwd_h = Vec3(cam_fwd.x, cam_fwd.y, 0.0)
                if fwd_h.length_squared() > 1e-6:
                    fwd_h.normalize()
                else:
                    fwd_h = Vec3(0.0, 1.0, 0.0)

                # Horizontal projection of camera's right vector
                right_h = fwd_h.cross(Vec3(0.0, 0.0, 1.0))
                if right_h.length_squared() > 1e-6:
                    right_h.normalize()
                else:
                    right_h = Vec3(1.0, 0.0, 0.0)

                # Transform (x, y) move vector:
                # Forward (W, y > 0) moves along camera's horizontal forward
                # Right (D, x > 0) moves along camera's horizontal right
                world_dir = fwd_h * move_vec.y + right_h * move_vec.x
                if world_dir.length_squared() > 1.0:
                    world_dir.normalize()

                target_velocity = world_dir * current_speed
                is_local = False
            else:
                target_velocity = Vec3(
                    move_vec.x * current_speed, move_vec.y * current_speed, 0.0
                )
                is_local = True

            # If the jump action is triggered and controller_node.isOnGround(), triggers controller_node.jump()
            if (
                input_handler.is_action_pressed(JUMP)
                and self.controller_node.isOnGround()
            ):
                if hasattr(self.controller_node, "jump"):
                    self.controller_node.jump()
                else:
                    self.controller_node.doJump()
        else:
            target_velocity = Vec3(0.0, 0.0, 0.0)
            is_local = camera_handler is None or not hasattr(
                camera_handler, "get_forward_vector"
            )

        # Smoothly blend velocity using acceleration / deceleration damping
        if self.acceleration > 0.0 and self.deceleration > 0.0:
            is_braking = (
                target_velocity.length_squared() < 1e-6
                or target_velocity.length_squared()
                < self._linear_velocity.length_squared()
            )
            rate = self.deceleration if is_braking else self.acceleration
            step = clamp(dt * rate, 0.0, 1.0)
            self._linear_velocity = (
                self._linear_velocity + (target_velocity - self._linear_velocity) * step
            )
            if (
                target_velocity.length_squared() < 1e-6
                and self._linear_velocity.length_squared() < 1e-6
            ):
                self._linear_velocity = Vec3(0.0, 0.0, 0.0)
        else:
            self._linear_velocity = target_velocity

        # Apply controller_node.setLinearMovement
        self.controller_node.setLinearMovement(self._linear_velocity, is_local=is_local)

        # Rotate the character's visual node according to orientation_mode.
        if self._visual_node is not None and not self._visual_node.isEmpty():
            target_h: float | None = None
            if (
                self.orientation_mode == CharacterOrientationMode.CAMERA_LOOK
                and camera_handler is not None
                and hasattr(camera_handler, "get_forward_vector")
            ):
                # Always face the horizontal forward direction of the camera
                cam_fwd = camera_handler.get_forward_vector()
                if cam_fwd.x * cam_fwd.x + cam_fwd.y * cam_fwd.y > 1e-6:
                    target_h = -math.degrees(math.atan2(cam_fwd.x, cam_fwd.y))
            elif (
                self.orientation_mode == CharacterOrientationMode.MOVE_DIRECTION
                and self._linear_velocity.length_squared() > 1e-4
            ):
                # Face movement direction (both camera-relative players and camera-less NPCs)
                target_h = -math.degrees(
                    math.atan2(self._linear_velocity.x, self._linear_velocity.y)
                )

            if target_h is not None:
                curr_h = self._visual_node.getH()
                diff = normalize_angle(target_h - curr_h)
                step = (
                    1.0
                    if self.turn_speed <= 0.0
                    else clamp(self.turn_speed * dt, 0.0, 1.0)
                )
                self._visual_node.setH(curr_h + diff * step)

    def jump(self) -> bool:
        """Explicitly trigger jump if controller node is on ground. Returns True if jumped."""
        if self.controller_node is not None and self.controller_node.isOnGround():
            if hasattr(self.controller_node, "jump"):
                self.controller_node.jump()
            else:
                self.controller_node.doJump()
            return True
        return False

    def on_stop(self) -> None:
        """Cleanly remove character controller from BulletWorld and detach nodes upon stop."""
        super().on_stop()
        self._detach_from_world()
        if self.controller_np is not None and not self.controller_np.isEmpty():
            self.controller_np.removeNode()
            self.controller_np = None

    def on_detach(self) -> None:
        """Cleanly remove character controller from BulletWorld and detach nodes upon detach."""
        super().on_detach()
        self._detach_from_world()
        if self.controller_np is not None and not self.controller_np.isEmpty():
            self.controller_np.removeNode()
            self.controller_np = None
        self.controller_node = None

    @property
    def is_on_ground(self) -> bool:
        """Return whether controller is on ground."""
        return (
            self.controller_node.isOnGround()
            if self.controller_node is not None
            else False
        )

    @property
    def can_jump(self) -> bool:
        """Return whether controller is currently capable of jumping."""
        return (
            self.controller_node.canJump()
            if self.controller_node is not None
            else False
        )

    @property
    def linear_velocity(self) -> Vec3:
        """Return the last applied linear velocity."""
        return Vec3(self._linear_velocity)

    @property
    def is_sprinting(self) -> bool:
        """Return whether sprint action is currently active on entity's InputHandler."""
        if self.entity is not None:
            input_handler = self.entity.get_handler(InputHandler)
            if input_handler is not None:
                return input_handler.is_action_down(SPRINT)
        return False

    @property
    def current_speed(self) -> float:
        """Return current speed (sprint vs walk)."""
        return self.sprint_speed if self.is_sprinting else self.walk_speed
