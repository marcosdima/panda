try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

import math
from panda3d.core import NodePath, Vec2, Vec3

from src.entities.entity import Entity
from src.handlers.camera.third_person import ThirdPersonCameraHandler
from src.handlers.input.base import InputHandler
from src.handlers.physics.character import CharacterControllerHandler


class TestCameraHandler(TerminalTest):
    """Headless unit test suite for ThirdPersonCameraHandler and camera-relative movement."""

    def on_start(self):
        self.print_title("TestCameraHandler started.", color="cyan")
        super().on_start()

    def test_camera_handler_attachment_and_defaults(self):
        self.print_subtitle("Testing ThirdPersonCameraHandler attachment, defaults, and lifecycle.")
        entity = Entity("CameraTargetHero")
        cam_node = NodePath("custom_test_camera")
        handler = ThirdPersonCameraHandler(
            distance=8.0,
            min_distance=2.0,
            max_distance=25.0,
            target_offset=Vec3(0.0, 0.0, 1.5),
            pitch=-15.0,
            min_pitch=-75.0,
            max_pitch=45.0,
            yaw=0.0,
            smooth_speed=10.0,
            mouse_sensitivity=0.2,
            camera=cam_node,
        )

        assert handler.distance == 8.0
        assert handler.min_distance == 2.0
        assert handler.max_distance == 25.0
        assert handler.target_offset == Vec3(0.0, 0.0, 1.5)
        assert handler.pitch == -15.0
        assert handler.min_pitch == -75.0
        assert handler.max_pitch == 45.0
        assert handler.yaw == 0.0
        assert handler.smooth_speed == 10.0
        assert handler.mouse_sensitivity == 0.2
        assert handler.camera == cam_node

        # Attach to entity
        entity.add_handler(handler)
        assert entity.get_handler(ThirdPersonCameraHandler) is handler

        entity.start()
        entity.update(0.016)

        # Verify camera position updated
        assert not cam_node.isEmpty()
        assert cam_node.getPos() != Vec3(0, 0, 0)

        # Stop and detach
        entity.stop()
        entity.remove_handler(handler)
        assert entity.get_handler(ThirdPersonCameraHandler) is None
        assert handler.entity is None

        entity.free()
        self.p("ThirdPersonCameraHandler attachment and lifecycle verified successfully.", color="green")
        self.space_line()

    def test_pitch_yaw_spherical_calculations(self):
        self.print_subtitle("Testing spherical coordinate calculations for pitch and yaw.")
        entity = Entity("SphericalHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("calc_cam")
        handler = ThirdPersonCameraHandler(
            distance=8.0,
            target_offset=Vec3(0.0, 0.0, 1.5),
            pitch=0.0,
            yaw=0.0,
            camera=cam_node,
        )
        entity.add_handler(handler)
        entity.start()

        # 1. Yaw = 0, Pitch = 0, Distance = 8.0
        # Target pos = (0, 0, 1.5)
        # cx = 0 + 8 * cos(0) * sin(0) = 0
        # cy = 0 - 8 * cos(0) * cos(0) = -8
        # cz = 1.5 + 8 * sin(0) = 1.5
        ideal_pos = handler.compute_ideal_position()
        assert abs(ideal_pos.x - 0.0) < 1e-4, f"Expected 0.0, got {ideal_pos.x}"
        assert abs(ideal_pos.y - (-8.0)) < 1e-4, f"Expected -8.0, got {ideal_pos.y}"
        assert abs(ideal_pos.z - 1.5) < 1e-4, f"Expected 1.5, got {ideal_pos.z}"

        fwd = handler.get_forward_vector()
        assert abs(fwd.x - 0.0) < 1e-4
        assert abs(fwd.y - 1.0) < 1e-4
        assert abs(fwd.z - 0.0) < 1e-4
        assert handler.get_camera_yaw() == 0.0

        # 2. Yaw = 90, Pitch = 0, Distance = 8.0 (Camera at +X looking along -X)
        handler.yaw = 90.0
        ideal_pos = handler.compute_ideal_position()
        assert abs(ideal_pos.x - 8.0) < 1e-4, f"Expected 8.0, got {ideal_pos.x}"
        assert abs(ideal_pos.y - 0.0) < 1e-4, f"Expected 0.0, got {ideal_pos.y}"
        assert abs(ideal_pos.z - 1.5) < 1e-4, f"Expected 1.5, got {ideal_pos.z}"

        fwd = handler.get_forward_vector()
        assert abs(fwd.x - (-1.0)) < 1e-4
        assert abs(fwd.y - 0.0) < 1e-4
        assert abs(fwd.z - 0.0) < 1e-4
        assert handler.get_camera_yaw() == 90.0

        # 3. Yaw = 270 (or -90), Pitch = 0, Distance = 8.0 (Camera at -X looking along +X)
        handler.yaw = 270.0
        ideal_pos = handler.compute_ideal_position()
        assert abs(ideal_pos.x - (-8.0)) < 1e-4, f"Expected -8.0, got {ideal_pos.x}"
        assert abs(ideal_pos.y - 0.0) < 1e-4, f"Expected 0.0, got {ideal_pos.y}"
        assert abs(ideal_pos.z - 1.5) < 1e-4, f"Expected 1.5, got {ideal_pos.z}"

        fwd = handler.get_forward_vector()
        assert abs(fwd.x - 1.0) < 1e-4
        assert abs(fwd.y - 0.0) < 1e-4
        assert abs(fwd.z - 0.0) < 1e-4

        # 4. Yaw = 180, Pitch = 0, Distance = 8.0 (Camera in front at +Y looking along -Y)
        handler.yaw = 180.0
        ideal_pos = handler.compute_ideal_position()
        assert abs(ideal_pos.x - 0.0) < 1e-4, f"Expected 0.0, got {ideal_pos.x}"
        assert abs(ideal_pos.y - 8.0) < 1e-4, f"Expected 8.0, got {ideal_pos.y}"
        assert abs(ideal_pos.z - 1.5) < 1e-4, f"Expected 1.5, got {ideal_pos.z}"

        fwd = handler.get_forward_vector()
        assert abs(fwd.x - 0.0) < 1e-4
        assert abs(fwd.y - (-1.0)) < 1e-4
        assert abs(fwd.z - 0.0) < 1e-4

        # 5. Yaw = 0, Pitch = -30 (Camera elevated looking down at target)
        handler.yaw = 0.0
        handler.pitch = -30.0
        ideal_pos = handler.compute_ideal_position()
        expected_cy = -8.0 * math.cos(math.radians(-30.0))
        expected_cz = 1.5 + 8.0 * math.sin(math.radians(30.0))
        assert abs(ideal_pos.x - 0.0) < 1e-4
        assert abs(ideal_pos.y - expected_cy) < 1e-4
        assert abs(ideal_pos.z - expected_cz) < 1e-4

        entity.stop()
        entity.free()
        self.p("Spherical coordinates pitch/yaw calculations verified successfully.", color="green")
        self.space_line()

    def test_distance_clamping_and_zoom(self):
        self.print_subtitle("Testing camera distance clamping and zoom functionality.")
        handler = ThirdPersonCameraHandler(
            distance=8.0,
            min_distance=2.0,
            max_distance=25.0,
            zoom_step=1.0,
        )

        assert handler.distance == 8.0

        # Zoom in
        handler.zoom_in(3.0)
        assert abs(handler.distance - 5.0) < 1e-4

        # Zoom in beyond min_distance
        handler.zoom_in(20.0)
        assert abs(handler.distance - 2.0) < 1e-4, f"Expected 2.0, got {handler.distance}"

        # Zoom out
        handler.zoom_out(10.0)
        assert abs(handler.distance - 12.0) < 1e-4

        # Zoom out beyond max_distance
        handler.zoom_out(50.0)
        assert abs(handler.distance - 25.0) < 1e-4, f"Expected 25.0, got {handler.distance}"

        # Direct property assignment clamps
        handler.distance = -100.0
        assert abs(handler.distance - 2.0) < 1e-4
        handler.distance = 500.0
        assert abs(handler.distance - 25.0) < 1e-4

        self.p("Distance clamping and zoom operations verified successfully.", color="green")
        self.space_line()

    def test_pitch_clamping_and_mouse_delta(self):
        self.print_subtitle("Testing pitch angle clamping and mouse delta processing.")
        handler = ThirdPersonCameraHandler(
            pitch=-15.0,
            min_pitch=-75.0,
            max_pitch=45.0,
            yaw=0.0,
            mouse_sensitivity=0.2,
        )

        assert handler.pitch == -15.0

        # Direct property clamping
        handler.pitch = -100.0
        assert abs(handler.pitch - (-75.0)) < 1e-4
        handler.pitch = 90.0
        assert abs(handler.pitch - 45.0) < 1e-4

        # Mouse delta processing: dx=10 (turns yaw), dy=20 (tilts pitch)
        handler.yaw = 100.0
        handler.pitch = 0.0
        # dx = 10 -> delta_yaw = 10 * 0.2 = 2.0 deg -> yaw = 98.0
        # dy = 20 -> delta_pitch = 20 * 0.2 = 4.0 deg -> pitch = -4.0
        handler.handle_mouse_delta(dx=10.0, dy=20.0)
        assert abs(handler.yaw - 98.0) < 1e-4, f"Expected 98.0, got {handler.yaw}"
        assert abs(handler.pitch - (-4.0)) < 1e-4, f"Expected -4.0, got {handler.pitch}"

        # Mouse delta with extreme dy respects clamping
        handler.handle_mouse_delta(dx=0.0, dy=1000.0)
        assert abs(handler.pitch - (-75.0)) < 1e-4
        handler.handle_mouse_delta(dx=0.0, dy=-2000.0)
        assert abs(handler.pitch - 45.0) < 1e-4

        self.p("Pitch clamping and mouse delta processing verified successfully.", color="green")
        self.space_line()

    def test_target_tracking_and_smoothing(self):
        self.print_subtitle("Testing target tracking, smooth lerp interpolation, and snap_to_target.")
        entity = Entity("MovingHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("smoothing_cam")
        handler = ThirdPersonCameraHandler(
            distance=10.0,
            target_offset=Vec3(0.0, 0.0, 2.0),
            pitch=0.0,
            yaw=0.0,
            smooth_speed=10.0,
            camera=cam_node,
        )
        entity.add_handler(handler)
        entity.start()

        # First update snaps/initializes camera position to ideal position
        entity.update(0.016)
        initial_ideal = handler.compute_ideal_position()
        assert (cam_node.getPos() - initial_ideal).length() < 1e-4

        # Teleport entity to new location
        entity.node.setPos(50.0, 50.0, 10.0)
        new_ideal = handler.compute_ideal_position()

        # One small frame update: position should smoothly move towards new ideal
        entity.update(0.016)
        pos_after_1_frame = cam_node.getPos()
        dist_to_ideal = (new_ideal - pos_after_1_frame).length()
        assert dist_to_ideal > 0.0, "Camera should not instantly snap during smooth update"
        assert dist_to_ideal < (new_ideal - initial_ideal).length(), "Camera should move closer to ideal"

        # snap_to_target() forces immediate sync
        handler.snap_to_target()
        assert (cam_node.getPos() - new_ideal).length() < 1e-4

        entity.stop()
        entity.free()
        self.p("Target tracking, smooth lerp, and snap_to_target verified successfully.", color="green")
        self.space_line()

    def test_headless_safety(self):
        self.print_subtitle("Testing headless safety without graphical window or MouseWatcher.")
        entity = Entity("HeadlessCamHero")
        handler = ThirdPersonCameraHandler()
        entity.add_handler(handler)

        entity.start()
        # Updates must complete cleanly without throwing exceptions
        entity.update(0.016)
        entity.update(0.033)
        entity.update(0.1)

        fwd = handler.get_forward_vector()
        assert isinstance(fwd, Vec3)
        assert abs(fwd.length() - 1.0) < 1e-4

        entity.stop()
        entity.free()
        self.p("Headless safety verified successfully.", color="green")
        self.space_line()

    def test_camera_relative_character_movement(self):
        self.print_subtitle("Testing camera-relative character movement with CharacterControllerHandler.")
        entity = Entity("CameraRelativeHero")
        visual_node = entity.node.attachNewNode("hero_visual")
        cam_node = NodePath("tps_cam")

        input_handler = InputHandler()
        cam_handler = ThirdPersonCameraHandler(
            pitch=0.0,
            yaw=0.0,
            camera=cam_node,
        )
        controller = CharacterControllerHandler(
            walk_speed=5.0,
            sprint_speed=10.0,
            visual_node=visual_node,
            turn_speed=0.0,  # 0.0 enables instant heading snap for exact testing
        )

        entity.add_handler(input_handler)
        entity.add_handler(cam_handler)
        entity.add_handler(controller)
        entity.start()

        # 1. Camera yaw = 0 (Camera facing +Y)
        # Forward (W): input (0, 1) -> moves along +Y (0, 5, 0), visual heading = 0 deg
        input_handler.set_move_vector(0.0, 1.0)
        entity.update(0.016)
        assert abs(controller.linear_velocity.x - 0.0) < 1e-4
        assert abs(controller.linear_velocity.y - 5.0) < 1e-4
        assert abs((visual_node.getH() % 360.0) - 0.0) < 1e-4

        # Right (D): input (1, 0) -> moves along +X (5, 0, 0), visual heading = -90 deg (270 deg)
        input_handler.set_move_vector(1.0, 0.0)
        entity.update(0.016)
        assert abs(controller.linear_velocity.x - 5.0) < 1e-4
        assert abs(controller.linear_velocity.y - 0.0) < 1e-4
        assert abs((visual_node.getH() % 360.0) - 270.0) < 1e-4

        # Backward (S): input (0, -1) -> moves along -Y (0, -5, 0), visual heading = 180 deg
        input_handler.set_move_vector(0.0, -1.0)
        entity.update(0.016)
        assert abs(controller.linear_velocity.x - 0.0) < 1e-4
        assert abs(controller.linear_velocity.y - (-5.0)) < 1e-4
        assert abs((visual_node.getH() % 360.0) - 180.0) < 1e-4

        # Left (A): input (-1, 0) -> moves along -X (-5, 0, 0), visual heading = 90 deg
        input_handler.set_move_vector(-1.0, 0.0)
        entity.update(0.016)
        assert abs(controller.linear_velocity.x - (-5.0)) < 1e-4
        assert abs(controller.linear_velocity.y - 0.0) < 1e-4
        assert abs((visual_node.getH() % 360.0) - 90.0) < 1e-4

        # 2. Camera yaw = 90 (Camera positioned at +X looking along -X)
        cam_handler.yaw = 90.0
        # Forward (W): should move along camera's forward (-X), velocity = (-5, 0, 0), heading = 90 deg
        input_handler.set_move_vector(0.0, 1.0)
        entity.update(0.016)
        assert abs(controller.linear_velocity.x - (-5.0)) < 1e-4
        assert abs(controller.linear_velocity.y - 0.0) < 1e-4
        assert abs((visual_node.getH() % 360.0) - 90.0) < 1e-4

        # Right (D): should move along camera's right (+Y), velocity = (0, 5, 0), heading = 0 deg
        input_handler.set_move_vector(1.0, 0.0)
        entity.update(0.016)
        assert abs(controller.linear_velocity.x - 0.0) < 1e-4
        assert abs(controller.linear_velocity.y - 5.0) < 1e-4
        assert abs((visual_node.getH() % 360.0) - 0.0) < 1e-4

        # 3. Fallback when camera handler is removed
        entity.remove_handler(cam_handler)
        input_handler.set_move_vector(0.0, 1.0)
        entity.update(0.016)
        # Local movement fallback
        assert abs(controller.linear_velocity.x - 0.0) < 1e-4
        assert abs(controller.linear_velocity.y - 5.0) < 1e-4

        entity.stop()
        entity.free()
        self.p("Camera-relative character movement and heading rotation verified successfully.", color="green")
        self.space_line()

    def on_stop(self):
        self.print_subtitle("TestCameraHandler completed.")


if __name__ == "__main__":
    test = TestCameraHandler()
    test.on_start()
    test.on_stop()
