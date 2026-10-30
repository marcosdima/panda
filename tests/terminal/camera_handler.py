try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

import math

from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.handlers.camera.first_person import FirstPersonCameraHandler
from src.handlers.camera.presets import (
    ADVENTURE_PRESET,
    ISOMETRIC_PRESET,
    OVERHEAD_PRESET,
    SHOOTER_PRESET,
)
from src.handlers.camera.third_person import ThirdPersonCameraHandler
from src.handlers.input.base import InputHandler
from src.handlers.physics.character import (
    CharacterControllerHandler,
    CharacterOrientationMode,
)


class TestCameraHandler(TerminalTest):
    """Headless unit test suite for ThirdPersonCameraHandler, FirstPersonCameraHandler and camera-relative movement."""

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
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)

        # Verify camera position updated
        assert not cam_node.isEmpty()
        assert cam_node.getPos() != Vec3(0, 0, 0)

        # Stop and detach
        entity.stop()
        entity.remove_handler(handler)
        assert entity.get_handler(ThirdPersonCameraHandler) is None
        assert handler.entity is None

        entity.free()
        self.p(
            "ThirdPersonCameraHandler attachment and lifecycle verified successfully.",
            color="green",
        )
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
        self.p(
            "Spherical coordinates pitch/yaw calculations verified successfully.",
            color="green",
        )
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

        self.p(
            "Distance clamping and zoom operations verified successfully.",
            color="green",
        )
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

        self.p(
            "Pitch clamping and mouse delta processing verified successfully.",
            color="green",
        )
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

        # Disable pointer capture so real mouse input (when a window is present)
        # cannot pollute the deterministic position assertions below.
        handler.set_pointer_captured(False)

        # First update snaps/initializes camera position to ideal position
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        initial_ideal = handler.compute_ideal_position()
        assert (cam_node.getPos() - initial_ideal).length() < 1e-4

        # Teleport entity to new location
        entity.node.setPos(50.0, 50.0, 10.0)
        new_ideal = handler.compute_ideal_position()

        # One small frame update: position should smoothly move towards new ideal
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        pos_after_1_frame = cam_node.getPos()
        dist_to_ideal = (new_ideal - pos_after_1_frame).length()
        assert dist_to_ideal > 0.0, "Camera should not instantly snap during smooth update"
        assert dist_to_ideal < (new_ideal - initial_ideal).length(), "Camera should move closer to ideal"

        # snap_to_target() forces immediate sync
        handler.snap_to_target()
        assert (cam_node.getPos() - new_ideal).length() < 1e-4

        entity.stop()
        entity.free()
        self.p(
            "Target tracking, smooth lerp, and snap_to_target verified successfully.",
            color="green",
        )
        self.space_line()

    def test_camera_tracks_character_controller_nodepath(self):
        self.print_subtitle("Testing camera tracking of CharacterControllerHandler controller_np.")
        entity = Entity("PhysicsTrackedHero")
        controller = CharacterControllerHandler()
        cam_handler = ThirdPersonCameraHandler(
            distance=8.0,
            target_offset=Vec3(0.0, 0.0, 1.5),
        )
        entity.add_handler(controller)
        entity.add_handler(cam_handler)
        entity.start()

        # Place controller_np at a specific world position
        assert controller.controller_np is not None
        controller.controller_np.setPos(15.0, 25.0, 3.0)

        # get_target_pos() must track controller_np + target_offset
        target_pos = cam_handler.get_target_pos()
        expected = Vec3(15.0, 25.0, 4.5)
        assert (target_pos - expected).length() < 1e-4, f"Expected {expected}, got {target_pos}"

        entity.stop()
        entity.free()
        self.p(
            "Camera tracking of CharacterControllerHandler controller_np verified successfully.",
            color="green",
        )
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

        # Disable pointer capture so real mouse input (when a window is present)
        # cannot pollute the deterministic yaw/pitch assertions below.
        cam_handler.set_pointer_captured(False)

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
        self.p(
            "Camera-relative character movement and heading rotation verified successfully.",
            color="green",
        )
        self.space_line()

    def test_first_person_camera_defaults_and_eye_lock(self):
        self.print_subtitle("Testing FirstPersonCameraHandler defaults, eye lock, and view orientation.")
        entity = Entity("FirstPersonHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("fp_test_camera")
        handler = FirstPersonCameraHandler(
            eye_offset=Vec3(0.0, 0.0, 1.7),
            yaw=0.0,
            pitch=0.0,
            min_pitch=-80.0,
            max_pitch=70.0,
            mouse_sensitivity=0.15,
            camera=cam_node,
        )

        assert handler.eye_offset == Vec3(0.0, 0.0, 1.7)
        assert handler.yaw == 0.0
        assert handler.pitch == 0.0
        assert handler.min_pitch == -80.0
        assert handler.max_pitch == 70.0
        assert handler.mouse_sensitivity == 0.15
        assert handler.camera == cam_node

        entity.add_handler(handler)
        assert entity.get_handler(FirstPersonCameraHandler) is handler

        entity.start()
        handler.set_pointer_captured(False)
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)

        # Camera locked at entity position + eye offset
        expected_eye = Vec3(0.0, 0.0, 1.7)
        assert (cam_node.getPos() - expected_eye).length() < 1e-4, f"Expected {expected_eye}, got {cam_node.getPos()}"

        # Camera view direction (local +Y after lookAt) matches forward vector
        cam_fwd = cam_node.getQuat().xform(Vec3(0.0, 1.0, 0.0))
        fwd = handler.get_forward_vector()
        assert (cam_fwd - fwd).length() < 1e-4, f"Expected {fwd}, got {cam_fwd}"

        # Yaw = 90 turns the view towards -X
        handler.yaw = 90.0
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        cam_fwd = cam_node.getQuat().xform(Vec3(0.0, 1.0, 0.0))
        fwd = handler.get_forward_vector()
        assert abs(fwd.x - (-1.0)) < 1e-4
        assert (cam_fwd - fwd).length() < 1e-4

        # Moving the entity moves the locked eye position
        entity.node.setPos(10.0, -5.0, 2.0)
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        assert (cam_node.getPos() - Vec3(10.0, -5.0, 3.7)).length() < 1e-4

        entity.stop()
        entity.remove_handler(handler)
        assert entity.get_handler(FirstPersonCameraHandler) is None
        assert handler.entity is None

        entity.free()
        self.p(
            "FirstPersonCameraHandler defaults, eye lock, and orientation verified successfully.",
            color="green",
        )
        self.space_line()

    def test_first_person_pitch_yaw_clamping_and_mouse_delta(self):
        self.print_subtitle("Testing first-person yaw/pitch clamping and mouse delta processing.")
        handler = FirstPersonCameraHandler(
            yaw=0.0,
            pitch=0.0,
            min_pitch=-89.0,
            max_pitch=89.0,
            mouse_sensitivity=0.2,
        )

        # Yaw normalized to [0, 360)
        handler.yaw = -90.0
        assert abs(handler.yaw - 270.0) < 1e-4
        handler.yaw = 450.0
        assert abs(handler.yaw - 90.0) < 1e-4

        # Pitch clamped by property setter
        handler.pitch = -120.0
        assert abs(handler.pitch - (-89.0)) < 1e-4
        handler.pitch = 120.0
        assert abs(handler.pitch - 89.0) < 1e-4

        # Mouse delta: dx=10 -> yaw -= 2.0, dy=20 -> pitch -= 4.0 (same as third person)
        handler.yaw = 100.0
        handler.pitch = 0.0
        handler.handle_mouse_delta(dx=10.0, dy=20.0)
        assert abs(handler.yaw - 98.0) < 1e-4, f"Expected 98.0, got {handler.yaw}"
        assert abs(handler.pitch - (-4.0)) < 1e-4, f"Expected -4.0, got {handler.pitch}"

        # Extreme deltas respect clamping
        handler.handle_mouse_delta(dx=0.0, dy=1000.0)
        assert abs(handler.pitch - (-89.0)) < 1e-4
        handler.handle_mouse_delta(dx=0.0, dy=-2000.0)
        assert abs(handler.pitch - 89.0) < 1e-4

        # Inverted pitch flips the vertical sign
        inverted = FirstPersonCameraHandler(invert_pitch=True, invert_yaw=True)
        inverted.handle_mouse_delta(dx=10.0, dy=20.0)
        assert abs(inverted.yaw - (0.0 + 2.0) % 360.0) < 1e-4, f"Expected 2.0, got {inverted.yaw}"
        assert abs(inverted.pitch - 4.0) < 1e-4, f"Expected 4.0, got {inverted.pitch}"

        self.p(
            "First-person yaw/pitch clamping and mouse delta verified successfully.",
            color="green",
        )
        self.space_line()

    def test_first_person_tracks_character_controller_nodepath(self):
        self.print_subtitle("Testing first-person eye tracking of CharacterControllerHandler controller_np.")
        entity = Entity("FirstPersonPhysicsHero")
        controller = CharacterControllerHandler()
        cam_handler = FirstPersonCameraHandler(eye_offset=Vec3(0.0, 0.0, 1.6))
        entity.add_handler(controller)
        entity.add_handler(cam_handler)
        entity.start()
        cam_handler.set_pointer_captured(False)

        assert controller.controller_np is not None
        controller.controller_np.setPos(12.0, -8.0, 3.0)

        eye_pos = cam_handler.get_target_pos()
        expected = Vec3(12.0, -8.0, 4.6)
        assert (eye_pos - expected).length() < 1e-4, f"Expected {expected}, got {eye_pos}"

        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        cam = cam_handler.camera
        assert (cam.getPos() - expected).length() < 1e-4, f"Expected {expected}, got {cam.getPos()}"

        entity.stop()
        entity.free()
        self.p(
            "First-person tracking of CharacterControllerHandler controller_np verified successfully.",
            color="green",
        )
        self.space_line()

    def test_first_person_headless_safety(self):
        self.print_subtitle("Testing first-person headless safety without graphical window.")
        entity = Entity("FirstPersonHeadlessHero")
        handler = FirstPersonCameraHandler()
        entity.add_handler(handler)

        entity.start()
        entity.update(0.016)
        entity.update(0.033)
        entity.update(0.1)

        fwd = handler.get_forward_vector()
        assert isinstance(fwd, Vec3)
        assert abs(fwd.length() - 1.0) < 1e-4

        cam = handler.camera
        assert cam is not None and not cam.isEmpty()

        entity.stop()
        entity.free()
        self.p("First-person headless safety verified successfully.", color="green")
        self.space_line()

    def test_third_person_collision_spring_arm(self):
        self.print_subtitle("Testing third-person camera boom collision (spring-arm).")
        from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode
        from panda3d.core import Point3, TransformState

        from src.globals.physics import Physics

        entity = Entity("SpringArmHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("spring_arm_camera")
        handler = ThirdPersonCameraHandler(
            distance=10.0,
            min_distance=1.0,
            max_distance=25.0,
            target_offset=Vec3(0.0, 0.0, 0.0),
            pitch=0.0,
            yaw=0.0,
            smooth_speed=0.0,
            camera=cam_node,
        )
        entity.add_handler(handler)

        world = Physics.get_world()
        body = BulletRigidBodyNode("spring_wall")
        body.setMass(0.0)
        shape = BulletBoxShape(Vec3(1.0, 1.0, 4.0))
        body.addShape(shape)
        body.setTransform(TransformState.makePos(Point3(0.0, -4.0, 0.0)))
        world.attachRigidBody(body)
        world.doPhysics(1e-6)

        entity.start()
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)

        ideal = handler.compute_ideal_position()
        ideal_distance = (ideal - handler.get_target_pos()).length()
        resolved = handler.resolve_collision_position(handler.get_target_pos(), ideal)
        resolved_distance = (resolved - handler.get_target_pos()).length()

        assert resolved_distance < ideal_distance, (
            f"Expected camera boom to shorten: ideal={ideal_distance}, resolved={resolved_distance}"
        )
        assert resolved_distance >= handler.min_distance - 1e-4

        assert (cam_node.getPos() - resolved).length() < 1e-3

        entity.stop()
        entity.free()
        world.removeRigidBody(body)
        self.p(
            "Third-person camera spring-arm collision verified successfully.",
            color="green",
        )
        self.space_line()

    def test_third_person_no_self_clipping(self):
        self.print_subtitle("Testing third-person camera does not clip into the owner entity.")
        entity = Entity("NoClipHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("no_clip_camera")
        handler = ThirdPersonCameraHandler(
            distance=1.0,
            min_distance=0.5,
            max_distance=25.0,
            target_offset=Vec3(0.0, 0.0, 0.0),
            pitch=0.0,
            yaw=0.0,
            smooth_speed=0.0,
            camera=cam_node,
            owner_min_distance=2.0,
        )
        entity.add_handler(handler)
        entity.start()
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)

        target_pos = handler.get_target_pos()
        resolved = handler.resolve_collision_position(target_pos, handler.compute_ideal_position())
        resolved_distance = (resolved - target_pos).length()

        assert resolved_distance >= handler.owner_min_distance - 1e-4, (
            f"Expected camera to be pushed out to at least {handler.owner_min_distance}, "
            f"got distance={resolved_distance}"
        )

        entity.stop()
        entity.free()
        self.p("Third-person camera no-self-clipping verified successfully.", color="green")
        self.space_line()

    def test_third_person_shoulder_offset(self):
        self.print_subtitle("Testing third-person camera over-the-shoulder offset.")
        entity = Entity("ShoulderHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("shoulder_camera")
        handler = ThirdPersonCameraHandler(
            distance=8.0,
            min_distance=2.0,
            max_distance=25.0,
            target_offset=Vec3(0.0, 0.0, 0.0),
            pitch=0.0,
            yaw=0.0,
            smooth_speed=0.0,
            camera=cam_node,
            shoulder_offset=Vec3(1.0, 0.0, 0.0),
        )
        entity.add_handler(handler)
        entity.start()
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)

        ideal = handler.compute_ideal_position()
        handler.get_target_pos()

        # With yaw=0, pitch=0, distance=8: ideal base = (0, -8, 0)
        # Shoulder offset rotated by yaw=0: (1.0, 0.0, 0.0)
        # Expected: (1.0, -8.0, 0.0)
        expected = Vec3(1.0, -8.0, 0.0)
        assert (ideal - expected).length() < 1e-4, f"Expected shoulder-offset ideal={expected}, got {ideal}"

        entity.stop()
        entity.free()
        self.p("Third-person camera shoulder offset verified successfully.", color="green")
        self.space_line()

    def test_first_person_no_wall_clipping(self):
        self.print_subtitle("Testing first-person camera does not clip into walls.")
        from panda3d.bullet import BulletRigidBodyNode
        from panda3d.core import Point3, TransformState

        from src.globals.physics import Physics

        entity = Entity("FPSHero")
        entity.node.setPos(0.0, 0.0, 0.0)
        cam_node = NodePath("fp_camera")
        handler = FirstPersonCameraHandler(
            eye_offset=Vec3(0.0, 0.0, 1.5),
            yaw=0.0,
            pitch=0.0,
            collision_enabled=True,
            collision_margin=0.15,
            camera=cam_node,
        )
        entity.add_handler(handler)
        entity.start()
        entity.update(0.016)

        # Colocar una pared justo delante del ojo del personaje
        world = Physics.get_world()
        body = BulletRigidBodyNode("fp_wall")
        body.setMass(0.0)
        from panda3d.bullet import BulletBoxShape

        shape = BulletBoxShape(Vec3(2.0, 0.2, 4.0))
        body.addShape(shape)
        body.setTransform(TransformState.makePos(Point3(0.0, 1.0, 0.0)))
        world.attachRigidBody(body)
        world.doPhysics(1e-6)

        eye_pos = handler.get_eye_pos()
        body_pos = handler.get_body_pos()
        (Vec3(0.0, 1.0, 0.0) - body_pos).length()

        # El ojo no debe quedar dentro o tras la pared (distancia cuerpo-ojomuy corta)
        # Si el ojo está a menos de collision_margin de la pared, se ajusta
        dist_body_eye = (eye_pos - body_pos).length()
        assert dist_body_eye < handler.eye_offset.length() + 1e-4, (
            f"Eye should be near body offset, got dist={dist_body_eye}"
        )

        # Verificar que el ojo no haya atravesado la pared (no debe estar tras el plano y=1.0)
        assert eye_pos.y < 1.0 - handler.collision_margin, (
            f"Eye clipped through wall: eye_pos.y={eye_pos.y}, wall at y=1.0, margin={handler.collision_margin}"
        )

        world.removeRigidBody(body)
        entity.stop()
        entity.free()
        self.p("First-person camera no-wall-clipping verified successfully.", color="green")
        self.space_line()

    # ------------------------------------------------------------------
    # First-person see-through protection (sphere sweep + real lens near plane)
    # ------------------------------------------------------------------
    def _make_static_box(self, name: str, pos: Vec3, half: Vec3, ghost: bool = False):
        """Attach a static box (or ghost trigger) to the physics world and return its node."""
        from panda3d.bullet import BulletBoxShape, BulletGhostNode, BulletRigidBodyNode
        from panda3d.core import TransformState

        from src.globals.physics import Physics

        node = BulletGhostNode(name) if ghost else BulletRigidBodyNode(name)
        if not ghost:
            node.setMass(0.0)
        node.addShape(BulletBoxShape(half))
        node.setTransform(TransformState.makePos(pos))
        if ghost:
            Physics.get_world().attachGhost(node)
        else:
            Physics.get_world().attachRigidBody(node)
        Physics.get_world().doPhysics(1e-6)
        return node

    def _remove_static_box(self, node) -> None:
        from panda3d.bullet import BulletGhostNode

        from src.globals.physics import Physics

        if isinstance(node, BulletGhostNode):
            Physics.get_world().removeGhost(node)
        else:
            Physics.get_world().removeRigidBody(node)

    def _make_fp_rig(self, name: str, fov: float = 90.0, **kwargs):
        """Create an entity with controller + FP handler driving a real Camera node with a 1.0 near plane."""
        from panda3d.core import Camera as CameraNode
        from panda3d.core import PerspectiveLens

        entity = Entity(name)
        controller = CharacterControllerHandler(radius=0.5, height=1.0)
        lens = PerspectiveLens()
        lens.setFov(fov)
        lens.setNearFar(1.0, 100000.0)  # Panda's default: the value that caused see-through walls
        cam_np = NodePath(CameraNode(f"{name}_cam"))
        cam_np.node().setLens(lens)
        handler = FirstPersonCameraHandler(eye_offset=Vec3(0.0, 0.0, 1.2), camera=cam_np, **kwargs)
        entity.add_handler(controller)
        entity.add_handler(handler)
        entity.start()
        handler.set_pointer_captured(False)
        return entity, controller, handler, cam_np, lens

    def _near_plane_corners(self, cam_np, lens) -> list[Vec3]:
        """Return the four near-plane corners in the camera's parent space."""
        from panda3d.core import Point2, Point3

        corners = []
        for x in (-1.0, 1.0):
            for y in (-1.0, 1.0):
                near_pt, far_pt = Point3(), Point3()
                assert lens.extrude(Point2(x, y), near_pt, far_pt)
                corners.append(Vec3(cam_np.getMat().xformPoint(near_pt)))
        return corners

    def test_first_person_pressed_against_wall_never_sees_through(self):
        self.print_subtitle("Testing FP camera cannot see through a wall it is pressed against.")
        wall = self._make_static_box("fp_press_wall", Vec3(0.0, 1.0, 0.0), Vec3(6.0, 0.2, 6.0))
        entity, controller, handler, cam_np, lens = self._make_fp_rig("FPPressHero")
        controller.controller_np.setPos(0.0, 0.3, 0.0)  # capsule surface touches the wall at y=0.8

        wall_surface = 0.8
        for yaw in (0.0, 45.0, 90.0, 180.0, 270.0, 315.0):
            for pitch in (-80.0, -30.0, 0.0, 30.0, 80.0):
                handler.yaw = yaw
                handler.pitch = pitch
                entity.update(0.016)
                if hasattr(entity, "update_post"):
                    entity.update_post(0.016)
                assert lens.getNear() < 1.0, "near plane was never applied to the real lens"
                for corner in self._near_plane_corners(cam_np, lens):
                    assert corner.y < wall_surface - 1e-3, (
                        f"Near plane crosses wall (yaw={yaw}, pitch={pitch}): corner.y={corner.y:.4f}"
                    )

        entity.stop()
        entity.free()
        self._remove_static_box(wall)
        self.p("FP camera pressed against a wall never sees through it.", color="green")
        self.space_line()

    def test_first_person_ceiling_and_corner_clearance(self):
        self.print_subtitle("Testing FP eye clearance below a low ceiling and around a pillar corner.")
        ceiling = self._make_static_box("fp_low_ceiling", Vec3(0.0, 0.0, 1.3), Vec3(4.0, 4.0, 0.2))  # underside z=1.1
        pillar = self._make_static_box("fp_corner_pillar", Vec3(1.0, 1.0, 0.0), Vec3(0.5, 0.5, 5.0))
        entity, controller, handler, cam_np, lens = self._make_fp_rig("FPCeilingHero")
        controller.controller_np.setPos(0.0, 0.0, 0.0)

        # Eye would sit at z=1.2 (inside the ceiling): it must be pulled below the underside.
        for pitch in (-60.0, 0.0, 60.0):
            handler.pitch = pitch
            handler.yaw = 0.0
            entity.update(0.016)
            if hasattr(entity, "update_post"):
                entity.update_post(0.016)
            for corner in self._near_plane_corners(cam_np, lens):
                assert corner.z < 1.1 - 1e-3, f"Near plane pokes through ceiling: z={corner.z:.4f}"
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        assert cam_np.getZ() < 1.1 - 1e-3, f"Eye inside ceiling: z={cam_np.getZ():.4f}"

        # Moving the body diagonally against the pillar corner must keep the near plane outside it.
        self._remove_static_box(ceiling)
        controller.controller_np.setPos(0.4, 0.4, 0.0)  # corner at (0.5, 0.5): capsule overlaps by design of the test
        controller.controller_np.setPos(0.1, 0.1, 0.0)
        for yaw in (0.0, 45.0, 90.0, 135.0, 225.0, 315.0):
            handler.yaw = yaw
            handler.pitch = 0.0
            entity.update(0.016)
            if hasattr(entity, "update_post"):
                entity.update_post(0.016)
            for corner in self._near_plane_corners(cam_np, lens):
                inside = 0.5 < corner.x < 1.5 and 0.5 < corner.y < 1.5
                assert not inside, f"Near plane corner inside pillar (yaw={yaw}): {corner}"

        entity.stop()
        entity.free()
        self._remove_static_box(pillar)
        self.p("FP ceiling and corner clearance verified successfully.", color="green")
        self.space_line()

    def test_first_person_ignores_own_capsule_and_triggers(self):
        self.print_subtitle("Testing FP collision ignores the player's capsule and trigger volumes.")
        from panda3d.bullet import BulletBoxShape

        from src.globals.physics import Physics
        from src.handlers.physics.trigger_zone import TriggerZoneHandler

        trigger_entity = Entity("FPTriggerZone")
        trigger_entity.node.setPos(0.0, 0.0, 1.0)
        trigger_entity.add_handler(TriggerZoneHandler(BulletBoxShape(Vec3(3.0, 3.0, 3.0))))
        trigger_entity.start()
        Physics.get_world().doPhysics(1e-6)
        entity, controller, handler, cam_np, lens = self._make_fp_rig("FPFreeHero")
        controller.controller_np.setPos(0.0, 0.0, 0.0)

        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        expected = Vec3(0.0, 0.0, 1.2)
        assert (cam_np.getPos() - expected).length() < 1e-4, (
            f"Eye should be free of own capsule and trigger, got {cam_np.getPos()}"
        )
        # In free space the requested near plane is only limited by the collision sphere.
        assert 0.0 < lens.getNear() <= handler.near_plane + 1e-6

        entity.stop()
        entity.free()
        trigger_entity.stop()
        trigger_entity.free()
        self.p("FP ignores own capsule and trigger volumes.", color="green")
        self.space_line()

    def test_first_person_oversized_margin_and_lens_restore(self):
        self.print_subtitle("Testing FP robustness with oversized margin and lens restoration on stop.")
        wall = self._make_static_box("fp_margin_wall", Vec3(0.0, 1.0, 0.0), Vec3(6.0, 0.2, 6.0))
        entity, controller, handler, cam_np, lens = self._make_fp_rig("FPMarginHero", collision_margin=5.0)
        controller.controller_np.setPos(0.0, 0.3, 0.0)

        handler.yaw = 0.0
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)
        eye = cam_np.getPos()
        assert eye.y < 0.8 - 1e-3, f"Oversized margin pushed the eye into the wall: {eye}"
        assert (eye - controller.controller_np.getPos()).length() > 0.5, "Eye collapsed into the body pivot"
        for corner in self._near_plane_corners(cam_np, lens):
            assert corner.y < 0.8 - 1e-3

        entity.stop()
        assert abs(lens.getNear() - 1.0) < 1e-6, f"Lens near not restored: {lens.getNear()}"
        assert abs(lens.getFar() - 100000.0) < 1e-3, f"Lens far not restored: {lens.getFar()}"

        entity.free()
        self._remove_static_box(wall)
        self.p("FP oversized margin handled and lens restored.", color="green")
        self.space_line()

    def test_first_person_smoothing_is_validated_against_geometry(self):
        self.print_subtitle("Testing FP position smoothing never lets the eye enter geometry.")
        wall = self._make_static_box("fp_smooth_wall", Vec3(0.0, 1.0, 0.0), Vec3(6.0, 0.2, 6.0))
        entity, controller, handler, cam_np, _lens = self._make_fp_rig("FPSmoothHero", smooth_factor=0.1)
        handler.yaw = 0.0
        controller.controller_np.setPos(0.0, -3.0, 0.0)
        entity.update(0.016)
        if hasattr(entity, "update_post"):
            entity.update_post(0.016)

        # Teleport-like fast approach: smoothed eye lags, but is always validated.
        for i in range(30):
            controller.controller_np.setPos(0.0, -3.0 + i * 0.12, 0.0)  # ends at y=0.48 (inside wall zone)
            entity.update(0.016)
            if hasattr(entity, "update_post"):
                entity.update_post(0.016)
            assert cam_np.getY() < 0.8 - 1e-3, f"Frame {i}: eye reached the wall, y={cam_np.getY():.4f}"

        entity.stop()
        entity.free()
        self._remove_static_box(wall)
        self.p("FP smoothing validated against geometry.", color="green")
        self.space_line()

    def test_third_person_camera_presets(self):
        self.print_subtitle("Testing ThirdPersonCameraHandler standard presets.")
        cam = NodePath("preset_cam")
        handler = ThirdPersonCameraHandler(camera=cam)

        # 1. Apply ADVENTURE
        handler.apply_preset(ADVENTURE_PRESET)
        assert abs(handler.distance - ADVENTURE_PRESET.distance) < 1e-4
        assert abs(handler.pitch - ADVENTURE_PRESET.pitch) < 1e-4
        assert handler.shoulder_offset == ADVENTURE_PRESET.shoulder_offset

        # 2. Apply SHOOTER by string
        handler.apply_preset("shooter")
        assert abs(handler.distance - SHOOTER_PRESET.distance) < 1e-4
        assert abs(handler.pitch - SHOOTER_PRESET.pitch) < 1e-4
        assert handler.shoulder_offset == SHOOTER_PRESET.shoulder_offset

        # 3. Apply ISOMETRIC by string
        handler.apply_preset("isometric")
        assert abs(handler.distance - ISOMETRIC_PRESET.distance) < 1e-4
        assert abs(handler.pitch - ISOMETRIC_PRESET.pitch) < 1e-4

        # 4. Apply OVERHEAD
        handler.apply_preset(OVERHEAD_PRESET)
        assert abs(handler.distance - OVERHEAD_PRESET.distance) < 1e-4
        assert abs(handler.pitch - OVERHEAD_PRESET.pitch) < 1e-4

        self.p("Third-person standard presets verified successfully.", color="green")
        self.space_line()

    def test_character_orientation_modes(self):
        self.print_subtitle("Testing CharacterOrientationMode MOVE_DIRECTION vs CAMERA_LOOK.")
        entity = Entity("OrientationHero")
        visual_node = entity.node.attachNewNode("visual")
        cam_node = NodePath("orientation_cam")

        input_handler = InputHandler()
        cam_handler = ThirdPersonCameraHandler(camera=cam_node, yaw=0.0)
        controller = CharacterControllerHandler(
            walk_speed=5.0,
            visual_node=visual_node,
            turn_speed=0.0,
            orientation_mode=CharacterOrientationMode.MOVE_DIRECTION,
        )

        entity.add_handler(input_handler)
        entity.add_handler(cam_handler)
        entity.add_handler(controller)
        entity.start()

        # Part 1: MOVE_DIRECTION
        # Moving Backward (S) -> linear velocity is (0, -5, 0), visual faces -Y (heading = 180 deg)
        input_handler.set_move_vector(0.0, -1.0)
        entity.update(0.016)
        assert abs((visual_node.getH() % 360.0) - 180.0) < 1e-4

        # When stopped, character keeps facing 180 deg even if camera yaw changes
        input_handler.set_move_vector(0.0, 0.0)
        cam_handler.yaw = 90.0
        entity.update(0.016)
        assert abs((visual_node.getH() % 360.0) - 180.0) < 1e-4

        # Part 2: CAMERA_LOOK
        controller.orientation_mode = CharacterOrientationMode.CAMERA_LOOK
        # Camera yaw = 90 -> camera looks along -X -> heading in Panda3D must be 90 deg
        cam_handler.yaw = 90.0
        entity.update(0.016)
        assert abs((visual_node.getH() % 360.0) - 90.0) < 1e-4

        # Camera yaw = 0 -> camera looks along +Y -> heading in Panda3D must be 0 deg
        cam_handler.yaw = 0.0
        entity.update(0.016)
        assert abs((visual_node.getH() % 360.0) - 0.0) < 1e-4

        # Backwards compatibility check
        assert controller.body_follows_camera_yaw is True
        controller.body_follows_camera_yaw = False
        assert controller.orientation_mode == CharacterOrientationMode.MOVE_DIRECTION

        entity.stop()
        entity.free()
        self.p(
            "Orientation modes and backwards compatibility verified successfully.",
            color="green",
        )
        self.space_line()

    def on_stop(self):
        self.print_subtitle("TestCameraHandler completed.")


if __name__ == "__main__":
    test = TestCameraHandler()
    test.on_start()
    test.on_stop()
