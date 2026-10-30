try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

import builtins

from panda3d.bullet import BulletCapsuleShape, BulletCharacterControllerNode
from panda3d.core import KeyboardButton, Vec2, Vec3

from src.entities.entity import Entity
from src.globals.physics import Physics
from src.handlers.input import InputHandler, WASDInputHandler
from src.handlers.physics import CharacterControllerHandler


class TestCharacterController(TerminalTest):
    """Terminal test suite for Input and Character Controller subsystems."""

    def on_start(self):
        self.print_title("TestCharacterController started.", color="cyan")
        super().on_start()

    def test_wasd_input_handler_headless(self):
        self.print_subtitle("Testing WASDInputHandler in headless mode.")
        entity = Entity("HeadlessHero")
        wasd = WASDInputHandler()
        entity.add_handler(wasd)

        # Initial move vector must be zero
        assert wasd.move_vector == Vec2(0.0, 0.0), f"Expected (0, 0), got {wasd.move_vector}"
        assert not wasd.is_action_down("jump")
        assert not wasd.is_action_pressed("jump")
        assert not wasd.is_action_down("sprint")
        assert not wasd.is_action_pressed("sprint")

        # Headless updates must not raise any exceptions
        entity.start()
        entity.update(0.016)
        entity.update(0.033)

        assert wasd.move_vector == Vec2(0.0, 0.0)
        assert not wasd.is_action_down("jump")

        entity.stop()
        entity.free()
        self.p("WASDInputHandler headless mode verified successfully.", color="green")
        self.space_line()

    def test_input_handler_action_edge_detection(self):
        self.print_subtitle("Testing InputHandler action edge-detection and movement vector.")
        entity = Entity("InputHero")
        input_handler = InputHandler()
        entity.add_handler(input_handler)
        entity.start()

        # Test movement vector normalization
        input_handler.set_move_vector(1.0, 1.0)
        assert abs(input_handler.move_vector.length() - 1.0) < 1e-4, "Diagonal movement must be normalized"

        # Frame 1: Action just pressed and processed in frame 1 tick
        input_handler.set_action_state("jump", True)
        entity.update(0.016)
        assert input_handler.is_action_down("jump"), "jump must be down"
        assert input_handler.is_action_pressed("jump"), "jump must be pressed on initial frame"
        assert not input_handler.is_action_released("jump"), "jump must not be released"

        # Frame 2: Action held down on subsequent tick
        entity.update(0.016)
        assert input_handler.is_action_down("jump"), "jump must remain down"
        assert not input_handler.is_action_pressed("jump"), "jump must NOT be pressed on subsequent frame"
        assert not input_handler.is_action_released("jump"), "jump must not be released"

        # Frame 3: Action released
        input_handler.set_action_state("jump", False)
        assert not input_handler.is_action_down("jump"), "jump must not be down"
        assert input_handler.is_action_released("jump"), "jump must be released"

        # Frame 4: Next frame after release
        entity.update(0.016)
        assert not input_handler.is_action_down("jump")
        assert not input_handler.is_action_pressed("jump")
        assert not input_handler.is_action_released("jump")

        entity.stop()
        entity.free()
        self.p("InputHandler edge-detection verified successfully.", color="green")
        self.space_line()

    def test_wasd_mock_polling(self):
        self.print_subtitle("Testing WASDInputHandler hardware polling via mock MouseWatcher.")
        entity = Entity("MockPolledHero")
        wasd = WASDInputHandler()
        entity.add_handler(wasd)

        # Mock mouseWatcherNode
        class MockMouseWatcher:
            def __init__(self, held_keys):
                self.held_keys = set(held_keys)

            def is_button_down(self, btn):
                return btn in self.held_keys

        class MockBase:
            def __init__(self, watcher):
                self.mouseWatcherNode = watcher

            def destroy(self):
                pass

        btn_w = KeyboardButton.ascii_key("w")
        btn_d = KeyboardButton.ascii_key("d")
        btn_shift = KeyboardButton.lshift()
        btn_space = KeyboardButton.space()

        original_base = getattr(builtins, "base", None)
        try:
            builtins.base = MockBase(MockMouseWatcher([btn_w, btn_d, btn_shift, btn_space]))
            entity.start()
            entity.update(0.016)

            # W + D should produce normalized diagonal vector
            expected_x = 0.70710678
            expected_y = 0.70710678
            assert abs(wasd.move_vector.x - expected_x) < 1e-3, f"Expected {expected_x}, got {wasd.move_vector.x}"
            assert abs(wasd.move_vector.y - expected_y) < 1e-3, f"Expected {expected_y}, got {wasd.move_vector.y}"
            assert wasd.is_action_down("sprint"), "sprint action must be active"
            assert wasd.is_action_down("jump"), "jump action must be active"
            assert wasd.is_action_pressed("jump"), "jump action must be pressed on initial tick"

            # Tick 2: Keys still held
            entity.update(0.016)
            assert wasd.is_action_down("jump")
            assert not wasd.is_action_pressed("jump")
        finally:
            if original_base is not None:
                builtins.base = original_base
            else:
                delattr(builtins, "base")
            entity.stop()
            entity.free()

        self.p("WASDInputHandler mock polling verified successfully.", color="green")
        self.space_line()

    def test_character_controller_parameters_and_shape(self):
        self.print_subtitle("Testing CharacterControllerHandler parameters and capsule shape.")
        controller = CharacterControllerHandler(
            radius=0.6,
            height=1.2,
            step_height=0.35,
            walk_speed=6.0,
            sprint_speed=12.0,
            jump_speed=8.0,
            gravity=18.0,
        )

        assert controller.radius == 0.6
        assert controller.height == 1.2
        assert controller.step_height == 0.35
        assert controller.walk_speed == 6.0
        assert controller.sprint_speed == 12.0
        assert controller.jump_speed == 8.0
        assert controller.gravity == 18.0

        assert isinstance(controller.shape, BulletCapsuleShape)
        assert abs(controller.shape.getRadius() - 0.6) < 1e-4
        assert abs(controller.shape.getHalfHeight() - 0.6) < 1e-4

        self.p(
            "CharacterControllerHandler configuration verified successfully.",
            color="green",
        )
        self.space_line()

    def test_character_controller_attachment_and_world(self):
        self.print_subtitle("Testing CharacterControllerHandler attachment to entity and BulletWorld.")
        entity = Entity("CharacterAlpha")
        controller = CharacterControllerHandler()
        entity.add_handler(controller)

        # Node and NodePath creation
        assert controller.controller_node is not None
        assert isinstance(controller.controller_node, BulletCharacterControllerNode)
        assert controller.controller_node.getName() == "CharacterAlpha"
        assert controller.controller_np is not None
        assert not controller.controller_np.isEmpty()
        assert controller.controller_np.getParent() == entity.node

        # Verification of BulletWorld attachment
        world = Physics.get_world()
        assert controller.controller_node in world.getCharacters()

        entity.start()
        assert controller.controller_node in world.getCharacters()

        entity.stop()
        entity.free()
        self.p(
            "CharacterControllerHandler entity and world attachment verified successfully.",
            color="green",
        )
        self.space_line()

    def test_character_controller_linear_movement_walk_and_sprint(self):
        self.print_subtitle("Testing linear movement scaling for walk and sprint states.")
        entity = Entity("RunnerHero")
        input_handler = InputHandler()
        controller = CharacterControllerHandler(walk_speed=5.0, sprint_speed=10.0)

        entity.add_handler(input_handler)
        entity.add_handler(controller)
        entity.start()

        # 1. Idle state
        entity.update(0.016)
        assert controller.linear_velocity == Vec3(0.0, 0.0, 0.0)
        assert not controller.is_sprinting
        assert controller.current_speed == 5.0

        # 2. Walk forward: move_vector = (0, 1)
        input_handler.set_move_vector(0.0, 1.0)
        entity.update(0.016)
        assert controller.linear_velocity == Vec3(0.0, 5.0, 0.0), f"Got {controller.linear_velocity}"
        assert not controller.is_sprinting
        assert controller.current_speed == 5.0

        # 3. Sprint forward: move_vector = (0, 1), sprint active
        input_handler.set_action_state("sprint", True)
        entity.update(0.016)
        assert controller.linear_velocity == Vec3(0.0, 10.0, 0.0), f"Got {controller.linear_velocity}"
        assert controller.is_sprinting
        assert controller.current_speed == 10.0

        # 4. Walk strafe left: move_vector = (-1, 0), sprint inactive
        input_handler.set_action_state("sprint", False)
        input_handler.set_move_vector(-1.0, 0.0)
        entity.update(0.016)
        assert controller.linear_velocity == Vec3(-5.0, 0.0, 0.0)

        entity.stop()
        entity.free()
        self.p(
            "CharacterControllerHandler walk and sprint scaling verified successfully.",
            color="green",
        )
        self.space_line()

    def test_character_controller_acceleration_damping(self):
        self.print_subtitle("Testing CharacterControllerHandler acceleration and deceleration damping.")
        entity = Entity("DampedHero")
        input_handler = InputHandler()
        controller = CharacterControllerHandler(
            walk_speed=6.0,
            sprint_speed=12.0,
            acceleration=25.0,
            deceleration=30.0,
        )
        entity.add_handler(input_handler)
        entity.add_handler(controller)
        entity.start()

        # Initial velocity is zero
        assert controller.linear_velocity == Vec3(0.0, 0.0, 0.0)

        # 1. Apply forward movement: move_vector = (0, 1)
        input_handler.set_move_vector(0.0, 1.0)
        dt = 0.016
        entity.update(dt)

        # With acceleration=25.0, step = dt * 25.0 = 0.4
        # Velocity should blend smoothly: 0 + (6.0 - 0) * 0.4 = 2.4
        vel = controller.linear_velocity
        assert 0.0 < vel.y < 6.0, f"Expected smooth acceleration, got {vel.y}"
        assert abs(vel.x) < 1e-4

        # Second tick: continues accelerating towards 6.0
        entity.update(dt)
        vel2 = controller.linear_velocity
        assert vel2.y > vel.y, f"Expected speed to increase from {vel.y}, got {vel2.y}"

        # Run several ticks until reaching target speed
        for _ in range(20):
            entity.update(dt)
        assert abs(controller.linear_velocity.y - 6.0) < 1e-3, f"Expected 6.0, got {controller.linear_velocity.y}"

        # 2. Release input: move_vector = (0, 0) -> decelerates smoothly to 0
        input_handler.set_move_vector(0.0, 0.0)
        entity.update(dt)
        vel_dec = controller.linear_velocity
        assert 0.0 < vel_dec.y < 6.0, f"Expected smooth deceleration, got {vel_dec.y}"

        for _ in range(20):
            entity.update(dt)
        assert controller.linear_velocity == Vec3(0.0, 0.0, 0.0), (
            f"Expected full stop, got {controller.linear_velocity}"
        )

        entity.stop()
        entity.free()
        self.p(
            "CharacterControllerHandler acceleration and deceleration damping verified successfully.",
            color="green",
        )
        self.space_line()

    def test_character_controller_jump(self):
        self.print_subtitle("Testing CharacterControllerHandler jump invocation.")
        entity = Entity("JumpingHero")
        input_handler = InputHandler()
        controller = CharacterControllerHandler()

        entity.add_handler(input_handler)
        entity.add_handler(controller)
        entity.start()

        assert controller.is_on_ground, "Controller must be grounded initially"
        assert controller.can_jump, "Controller must be able to jump"

        # Trigger jump via input handler
        input_handler.set_action_state("jump", True)
        entity.update(0.016)

        # After jumping, canJump becomes False until landing
        assert not controller.can_jump, "Controller must consume jump state"

        # Calling controller.jump() while in air should return False
        assert not controller.jump(), "Jump in mid-air should not execute"

        entity.stop()
        entity.free()
        self.p("CharacterControllerHandler jump verified successfully.", color="green")
        self.space_line()

    def test_character_controller_clean_lifecycle_and_detach(self):
        self.print_subtitle("Testing clean detachment, stop/start symmetry, and memory leak prevention.")
        world = Physics.get_world()

        entity = Entity("LifecycleHero")
        controller = CharacterControllerHandler()
        entity.add_handler(controller)

        char_node = controller.controller_node
        assert char_node in world.getCharacters()

        # Stop scene/entity -> character controller must be cleanly removed from BulletWorld
        entity.start()
        entity.stop()
        assert char_node not in world.getCharacters(), "Controller must be removed from world on stop"
        assert controller.controller_np is None, "NodePath must be cleaned up on stop"

        # Re-start entity -> character controller must cleanly re-attach
        entity.start()
        assert char_node in world.getCharacters(), "Controller must re-attach to world on restart"
        assert controller.controller_np is not None
        assert not controller.controller_np.isEmpty()

        # Remove handler -> cleanly detached
        entity.remove_handler(controller)
        assert char_node not in world.getCharacters(), "Controller must be removed from world on detach"
        assert controller.controller_np is None
        assert controller.controller_node is None

        # Free entity
        entity.free()
        assert entity.is_freed
        assert entity.node.isEmpty()

        self.p(
            "CharacterControllerHandler lifecycle and leak prevention verified successfully.",
            color="green",
        )
        self.space_line()

    def on_stop(self):
        self.print_subtitle("TestCharacterController completed.")


if __name__ == "__main__":
    test = TestCharacterController()
    test.on_start()
    test.on_stop()
