from __future__ import annotations

import builtins
import logging
import math
from typing import TYPE_CHECKING, Any

from panda3d.core import Camera as CameraNode
from panda3d.core import Lens, MouseButton, NodePath, Vec3, WindowProperties

from src.handlers.base import Handler
from src.handlers.physics.character import CharacterControllerHandler
from src.handlers.physics.groups import CameraCollision
from src.utils.handler_phase import HandlerPhase
from src.utils.math import clamp, normalize_angle
from src.utils.position import world_position

if TYPE_CHECKING:
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)

_MIN_COLLISION_RADIUS: float = 0.02
_MIN_NEAR_PLANE: float = 0.005
_CAPSULE_RADIUS_FRACTION: float = 0.9
_MAX_RADIUS_RETRIES: int = 6
_START_PENETRATION_EPS: float = 1e-3
_DEFAULT_EXTENT_FACTOR: float = 1.8
_NEAR_SAFETY: float = 1.1
_SMOOTH_SNAP_DISTANCE: float = 5.0


class FirstPersonCameraHandler(Handler):
    phase = HandlerPhase.POST
    """First-person camera handler that locks the camera to the character's eye position."""

    def __init__(
        self,
        eye_offset: Vec3 = Vec3(0.0, 0.0, 1.5),
        yaw: float = 0.0,
        pitch: float = 0.0,
        min_pitch: float = -89.0,
        max_pitch: float = 89.0,
        mouse_sensitivity: float = 0.2,
        camera: NodePath | None = None,
        invert_yaw: bool = False,
        invert_pitch: bool = False,
        collision_enabled: bool = True,
        collision_margin: float = 0.2,
        hide_self: bool = True,
        near_plane: float = 0.1,
        far_plane: float = 1000.0,
        smooth_factor: float = 0.0,
        pivot_offset: Vec3 | None = None,
    ) -> None:
        """Create a FirstPersonCameraHandler.

        Parameters
        ----------
        collision_margin: float
            Radius (world units) of the sphere swept from the body pivot to the eye.
            It is capped to 90% of the character capsule radius so it always fits
            inside the body, and the near plane is automatically reduced to fit
            inside it, so the view can never see through geometry the eye touches.
        near_plane: float
            Desired near plane distance, applied to the real camera lens.
        far_plane: float
            Far plane distance, applied to the real camera lens.
        smooth_factor: float
            Optional position smoothing in [0, 1] applied to the eye before
            collision resolution (frame-rate independent, relative to 60 FPS).
            ``0`` (default) locks the eye rigidly to the character.
        pivot_offset: Vec3 | None
            Offset from the body position where the collision sweep starts. It must be
            inside the character. Defaults to the capsule centre when a
            ``CharacterControllerHandler`` is attached, otherwise half of ``eye_offset``.
        """
        super().__init__()
        self.eye_offset: Vec3 = Vec3(eye_offset)

        self.min_pitch: float = float(min_pitch)
        self.max_pitch: float = float(max_pitch)
        self._pitch: float = clamp(float(pitch), self.min_pitch, self.max_pitch)
        self._yaw: float = normalize_angle(float(yaw), 0.0)

        self.mouse_sensitivity: float = float(mouse_sensitivity)
        self.invert_yaw: bool = invert_yaw
        self.invert_pitch: bool = invert_pitch
        self.collision_enabled: bool = collision_enabled
        self.collision_margin: float = float(max(collision_margin, 0.0))
        self.hide_self: bool = hide_self
        self.near_plane: float = float(max(near_plane, _MIN_NEAR_PLANE))
        self.far_plane: float = float(far_plane)
        self.pivot_offset: Vec3 | None = (
            Vec3(pivot_offset) if pivot_offset is not None else None
        )

        self.smooth_factor: float = clamp(smooth_factor, 0.0, 1.0)
        self._smoothed_eye: Vec3 | None = None
        self._effective_radius: float | None = None
        self._saved_near_far: tuple[float, float] | None = None
        self._hidden_nodes: list[NodePath] = []

        self._camera_node: NodePath | None = camera
        self._saved_cam_pos: Vec3 | None = None
        self._saved_cam_hpr: Vec3 | None = None

        self._last_mouse_pos: tuple[float, float] | None = None
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        self.is_pointer_captured: bool = win is not None
        self._captured_before_pause: bool = self.is_pointer_captured
        self._skip_first_mouse_delta: bool = True
        self._btn_mouse3 = MouseButton.three()

    @property
    def pitch(self) -> float:
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        self._pitch = clamp(float(value), self.min_pitch, self.max_pitch)

    @property
    def yaw(self) -> float:
        return self._yaw

    @yaw.setter
    def yaw(self, value: float) -> None:
        self._yaw = normalize_angle(float(value), 0.0)

    @property
    def camera(self) -> NodePath:
        return self.get_camera_node()

    @camera.setter
    def camera(self, cam: NodePath | None) -> None:
        self._camera_node = cam

    def get_camera_node(self) -> NodePath:
        if self._camera_node is not None and not self._camera_node.isEmpty():
            return self._camera_node

        try:
            from src.globals.camera import Camera

            cam = Camera.get_camera()
            if cam is not None and not cam.isEmpty():
                self._camera_node = cam
                return cam
        except Exception:
            logger.debug(
                "Global Camera unavailable; falling back to builtins.base.camera.",
                exc_info=True,
            )

        base = getattr(builtins, "base", None)
        cam = getattr(base, "camera", None) if base else None
        if cam is not None and hasattr(cam, "isEmpty") and not cam.isEmpty():
            self._camera_node = cam
            return cam

        self._camera_node = NodePath("headless_fp_camera")
        return self._camera_node

    def set_pointer_captured(self, captured: bool) -> None:
        self.is_pointer_captured = captured
        self._skip_first_mouse_delta = True
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        if win is not None and hasattr(win, "requestProperties"):
            props = WindowProperties()
            if captured:
                props.setCursorHidden(True)
                props.setMouseMode(WindowProperties.M_relative)
                cx = win.getXSize() // 2
                cy = win.getYSize() // 2
                if hasattr(win, "movePointer"):
                    win.movePointer(0, cx, cy)
            else:
                props.setCursorHidden(False)
                props.setMouseMode(WindowProperties.M_absolute)
            win.requestProperties(props)

    def _on_toggle_cursor(self) -> None:
        base = getattr(builtins, "base", None)
        if getattr(base, "paused", False):
            return
        self.set_pointer_captured(not self.is_pointer_captured)

    def _on_unlock_cursor(self) -> None:
        if self.is_pointer_captured:
            self.set_pointer_captured(False)

    def _on_lock_cursor(self) -> None:
        base = getattr(builtins, "base", None)
        if getattr(base, "paused", False):
            return
        if not self.is_pointer_captured:
            self.set_pointer_captured(True)

    def _on_game_paused(self, paused: bool) -> None:
        if paused:
            self._captured_before_pause = self.is_pointer_captured
            if self.is_pointer_captured:
                self.set_pointer_captured(False)
        else:
            base = getattr(builtins, "base", None)
            win = getattr(base, "win", None) if base else None
            if win is not None and self._captured_before_pause:
                self.set_pointer_captured(True)

    def _get_mouse_watcher(self):
        base = getattr(builtins, "base", None)
        if base is None:
            return None
        watcher = getattr(base, "mouseWatcherNode", None)
        if watcher is not None and hasattr(watcher, "is_button_down"):
            return watcher
        mw_np = getattr(base, "mouseWatcher", None)
        if mw_np is not None and hasattr(mw_np, "node"):
            node = mw_np.node()
            if hasattr(node, "is_button_down"):
                return node
        return None

    def handle_mouse_delta(self, dx: float, dy: float) -> None:
        yaw_delta = dx * self.mouse_sensitivity
        pitch_delta = dy * self.mouse_sensitivity

        if not self.invert_yaw:
            self.yaw = normalize_angle(self.yaw - yaw_delta, 0.0)
        else:
            self.yaw = normalize_angle(self.yaw + yaw_delta, 0.0)

        if not self.invert_pitch:
            self.pitch = clamp(self.pitch - pitch_delta, self.min_pitch, self.max_pitch)
        else:
            self.pitch = clamp(self.pitch + pitch_delta, self.min_pitch, self.max_pitch)

    def get_body_pos(self) -> Vec3:
        """Return the character's body position without the eye offset."""
        if self.entity is None:
            return Vec3(0.0, 0.0, 0.0)
        return world_position(self.entity)

    def get_target_pos(self) -> Vec3:
        """Return the eye position (body position + eye_offset)."""
        return self.get_body_pos() + self.eye_offset

    def get_forward_vector(self) -> Vec3:
        pitch_rad = math.radians(self.pitch)
        yaw_rad = math.radians(self.yaw)
        fx = -math.cos(pitch_rad) * math.sin(yaw_rad)
        fy = math.cos(pitch_rad) * math.cos(yaw_rad)
        fz = math.sin(pitch_rad)
        return Vec3(fx, fy, fz)

    def get_body_yaw(self) -> float:
        """Return the yaw angle the character body should face.

        In Panda3D, heading 0 faces +Y, -90 faces +X (right), 90 faces -X (left).
        Returns the body yaw normalized to [0, 360).
        """
        fwd = self.get_forward_vector()
        return normalize_angle(-math.degrees(math.atan2(fwd.x, fwd.y)), 0.0)

    def _get_controller(self) -> CharacterControllerHandler | None:
        """Return the entity's character controller handler, if any."""
        if self.entity is None:
            return None
        return self.entity.get_handler(CharacterControllerHandler)

    def get_pivot_pos(self) -> Vec3:
        """Return the world-space point from which the eye sphere is swept.

        The pivot must always be a free position that is *inside* the character
        (its capsule centre), so the sweep towards the eye can only be blocked
        by world geometry between the body and the head, never by the body itself.
        """
        body = self.get_body_pos()
        if self.pivot_offset is not None:
            return body + self.pivot_offset
        if self._get_controller() is not None:
            return body
        return body + self.eye_offset * 0.5

    def get_eye_pos(self) -> Vec3:
        """Return the collision-safe eye position for the current frame (no smoothing)."""
        return self._resolve_collision(self.get_target_pos())

    def _get_physics(self) -> Any:
        """Retrieve physics world from Service Locator, falling back to global Physics."""
        try:
            from src.globals.physics import Physics
            from src.services import services

            return services.get("physics", default=Physics)
        except ImportError:
            from src.globals.physics import Physics

            return Physics

    def _get_collision_radius(self) -> float:
        """Radius of the sphere that represents the camera's near-plane volume.

        ``collision_margin`` is capped to a fraction of the controller's capsule
        radius so the sweep sphere always fits inside the body at its pivot.
        """
        radius = max(self.collision_margin, _MIN_COLLISION_RADIUS)
        ctrl = self._get_controller()
        if ctrl is not None:
            radius = min(
                radius,
                max(ctrl.radius * _CAPSULE_RADIUS_FRACTION, _MIN_COLLISION_RADIUS),
            )
        return radius

    def _resolve_collision(self, eye_pos: Vec3) -> Vec3:
        """Return the closest valid eye position along the pivot -> `eye_pos` path.

        A single sphere sweep from the pivot (inside the body) to the desired eye
        replaces ad-hoc ray checks: the sphere has the volume of the camera's near
        plane, so walls, corners, floors and ceilings are all handled uniformly and
        the returned position is guaranteed to be free of world geometry. The
        radius actually used is stored so the near plane can be fitted inside it
        (see ``_get_effective_near``).
        """
        if not self.collision_enabled:
            self._effective_radius = None
            return Vec3(eye_pos)

        physics = self._get_physics()
        pivot = self.get_pivot_pos()
        path = eye_pos - pivot
        length = path.length()
        radius = self._get_collision_radius()
        if length < 1e-6:
            self._effective_radius = radius
            return Vec3(eye_pos)

        for _ in range(_MAX_RADIUS_RETRIES):
            hit = physics.sweep_sphere_closest(
                pivot, eye_pos, radius, CameraCollision.QUERY_MASK
            )
            if hit is None:
                self._effective_radius = radius
                return Vec3(eye_pos)
            fraction = hit[0]
            if fraction * length > _START_PENETRATION_EPS:
                self._effective_radius = radius
                return pivot + path * fraction
            # The sphere already overlaps geometry at the pivot: shrink and retry.
            radius *= 0.5

        # Squeezed into geometry even with a tiny sphere: stay at the pivot (inside the body).
        self._effective_radius = radius
        return Vec3(pivot)

    def _get_lens(self) -> Lens | None:
        """Return the real lens used to render the view, or None when headless.

        ``base.camera`` is only a transform node; the lens lives on the ``Camera``
        node underneath it (``base.cam``) and is shared with ``base.camLens``.
        """
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            node = cam.node()
            if isinstance(node, CameraNode):
                return node.getLens()
            child = cam.find("**/+Camera")
            if not child.isEmpty():
                return child.node().getLens()

        base = getattr(builtins, "base", None)
        return getattr(base, "camLens", None) if base is not None else None

    @staticmethod
    def _get_frustum_extent_factor(lens: Lens | None) -> float:
        """Return the distance from the eye to the near-plane corners divided by ``near``."""
        if lens is None:
            return _DEFAULT_EXTENT_FACTOR
        fov = lens.getFov()
        half_h = math.radians(clamp(fov[0], 1.0, 170.0) / 2.0)
        half_v = math.radians(clamp(fov[1], 1.0, 170.0) / 2.0)
        return math.sqrt(1.0 + math.tan(half_h) ** 2 + math.tan(half_v) ** 2)

    def _get_effective_near(self, lens: Lens | None) -> float:
        """Near plane distance, reduced when needed so it fits inside the collision sphere.

        Every point of the near-plane rectangle is at most ``near * extent_factor``
        from the eye. Keeping that below the sphere radius guarantees the visible
        frustum never starts behind a surface the sphere has been stopped by.
        """
        near = self.near_plane
        if self.collision_enabled and self._effective_radius is not None:
            factor = self._get_frustum_extent_factor(lens) * _NEAR_SAFETY
            near = min(near, self._effective_radius / factor)
        return max(near, _MIN_NEAR_PLANE)

    def _apply_lens(self) -> None:
        """Push the effective near/far planes to the real lens, remembering the originals."""
        lens = self._get_lens()
        if lens is None:
            return
        if self._saved_near_far is None:
            self._saved_near_far = (lens.getNear(), lens.getFar())
        lens.setNearFar(self._get_effective_near(lens), self.far_plane)

    def _restore_lens(self) -> None:
        """Restore the near/far planes the lens had before this handler touched it."""
        if self._saved_near_far is None:
            return
        lens = self._get_lens()
        if lens is not None:
            lens.setNearFar(*self._saved_near_far)
        self._saved_near_far = None

    def _smooth_eye(self, desired: Vec3, dt: float) -> Vec3:
        """Optionally smooth the unresolved eye position (frame-rate independent).

        Smoothing happens *before* collision resolution so the resolved position
        is always validated against the geometry, whatever the interpolation does.
        """
        if self.smooth_factor <= 0.0 or self._smoothed_eye is None:
            self._smoothed_eye = Vec3(desired)
            return Vec3(desired)
        if (desired - self._smoothed_eye).length() > _SMOOTH_SNAP_DISTANCE:
            self._smoothed_eye = Vec3(desired)
            return Vec3(desired)
        keep = (1.0 - clamp(self.smooth_factor, 0.0, 1.0)) ** (max(dt, 0.0) * 60.0)
        self._smoothed_eye = desired + (self._smoothed_eye - desired) * keep
        return Vec3(self._smoothed_eye)

    def apply_view(self, dt: float = 1.0 / 60.0) -> None:
        """Apply the camera transform and lens planes for this frame.

        - Resolves the eye position through the sphere-sweep collision pass.
        - Orients the camera directly from yaw/pitch (no look smoothing).
        - Fits the near plane inside the collision sphere on the real lens.
        - Keeps the camera parented to the render scene (headless safe).
        """
        cam = self.get_camera_node()
        if cam is None or cam.isEmpty():
            return

        base = getattr(builtins, "base", None)
        render = getattr(base, "render", None) if base else None
        if render is not None and cam.getParent() != render:
            cam.reparentTo(render)

        eye = self._resolve_collision(self._smooth_eye(self.get_target_pos(), dt))
        cam.setPos(eye)
        cam.lookAt(eye + self.get_forward_vector())
        self._apply_lens()

    def _apply_camera_transform(self, dt: float = 1.0 / 60.0) -> None:
        """Apply camera transform and lens planes using final frame positions."""
        cam = self.get_camera_node()
        if cam is None or cam.isEmpty():
            return

        base = getattr(builtins, "base", None)
        render = getattr(base, "render", None) if base else None
        if render is not None and cam.getParent() != render:
            cam.reparentTo(render)

        eye = self._resolve_collision(self._smooth_eye(self.get_target_pos(), dt))
        cam.setPos(eye)
        cam.lookAt(eye + self.get_forward_vector())
        self._apply_lens()

    def _hide_entity_model(self) -> None:
        if not self.hide_self or self.entity is None:
            return
        node = self.entity.node
        if node is None or node.isEmpty():
            return
        if node.isHidden():
            return
        node.hide()
        self._hidden_nodes.append(node)

    def _show_entity_model(self) -> None:
        for np in self._hidden_nodes:
            if np is not None and not np.isEmpty() and np.isHidden():
                np.show()
        self._hidden_nodes.clear()

    def on_attach(self, entity: Entity) -> None:
        super().on_attach(entity)
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            if self._saved_cam_pos is None:
                self._saved_cam_pos = Vec3(cam.getPos())
                self._saved_cam_hpr = Vec3(cam.getHpr())

    def on_start(self) -> None:
        super().on_start()
        self._hide_entity_model()
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            if self._saved_cam_pos is None:
                self._saved_cam_pos = Vec3(cam.getPos())
                self._saved_cam_hpr = Vec3(cam.getHpr())

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "accept"):
            base.accept("tab", self._on_toggle_cursor)
            base.accept("mouse1", self._on_lock_cursor)

        from src.utils import bus

        bus.subscribe("game_paused", self._on_game_paused)

        win = getattr(base, "win", None) if base else None
        if win is not None and not getattr(base, "paused", False):
            self.set_pointer_captured(True)

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        if (
            self.entity is None
            or self.entity.node is None
            or self.entity.node.isEmpty()
        ):
            return

        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None

        if win is not None and hasattr(win, "getPointer"):
            mouse3_down = False
            watcher = self._get_mouse_watcher()
            if watcher is not None and hasattr(watcher, "is_button_down"):
                mouse3_down = watcher.is_button_down(self._btn_mouse3)

            is_looking = self.is_pointer_captured or mouse3_down

            if is_looking:
                pointer = win.getPointer(0)
                px = pointer.getX()
                py = pointer.getY()

                if self.is_pointer_captured:
                    cx = win.getXSize() // 2
                    cy = win.getYSize() // 2
                    dx = float(px - cx)
                    dy = float(py - cy)
                    if hasattr(win, "movePointer"):
                        win.movePointer(0, cx, cy)
                    if self._skip_first_mouse_delta:
                        self._skip_first_mouse_delta = False
                        dx = 0.0
                        dy = 0.0
                else:
                    if self._last_mouse_pos is not None:
                        dx = float(px - self._last_mouse_pos[0])
                        dy = float(py - self._last_mouse_pos[1])
                    else:
                        dx = 0.0
                        dy = 0.0
                    self._last_mouse_pos = (px, py)

                if dx != 0.0 or dy != 0.0:
                    self.handle_mouse_delta(dx, dy)
            else:
                self._last_mouse_pos = None

    def on_post_update(self, dt: float) -> None:
        super().on_post_update(dt)
        if (
            self.entity is None
            or self.entity.node is None
            or self.entity.node.isEmpty()
        ):
            return
        self._apply_camera_transform(dt)

    def on_stop(self) -> None:
        super().on_stop()
        from src.utils import bus

        bus.unsubscribe("game_paused", self._on_game_paused)
        self._show_entity_model()
        self._restore_lens()
        self._smoothed_eye = None
        self._effective_radius = None
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            base.ignore("tab")
            base.ignore("mouse1")

        win = getattr(base, "win", None) if base else None
        if win is not None and hasattr(win, "requestProperties"):
            props = WindowProperties()
            props.setCursorHidden(False)
            props.setMouseMode(WindowProperties.M_absolute)
            win.requestProperties(props)
        self.is_pointer_captured = False

        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            if self._saved_cam_pos is not None:
                cam.setPos(self._saved_cam_pos)
            if self._saved_cam_hpr is not None:
                cam.setHpr(self._saved_cam_hpr)

        self._last_mouse_pos = None

    def on_detach(self) -> None:
        super().on_detach()
        self._show_entity_model()
        self.on_stop()
        self._camera_node = None
        self._saved_cam_pos = None
        self._saved_cam_hpr = None
        self._hidden_nodes.clear()
