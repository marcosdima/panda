from __future__ import annotations

import builtins
import math
from typing import TYPE_CHECKING
from panda3d.core import MouseButton, NodePath, Vec3, WindowProperties

from src.handlers.base import Handler

if TYPE_CHECKING:
    from src.entities.entity import Entity


class ThirdPersonCameraHandler(Handler):
    """Third-person orbit camera handler with spherical coordinates, mouse orbit, and position smoothing."""

    def __init__(
        self,
        distance: float = 8.0,
        min_distance: float = 2.0,
        max_distance: float = 25.0,
        target_offset: Vec3 = Vec3(0.0, 0.0, 1.5),
        pitch: float = -15.0,
        min_pitch: float = -75.0,
        max_pitch: float = 45.0,
        yaw: float = 0.0,
        smooth_speed: float = 10.0,
        mouse_sensitivity: float = 0.2,
        zoom_step: float = 1.0,
        camera: NodePath | None = None,
        invert_yaw: bool = False,
        invert_pitch: bool = False,
    ) -> None:
        super().__init__()
        self.min_distance: float = float(min_distance)
        self.max_distance: float = float(max_distance)
        self._distance: float = max(self.min_distance, min(self.max_distance, float(distance)))

        self.target_offset: Vec3 = Vec3(target_offset)

        self.min_pitch: float = float(min_pitch)
        self.max_pitch: float = float(max_pitch)
        self._pitch: float = max(self.min_pitch, min(self.max_pitch, float(pitch)))

        self._yaw: float = float(yaw) % 360.0

        self.smooth_speed: float = float(smooth_speed)
        self.mouse_sensitivity: float = float(mouse_sensitivity)
        self.zoom_step: float = float(zoom_step)
        self.invert_yaw: bool = invert_yaw
        self.invert_pitch: bool = invert_pitch

        self._camera_node: NodePath | None = camera
        self._current_cam_pos: Vec3 | None = None
        self._saved_cam_pos: Vec3 | None = None
        self._saved_cam_hpr: Vec3 | None = None
        self._has_updated: bool = False

        self._last_mouse_pos: tuple[float, float] | None = None
        self.is_pointer_captured: bool = False
        self.force_orbit: bool = False
        self._btn_mouse3 = MouseButton.three()

    @property
    def distance(self) -> float:
        """Current distance from camera to target."""
        return self._distance

    @distance.setter
    def distance(self, value: float) -> None:
        """Set distance, clamped between min_distance and max_distance."""
        self._distance = max(self.min_distance, min(self.max_distance, float(value)))

    @property
    def pitch(self) -> float:
        """Current pitch angle in degrees (clamped between min_pitch and max_pitch)."""
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        """Set pitch angle in degrees, clamped between min_pitch and max_pitch."""
        self._pitch = max(self.min_pitch, min(self.max_pitch, float(value)))

    @property
    def yaw(self) -> float:
        """Current yaw angle in degrees."""
        return self._yaw

    @yaw.setter
    def yaw(self, value: float) -> None:
        """Set yaw angle in degrees (normalized to [0, 360))."""
        self._yaw = float(value) % 360.0

    @property
    def camera(self) -> NodePath:
        """Return the managed camera NodePath."""
        return self.get_camera_node()

    @camera.setter
    def camera(self, cam: NodePath | None) -> None:
        """Set a custom camera NodePath."""
        self._camera_node = cam

    @property
    def current_cam_pos(self) -> Vec3:
        """Return the current smoothed camera position or computed ideal position."""
        if self._current_cam_pos is not None:
            return Vec3(self._current_cam_pos)
        return self.compute_ideal_position()

    def get_camera_node(self) -> NodePath:
        """Retrieve the camera NodePath safely, falling back to a dummy node in headless mode."""
        if self._camera_node is not None and not self._camera_node.isEmpty():
            return self._camera_node

        try:
            from src.globals.camera import Camera
            cam = Camera.get_camera()
            if cam is not None and not cam.isEmpty():
                self._camera_node = cam
                return cam
        except Exception:
            pass

        base = getattr(builtins, "base", None)
        cam = getattr(base, "camera", None) if base else None
        if cam is not None and hasattr(cam, "isEmpty") and not cam.isEmpty():
            self._camera_node = cam
            return cam

        self._camera_node = NodePath("headless_camera")
        return self._camera_node

    def set_pointer_captured(self, captured: bool) -> None:
        """Enable or disable pointer capture mode (relative mouse mode)."""
        self.is_pointer_captured = captured
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        if win is not None and hasattr(win, "requestProperties"):
            props = WindowProperties()
            if captured:
                props.setCursorHidden(True)
                props.setMouseMode(WindowProperties.M_relative)
            else:
                props.setCursorHidden(False)
                props.setMouseMode(WindowProperties.M_absolute)
            win.requestProperties(props)

    def zoom(self, delta: float) -> None:
        """Adjust camera distance by delta, clamped between min_distance and max_distance."""
        self.distance = self.distance + delta

    def zoom_in(self, step: float | None = None) -> None:
        """Zoom closer to target (decrease distance)."""
        delta = step if step is not None else self.zoom_step
        self.zoom(-delta)

    def zoom_out(self, step: float | None = None) -> None:
        """Zoom farther from target (increase distance)."""
        delta = step if step is not None else self.zoom_step
        self.zoom(delta)

    def _on_wheel_up(self) -> None:
        """Callback for mouse wheel up event: zooms in."""
        self.zoom_in()

    def _on_wheel_down(self) -> None:
        """Callback for mouse wheel down event: zooms out."""
        self.zoom_out()

    def _get_mouse_watcher(self):
        """Retrieve MouseWatcher node if engine is initialized with active input."""
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
        """Process horizontal and vertical mouse deltas and update yaw and pitch."""
        yaw_delta = dx * self.mouse_sensitivity
        pitch_delta = dy * self.mouse_sensitivity

        if not self.invert_yaw:
            self.yaw = (self.yaw - yaw_delta) % 360.0
        else:
            self.yaw = (self.yaw + yaw_delta) % 360.0

        if not self.invert_pitch:
            self.pitch = max(
                self.min_pitch,
                min(self.max_pitch, self.pitch - pitch_delta),
            )
        else:
            self.pitch = max(
                self.min_pitch,
                min(self.max_pitch, self.pitch + pitch_delta),
            )

    def get_target_pos(self) -> Vec3:
        """Compute the world-space target position (entity position + target_offset)."""
        if self.entity is None or self.entity.node is None or self.entity.node.isEmpty():
            return Vec3(self.target_offset)

        base = getattr(builtins, "base", None)
        render = getattr(base, "render", None) if base else None
        if render is not None and self.entity.node.hasParent():
            return self.entity.node.getPos(render) + self.target_offset
        return self.entity.node.getPos() + self.target_offset

    def compute_ideal_position(self) -> Vec3:
        """Compute the ideal spherical camera position centered at target_pos.

        cx = target_pos.x + distance * cos(pitch) * sin(yaw)
        cy = target_pos.y - distance * cos(pitch) * cos(yaw)
        cz = target_pos.z + distance * sin(-pitch) (Z-up in Panda3D)
        """
        target_pos = self.get_target_pos()
        pitch_rad = math.radians(self.pitch)
        yaw_rad = math.radians(self.yaw)

        cx = target_pos.x + self.distance * math.cos(pitch_rad) * math.sin(yaw_rad)
        cy = target_pos.y - self.distance * math.cos(pitch_rad) * math.cos(yaw_rad)
        cz = target_pos.z + self.distance * math.sin(-pitch_rad)
        return Vec3(cx, cy, cz)

    def get_forward_vector(self) -> Vec3:
        """Return the normalized 3D forward vector pointing from camera towards target."""
        pitch_rad = math.radians(self.pitch)
        yaw_rad = math.radians(self.yaw)
        fx = -math.cos(pitch_rad) * math.sin(yaw_rad)
        fy = math.cos(pitch_rad) * math.cos(yaw_rad)
        fz = -math.sin(-pitch_rad)
        return Vec3(fx, fy, fz)

    def get_camera_yaw(self) -> float:
        """Return the current camera yaw angle in degrees."""
        return self.yaw

    def snap_to_target(self) -> None:
        """Instantly place camera at ideal spherical position without smoothing."""
        target_pos = self.get_target_pos()
        ideal_pos = self.compute_ideal_position()
        self._current_cam_pos = Vec3(ideal_pos)
        self._has_updated = True
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            cam.setPos(ideal_pos)
            cam.lookAt(target_pos)

    def on_attach(self, entity: Entity) -> None:
        """Attach to entity, initialize camera reference, and save defaults."""
        super().on_attach(entity)
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            if self._saved_cam_pos is None:
                self._saved_cam_pos = Vec3(cam.getPos())
                self._saved_cam_hpr = Vec3(cam.getHpr())

    def on_start(self) -> None:
        """Register wheel listeners and initialize defaults on scene/entity start."""
        super().on_start()
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            if self._saved_cam_pos is None:
                self._saved_cam_pos = Vec3(cam.getPos())
                self._saved_cam_hpr = Vec3(cam.getHpr())

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "accept"):
            base.accept("wheel_up", self._on_wheel_up)
            base.accept("wheel_down", self._on_wheel_down)

    def on_update(self, dt: float) -> None:
        """Per-frame update: poll mouse input, update pitch/yaw, calculate ideal pos, lerp, and lookAt."""
        super().on_update(dt)
        if self.entity is None or self.entity.node is None or self.entity.node.isEmpty():
            return

        # Headless safety: check if base and base.win are available
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None

        if win is not None and hasattr(win, "getPointer"):
            mouse3_down = False
            watcher = self._get_mouse_watcher()
            if watcher is not None and hasattr(watcher, "is_button_down"):
                mouse3_down = watcher.is_button_down(self._btn_mouse3)

            is_orbiting = self.is_pointer_captured or mouse3_down or self.force_orbit

            if is_orbiting:
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

        target_pos = self.get_target_pos()
        ideal_pos = self.compute_ideal_position()
        cam = self.get_camera_node()

        if cam is not None and not cam.isEmpty():
            if not self._has_updated:
                self._current_cam_pos = Vec3(ideal_pos)
                self._has_updated = True
            else:
                t = 1.0 if self.smooth_speed <= 0.0 else min(1.0, max(0.0, self.smooth_speed * dt))
                self._current_cam_pos = self._current_cam_pos + (ideal_pos - self._current_cam_pos) * t

            cam.setPos(self._current_cam_pos)
            cam.lookAt(target_pos)

    def on_stop(self) -> None:
        """Restore camera defaults and unregister wheel listeners."""
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            base.ignore("wheel_up")
            base.ignore("wheel_down")

        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty():
            if self._saved_cam_pos is not None:
                cam.setPos(self._saved_cam_pos)
            if self._saved_cam_hpr is not None:
                cam.setHpr(self._saved_cam_hpr)

        self._last_mouse_pos = None
        self._has_updated = False
        super().on_stop()

    def on_detach(self) -> None:
        """Restore defaults and detach cleanly from entity."""
        self.on_stop()
        self._camera_node = None
        self._saved_cam_pos = None
        self._saved_cam_hpr = None
        super().on_detach()
