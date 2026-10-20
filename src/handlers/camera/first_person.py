from __future__ import annotations

import builtins
import logging
import math
from typing import TYPE_CHECKING
from panda3d.core import MouseButton, NodePath, Vec3, WindowProperties

from src.handlers.base import Handler

if TYPE_CHECKING:
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)


class FirstPersonCameraHandler(Handler):
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
        collision_margin: float = 0.15,
        hide_self: bool = True,
    ) -> None:
        super().__init__()
        self.eye_offset: Vec3 = Vec3(eye_offset)

        self.min_pitch: float = float(min_pitch)
        self.max_pitch: float = float(max_pitch)
        self._pitch: float = max(self.min_pitch, min(self.max_pitch, float(pitch)))
        self._yaw: float = float(yaw) % 360.0

        self.mouse_sensitivity: float = float(mouse_sensitivity)
        self.invert_yaw: bool = invert_yaw
        self.invert_pitch: bool = invert_pitch
        self.collision_enabled: bool = collision_enabled
        self.collision_margin: float = float(collision_margin)
        self.hide_self: bool = hide_self
        self._hidden_nodes: list[NodePath] = []

        self._camera_node: NodePath | None = camera
        self._saved_cam_pos: Vec3 | None = None
        self._saved_cam_hpr: Vec3 | None = None

        self._last_mouse_pos: tuple[float, float] | None = None
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base else None
        self.is_pointer_captured: bool = win is not None
        self._skip_first_mouse_delta: bool = True
        self._btn_mouse3 = MouseButton.three()

    @property
    def pitch(self) -> float:
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        self._pitch = max(self.min_pitch, min(self.max_pitch, float(value)))

    @property
    def yaw(self) -> float:
        return self._yaw

    @yaw.setter
    def yaw(self, value: float) -> None:
        self._yaw = float(value) % 360.0

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
            logger.debug("Global Camera unavailable; falling back to builtins.base.camera.", exc_info=True)

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
        self.set_pointer_captured(not self.is_pointer_captured)

    def _on_unlock_cursor(self) -> None:
        if self.is_pointer_captured:
            self.set_pointer_captured(False)

    def _on_lock_cursor(self) -> None:
        if not self.is_pointer_captured:
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
            self.yaw = (self.yaw - yaw_delta) % 360.0
        else:
            self.yaw = (self.yaw + yaw_delta) % 360.0

        if not self.invert_pitch:
            self.pitch = max(self.min_pitch, min(self.max_pitch, self.pitch - pitch_delta))
        else:
            self.pitch = max(self.min_pitch, min(self.max_pitch, self.pitch + pitch_delta))

    def get_target_pos(self) -> Vec3:
        if self.entity is not None:
            from src.handlers.physics.character import CharacterControllerHandler

            ctrl = self.entity.get_handler(CharacterControllerHandler)
            if ctrl is not None and ctrl.controller_np is not None and not ctrl.controller_np.isEmpty():
                base = getattr(builtins, "base", None)
                render = getattr(base, "render", None) if base else None
                if render is not None and ctrl.controller_np.hasParent():
                    return ctrl.controller_np.getPos(render) + self.eye_offset
                return ctrl.controller_np.getPos() + self.eye_offset

        if self.entity is None or self.entity.node is None or self.entity.node.isEmpty():
            return Vec3(self.eye_offset)

        base = getattr(builtins, "base", None)
        render = getattr(base, "render", None) if base else None
        if render is not None and self.entity.node.hasParent():
            return self.entity.node.getPos(render) + self.eye_offset
        return self.entity.node.getPos() + self.eye_offset

    def get_forward_vector(self) -> Vec3:
        pitch_rad = math.radians(self.pitch)
        yaw_rad = math.radians(self.yaw)
        fx = -math.cos(pitch_rad) * math.sin(yaw_rad)
        fy = math.cos(pitch_rad) * math.cos(yaw_rad)
        fz = math.sin(pitch_rad)
        return Vec3(fx, fy, fz)

    def get_eye_pos(self) -> Vec3:
        eye_pos = self.get_target_pos()
        return self._resolve_collision(eye_pos)

    def _resolve_collision(self, eye_pos: Vec3) -> Vec3:
        if not self.collision_enabled:
            return eye_pos

        from src.globals.physics import Physics

        directions = (
            Vec3(1, 0, 0),
            Vec3(-1, 0, 0),
            Vec3(0, 1, 0),
            Vec3(0, -1, 0),
            Vec3(0, 0, 1),
            Vec3(0, 0, -1),
        )
        origin = Vec3(eye_pos)
        adjusted = Vec3(eye_pos)
        for d in directions:
            hit = Physics.raycast_closest(origin, origin + d * (self.collision_margin + 0.02))
            if hit is None:
                continue
            hit_pos, _ = hit
            push = origin - hit_pos
            dist = push.length()
            if dist < self.collision_margin + 1e-6 and dist > 1e-6:
                push.normalize()
                adjusted += push * (self.collision_margin + 1e-6 - dist)
        return adjusted

    def apply_view(self) -> None:
        eye_pos = self.get_eye_pos()
        cam = self.get_camera_node()
        if cam is None or cam.isEmpty():
            return
        cam.setPos(eye_pos)
        cam.lookAt(eye_pos + self.get_forward_vector())

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
            base.accept("escape", self._on_unlock_cursor)
            base.accept("mouse1", self._on_lock_cursor)

        win = getattr(base, "win", None) if base else None
        if win is not None:
            self.set_pointer_captured(True)

    def on_update(self, dt: float) -> None:
        super().on_update(dt)
        if self.entity is None or self.entity.node is None or self.entity.node.isEmpty():
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

        self.apply_view()

    def on_stop(self) -> None:
        self._show_entity_model()
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            base.ignore("tab")
            base.ignore("escape")
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
        super().on_stop()

    def on_detach(self) -> None:
        self._show_entity_model()
        self.on_stop()
        self._camera_node = None
        self._saved_cam_pos = None
        self._saved_cam_hpr = None
        self._hidden_nodes.clear()
        super().on_detach()
