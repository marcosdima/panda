from __future__ import annotations

import builtins
import logging
import math
from typing import TYPE_CHECKING

from panda3d.core import MouseButton, NodePath, Vec3, WindowProperties

from src.handlers.base import Handler
from src.handlers.camera.presets import PRESETS_BY_NAME, CameraPreset
from src.utils.handler_phase import HandlerPhase
from src.utils.math import clamp, normalize_angle
from src.utils.position import world_position

if TYPE_CHECKING:
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)


class ThirdPersonCameraHandler(Handler):
    phase = HandlerPhase.POST
    """Third-person orbit camera handler with spherical coordinates, mouse orbit, and position smoothing."""

    def __init__(
        self,
        distance: float = 8.0,
        min_distance: float = 2.0,
        max_distance: float = 25.0,
        target_offset: Vec3 | None = None,
        pitch: float = -15.0,
        min_pitch: float = -75.0,
        max_pitch: float = 45.0,
        yaw: float = 0.0,
        smooth_speed: float = 10.0,
        mouse_sensitivity: float = 0.2,
        zoom_step: float = 1.0,
        zoom_speed: float = 10.0,
        camera: NodePath | None = None,
        invert_yaw: bool = False,
        invert_pitch: bool = False,
        collision_enabled: bool = True,
        collision_margin: float = 0.3,
        shoulder_offset: Vec3 | None = None,
        owner_min_distance: float = 1.0,
        preset: CameraPreset | str | None = None,
    ) -> None:
        super().__init__()
        self.min_distance: float = float(min_distance)
        self.max_distance: float = float(max_distance)
        self._distance: float = clamp(float(distance), self.min_distance, self.max_distance)
        self._target_distance: float = self._distance

        self.target_offset: Vec3 = Vec3(target_offset) if target_offset is not None else Vec3(0.0, 0.0, 1.5)

        self.min_pitch: float = float(min_pitch)
        self.max_pitch: float = float(max_pitch)
        self._pitch: float = clamp(float(pitch), self.min_pitch, self.max_pitch)

        self._yaw: float = normalize_angle(float(yaw), 0.0)

        self.smooth_speed: float = float(smooth_speed)
        self.mouse_sensitivity: float = float(mouse_sensitivity)
        self.zoom_step: float = float(zoom_step)
        self.zoom_speed: float = float(zoom_speed)
        self.invert_yaw: bool = invert_yaw
        self.invert_pitch: bool = invert_pitch
        self.collision_enabled: bool = collision_enabled
        self.owner_min_distance: float = float(owner_min_distance)
        self.collision_margin: float = float(collision_margin)
        self.shoulder_offset: Vec3 = Vec3(shoulder_offset) if shoulder_offset is not None else Vec3(0.0, 0.0, 0.0)

        if preset is not None:
            self.apply_preset(preset, snap=False)

        self._camera_node: NodePath | None = camera
        self._current_cam_pos: Vec3 | None = None
        self._saved_cam_pos: Vec3 | None = None
        self._saved_cam_hpr: Vec3 | None = None
        self._has_updated: bool = False

        self._last_mouse_pos: tuple[float, float] | None = None
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        self.is_pointer_captured: bool = win is not None
        self._captured_before_pause: bool = self.is_pointer_captured
        self._skip_first_mouse_delta: bool = True
        self.force_orbit: bool = False
        self._btn_mouse3 = MouseButton.three()

    @property
    def distance(self) -> float:
        """Current distance from camera to target."""
        return self._distance

    @distance.setter
    def distance(self, value: float) -> None:
        """Set distance, clamped between min_distance and max_distance."""
        self._distance = clamp(float(value), self.min_distance, self.max_distance)

    @property
    def target_distance(self) -> float:
        """Target distance the camera is smoothly zooming towards."""
        return self._target_distance

    @target_distance.setter
    def target_distance(self, value: float) -> None:
        """Set target zoom distance, clamped between min_distance and max_distance."""
        self._target_distance = clamp(float(value), self.min_distance, self.max_distance)

    @property
    def pitch(self) -> float:
        """Current pitch angle in degrees (clamped between min_pitch and max_pitch)."""
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        """Set pitch angle in degrees, clamped between min_pitch and max_pitch."""
        self._pitch = clamp(float(value), self.min_pitch, self.max_pitch)

    @property
    def yaw(self) -> float:
        """Current yaw angle in degrees."""
        return self._yaw

    @yaw.setter
    def yaw(self, value: float) -> None:
        """Set yaw angle in degrees (normalized to [0, 360))."""
        self._yaw = normalize_angle(float(value), 0.0)

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
            logger.debug(
                "Global Camera unavailable; falling back to builtins.base.camera.",
                exc_info=True,
            )

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
        """Toggle pointer capture mode (bound to Tab key)."""
        base = getattr(builtins, "base", None)
        if getattr(base, "paused", False):
            return
        self.set_pointer_captured(not self.is_pointer_captured)

    def _on_unlock_cursor(self) -> None:
        """Unlock pointer capture and show cursor."""
        if self.is_pointer_captured:
            self.set_pointer_captured(False)

    def _on_lock_cursor(self) -> None:
        """Lock pointer capture and hide cursor on click (bound to mouse1) when not paused."""
        base = getattr(builtins, "base", None)
        if getattr(base, "paused", False):
            return
        if not self.is_pointer_captured:
            self.set_pointer_captured(True)

    def _on_game_paused(self, paused: bool) -> None:
        """Release pointer capture on pause and restore it on resume."""
        if paused:
            self._captured_before_pause = self.is_pointer_captured
            if self.is_pointer_captured:
                self.set_pointer_captured(False)
        else:
            base = getattr(builtins, "base", None)
            win = getattr(base, "win", None) if base else None
            if win is not None and self._captured_before_pause:
                self.set_pointer_captured(True)

    def zoom(self, delta: float) -> None:
        """Adjust camera distance by delta, clamped between min_distance and max_distance.

        Sets both the current and target distance so the change is immediate
        (backwards compatible). Use ``target_distance`` directly for smooth,
        interpolated zooming driven from outside the handler.
        """
        new_dist = self.distance + delta
        self.distance = new_dist
        self.target_distance = new_dist

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
            self.yaw = normalize_angle(self.yaw - yaw_delta, 0.0)
        else:
            self.yaw = normalize_angle(self.yaw + yaw_delta, 0.0)

        if not self.invert_pitch:
            self.pitch = clamp(self.pitch - pitch_delta, self.min_pitch, self.max_pitch)
        else:
            self.pitch = clamp(self.pitch + pitch_delta, self.min_pitch, self.max_pitch)

    def get_target_pos(self) -> Vec3:
        """Compute the world-space target position (entity position + target_offset).

        Uses the authoritative entity position, so it follows the character
        controller node when one is attached.
        """
        if self.entity is None:
            return Vec3(self.target_offset)
        return world_position(self.entity) + self.target_offset

    def compute_ideal_position(self) -> Vec3:
        """Compute the ideal spherical camera position centered at target_pos.

        Applies an over-the-shoulder offset (rotated around Z by yaw) so the
        camera does not look straight through the back of the owner model.
        """
        target_pos = self.get_target_pos()
        pitch_rad = math.radians(self.pitch)
        yaw_rad = math.radians(self.yaw)

        cx = target_pos.x + self.distance * math.cos(pitch_rad) * math.sin(yaw_rad)
        cy = target_pos.y - self.distance * math.cos(pitch_rad) * math.cos(yaw_rad)
        cz = target_pos.z + self.distance * math.sin(-pitch_rad)

        # Over-the-shoulder offset rotated into world space by yaw
        so_x = self.shoulder_offset.x * math.cos(yaw_rad) - self.shoulder_offset.y * math.sin(yaw_rad)
        so_y = self.shoulder_offset.x * math.sin(yaw_rad) + self.shoulder_offset.y * math.cos(yaw_rad)
        so_z = self.shoulder_offset.z

        return Vec3(cx + so_x, cy + so_y, cz + so_z)

    def resolve_collision_position(self, target_pos: Vec3, ideal_pos: Vec3) -> Vec3:
        """Shorten the camera boom to the closest obstacle between the target and ideal position.

        Casts a ray from target_pos towards ideal_pos; when an obstacle is hit, the
        camera is pulled in front of the impact (minus collision_margin) so the view
        never ends up behind or inside world geometry. Returns the ideal position
        unchanged when collision handling is disabled or the path is clear.
        """
        if not self.collision_enabled:
            resolved = ideal_pos
        else:
            offset = ideal_pos - target_pos
            distance = offset.length()
            if distance <= 1e-5:
                resolved = ideal_pos
            else:
                from src.globals.physics import Physics

                hit = Physics.raycast_closest(target_pos, ideal_pos, step_physics=False)
                if hit is None:
                    resolved = ideal_pos
                else:
                    hit_pos, _ = hit
                    hit_distance = (target_pos - hit_pos).length()
                    clamped_distance = max(self.min_distance, hit_distance - self.collision_margin)
                    if clamped_distance >= distance:
                        resolved = ideal_pos
                    else:
                        direction = offset / distance
                        resolved = target_pos + direction * clamped_distance

        # Prevent the camera from clipping into the owner entity itself.
        # If the camera ends up closer than owner_min_distance to the target,
        # push it out along the view direction so the player is never seen
        # from behind or from inside their own model. This runs unconditionally
        # so it applies even when no world geometry blocks the view.
        owner_offset = resolved - target_pos
        owner_dist = owner_offset.length()
        if owner_dist < self.owner_min_distance and owner_dist > 1e-5:
            safe_dir = owner_offset / owner_dist
            resolved = target_pos + safe_dir * self.owner_min_distance
        elif owner_dist <= 1e-5:
            resolved = target_pos + Vec3(0.0, -self.owner_min_distance, 0.0)

        return resolved

    def get_forward_vector(self) -> Vec3:
        """Return the normalized 3D forward vector pointing from camera towards target."""
        pitch_rad = math.radians(self.pitch)
        yaw_rad = math.radians(self.yaw)
        fx = -math.cos(pitch_rad) * math.sin(yaw_rad)
        fy = math.cos(pitch_rad) * math.cos(yaw_rad)
        fz = -math.sin(-pitch_rad)
        return Vec3(fx, fy, fz)

    def apply_preset(self, preset: CameraPreset | str, snap: bool = True) -> None:
        """Apply a standard CameraPreset configuration."""
        if isinstance(preset, str):
            key = preset.lower()
            if key not in PRESETS_BY_NAME:
                raise ValueError(f"Unknown camera preset: {preset}. Choose from {list(PRESETS_BY_NAME.keys())}")
            resolved = PRESETS_BY_NAME[key]
        else:
            resolved = preset

        self.min_distance = resolved.min_distance
        self.max_distance = resolved.max_distance
        self.min_pitch = resolved.min_pitch
        self.max_pitch = resolved.max_pitch
        self.pitch = resolved.pitch
        self.distance = resolved.distance
        self.target_distance = resolved.distance
        self.target_offset = Vec3(resolved.target_offset)
        self.shoulder_offset = Vec3(resolved.shoulder_offset)
        if snap:
            self.snap_to_target()

    def get_camera_yaw(self) -> float:
        """Return the current camera yaw angle in degrees."""
        return self.yaw

    def get_body_yaw(self) -> float:
        """Return the yaw angle the character body should face.

        In Panda3D, heading 0 faces +Y, -90 faces +X (right), 90 faces -X (left).
        Returns the body yaw normalized to [0, 360).
        """
        fwd = self.get_forward_vector()
        return normalize_angle(-math.degrees(math.atan2(fwd.x, fwd.y)), 0.0)

    def snap_to_target(self) -> None:
        """Instantly place camera at ideal spherical position without smoothing."""
        target_pos = self.get_target_pos()
        ideal_pos = self.compute_ideal_position()
        ideal_pos = self.resolve_collision_position(target_pos, ideal_pos)
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
        if cam is not None and not cam.isEmpty() and self._saved_cam_pos is None:
            self._saved_cam_pos = Vec3(cam.getPos())
            self._saved_cam_hpr = Vec3(cam.getHpr())

    def on_start(self) -> None:
        """Register input listeners, enable pointer capture in graphical mode, and initialize defaults."""
        super().on_start()
        cam = self.get_camera_node()
        if cam is not None and not cam.isEmpty() and self._saved_cam_pos is None:
            self._saved_cam_pos = Vec3(cam.getPos())
            self._saved_cam_hpr = Vec3(cam.getHpr())

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "accept"):
            base.accept("wheel_up", self._on_wheel_up)
            base.accept("wheel_down", self._on_wheel_down)
            base.accept("tab", self._on_toggle_cursor)
            base.accept("mouse1", self._on_lock_cursor)

        from src.utils import bus

        bus.subscribe("game_paused", self._on_game_paused)

        win = getattr(base, "win", None) if base else None
        if win is not None and not getattr(base, "paused", False):
            self.set_pointer_captured(True)

    def on_update(self, dt: float) -> None:
        """Per-frame update: poll mouse input and update pitch/yaw/orbit/look."""
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

        # Smoothly interpolate distance toward target_distance (zoom smoothing)
        if self._distance != self._target_distance:
            t = 1.0 if self.zoom_speed <= 0.0 else clamp(self.zoom_speed * dt, 0.0, 1.0)
            self._distance = self._distance + (self._target_distance - self._distance) * t

    def on_post_update(self, dt: float) -> None:
        """Apply camera transform after physics step."""
        super().on_post_update(dt)
        if self.entity is None or self.entity.node is None or self.entity.node.isEmpty():
            return

        target_pos = self.get_target_pos()
        ideal_pos = self.compute_ideal_position()
        ideal_pos = self.resolve_collision_position(target_pos, ideal_pos)
        cam = self.get_camera_node()

        if cam is not None and not cam.isEmpty():
            if not self._has_updated:
                self._current_cam_pos = Vec3(ideal_pos)
                self._has_updated = True
            else:
                t = 1.0 if self.smooth_speed <= 0.0 else clamp(self.smooth_speed * dt, 0.0, 1.0)
                self._current_cam_pos = self._current_cam_pos + (ideal_pos - self._current_cam_pos) * t

            cam.setPos(self._current_cam_pos)
            cam.lookAt(target_pos)

    def on_stop(self) -> None:
        """Restore camera defaults, mouse mode, and unregister input listeners."""
        super().on_stop()
        from src.utils import bus

        bus.unsubscribe("game_paused", self._on_game_paused)
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            base.ignore("wheel_up")
            base.ignore("wheel_down")
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
        self._has_updated = False

    def on_detach(self) -> None:
        """Restore defaults and detach cleanly from entity."""
        super().on_detach()
        self.on_stop()
        self._camera_node = None
        self._saved_cam_pos = None
        self._saved_cam_hpr = None
