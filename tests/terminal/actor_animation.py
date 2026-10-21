try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

import builtins
import math
from panda3d.core import Vec3

from src.entities.entity import Entity
from src.handlers.graphics.actor import ActorAnimationHandler
from src.handlers.input.base import InputHandler
from src.handlers.physics.character import CharacterControllerHandler


class TestActorAnimation(TerminalTest):
    """Terminal test suite for ActorAnimationHandler and drift-free visual pivot integration."""

    def on_start(self) -> None:
        self.print_title("TestActorAnimation started.", color="cyan")
        super().on_start()

    def test_actor_animation_handler_initialization(self) -> None:
        self.print_subtitle("Testing ActorAnimationHandler default & custom parameters.")
        handler = ActorAnimationHandler()

        assert handler.model_path == "X Bot.glb"
        assert handler.animations == {"Idle": "anims/X Bot@Idle.glb"}
        assert handler.scale == 100.0
        assert handler.offset == Vec3(0.0, 0.0, -1.0)
        assert handler.hpr == Vec3(0.0, 0.0, 0.0)
        assert handler.visual_pivot is None
        assert handler.model_root is None
        assert handler.current_animation is None

        # Custom configuration
        custom_handler = ActorAnimationHandler(
            model_path="X Bot.glb",
            animations={"CustomIdle": "anims/X Bot@Idle.glb"},
            scale=50.0,
            offset=Vec3(0.0, 0.0, -0.5),
            hpr=Vec3(180.0, 90.0, 0.0),
        )
        assert custom_handler.scale == 50.0
        assert custom_handler.offset == Vec3(0.0, 0.0, -0.5)
        assert custom_handler.hpr == Vec3(180.0, 90.0, 0.0)
        assert custom_handler.animations == {"CustomIdle": "anims/X Bot@Idle.glb"}

        self.p("ActorAnimationHandler parameters verified successfully.", color="green")
        self.space_line()

    def test_actor_attachment_and_visual_pivot_standalone(self) -> None:
        self.print_subtitle("Testing ActorAnimationHandler standalone entity attachment.")
        entity = Entity("StandaloneActorHero")
        handler = ActorAnimationHandler()
        entity.add_handler(handler)

        # Visual pivot must be created at (0, 0, 0) attached to entity.node
        assert handler.visual_pivot is not None
        assert not handler.visual_pivot.isEmpty()
        assert handler.visual_pivot.getParent() == entity.node
        assert handler.visual_pivot.getPos() == Vec3(0.0, 0.0, 0.0)

        # Model root must be created, child of visual_pivot, and properly transformed
        assert handler.model_root is not None
        assert not handler.model_root.isEmpty()
        assert handler.model_root.getParent() == handler.visual_pivot
        assert handler.model_root.getScale() == Vec3(100.0, 100.0, 100.0)
        assert handler.model_root.getPos() == Vec3(0.0, 0.0, -1.0)
        assert handler.model_root.getHpr() == Vec3(0.0, 0.0, 0.0)

        # Start entity -> should loop Idle animation
        entity.start()
        assert handler.current_animation == "Idle"

        # Update tick
        entity.update(0.016)
        assert handler.current_animation == "Idle"

        # Teardown
        entity.stop()
        assert handler.model_root is None
        assert handler.visual_pivot is None
        assert handler.current_animation is None

        entity.free()
        assert entity.is_freed
        self.p("Standalone actor attachment & transform verified successfully.", color="green")
        self.space_line()

    def test_actor_attachment_with_character_controller_and_pivot_drift(self) -> None:
        self.print_subtitle("Testing drift-free visual pivot with CharacterControllerHandler.")
        entity = Entity("PhysicsActorHero")
        controller = CharacterControllerHandler()
        anim_handler = ActorAnimationHandler()

        entity.add_handler(controller)
        entity.add_handler(anim_handler)

        # Visual pivot must be attached to controller.controller_np at (0, 0, 0)
        assert anim_handler.visual_pivot is not None
        assert controller.controller_np is not None
        assert anim_handler.visual_pivot.getParent() == controller.controller_np
        assert anim_handler.visual_pivot.getPos() == Vec3(0.0, 0.0, 0.0)

        # CharacterControllerHandler visual_node must be bound to visual_pivot
        assert controller.visual_node == anim_handler.visual_pivot

        # Verify pivot drift fix:
        # Rotating controller.visual_node must NOT alter its position from (0, 0, 0)!
        controller.visual_node.setH(45.0)
        pos_after_rot = controller.visual_node.getPos()
        assert pos_after_rot == Vec3(0.0, 0.0, 0.0), f"Pivot drifted! Got {pos_after_rot}"

        controller.visual_node.setH(180.0)
        pos_after_180 = controller.visual_node.getPos()
        assert pos_after_180 == Vec3(0.0, 0.0, 0.0), f"Pivot drifted! Got {pos_after_180}"

        controller.visual_node.setH(270.0)
        pos_after_270 = controller.visual_node.getPos()
        assert pos_after_270 == Vec3(0.0, 0.0, 0.0), f"Pivot drifted! Got {pos_after_270}"

        # Clean teardown
        entity.stop()
        entity.free()
        self.p("Drift-free visual pivot verified successfully.", color="green")
        self.space_line()

    def test_actor_rotation_under_controller_movement(self) -> None:
        self.print_subtitle("Testing visual pivot rotation driven by CharacterControllerHandler.")
        entity = Entity("MovingActorHero")
        input_handler = InputHandler()
        controller = CharacterControllerHandler(turn_speed=12.0)
        anim_handler = ActorAnimationHandler()

        entity.add_handler(input_handler)
        entity.add_handler(controller)
        entity.add_handler(anim_handler)
        entity.start()

        # Simulate movement with a mock camera handler providing forward vector
        class MockCameraHandler:
            def get_forward_vector(self) -> Vec3:
                return Vec3(0.0, 1.0, 0.0)

        controller.camera_handler = MockCameraHandler()

        # Strafe right (move_vector.x = 1.0) -> controller should rotate visual_node towards +X (heading ~ -90)
        input_handler.set_move_vector(1.0, 0.0)
        for _ in range(15):
            entity.update(0.033)

        # Check that visual_node rotated towards movement direction
        curr_h = controller.visual_node.getH()
        expected_target_h = -math.degrees(math.atan2(1.0, 0.0))  # -90 deg
        assert abs((curr_h - expected_target_h + 180.0) % 360.0 - 180.0) < 5.0, (
            f"Expected heading near {expected_target_h}, got {curr_h}"
        )

        # Position of visual_pivot MUST remain strictly at (0, 0, 0)
        pivot_pos = anim_handler.visual_pivot.getPos()
        assert pivot_pos == Vec3(0.0, 0.0, 0.0), f"Pivot drifted after rotation! Pos: {pivot_pos}"

        entity.stop()
        entity.free()
        self.p("Visual pivot rotation without drift verified successfully.", color="green")
        self.space_line()

    def test_animation_playback_and_locomotion_states(self) -> None:
        self.print_subtitle("Testing animation playback and locomotion synchronization.")
        entity = Entity("LocomotionHero")
        input_handler = InputHandler()
        controller = CharacterControllerHandler(walk_speed=5.0, sprint_speed=10.0)
        anim_handler = ActorAnimationHandler(
            model_path="X Bot.glb",
            animations={"Idle": "anims/X Bot@Idle.glb"},
        )

        entity.add_handler(input_handler)
        entity.add_handler(controller)
        entity.add_handler(anim_handler)
        entity.start()

        # 1. Idle state on start
        assert anim_handler.current_animation == "Idle"

        # 2. Moving state
        input_handler.set_move_vector(0.0, 1.0)
        entity.update(0.016)
        # With only "Idle" available in X Bot anim set, handler gracefully maintains "Idle"
        assert anim_handler.current_animation == "Idle"

        # 3. Stop movement -> maintains Idle
        input_handler.set_move_vector(0.0, 0.0)
        entity.update(0.016)
        assert anim_handler.current_animation == "Idle"

        # 4. Explicit animation control methods
        assert anim_handler.loop_animation("Idle")
        assert anim_handler.current_animation == "Idle"
        assert not anim_handler.play_animation("NonExistentClip")

        anim_handler.stop_animation()
        assert anim_handler.current_animation is None

        # Next update tick when stopped restores Idle loop
        entity.update(0.016)
        assert anim_handler.current_animation == "Idle"

        entity.stop()
        entity.free()
        self.p("Animation locomotion state management verified successfully.", color="green")
        self.space_line()

    def test_clean_lifecycle_and_memory_leak_prevention(self) -> None:
        self.print_subtitle("Testing clean lifecycle, restart symmetry, and leak prevention.")
        entity = Entity("LifecycleActorHero")
        controller = CharacterControllerHandler()
        anim_handler = ActorAnimationHandler()

        entity.add_handler(controller)
        entity.add_handler(anim_handler)

        assert anim_handler.visual_pivot is not None
        assert anim_handler.model_root is not None
        pivot_np = anim_handler.visual_pivot

        # Start entity
        entity.start()
        assert anim_handler.current_animation == "Idle"

        # Stop entity -> model cleaned up, nodes removed
        entity.stop()
        assert anim_handler.model_root is None
        assert anim_handler.visual_pivot is None
        assert pivot_np.isEmpty()
        assert controller.visual_node is None

        # Restart entity -> cleanly restores visual pivot and model
        entity.start()
        assert anim_handler.visual_pivot is not None
        assert not anim_handler.visual_pivot.isEmpty()
        assert anim_handler.model_root is not None
        assert not anim_handler.model_root.isEmpty()
        assert anim_handler.current_animation == "Idle"
        assert controller.visual_node == anim_handler.visual_pivot

        # Detach handler cleanly
        entity.remove_handler(anim_handler)
        assert anim_handler.model_root is None
        assert anim_handler.visual_pivot is None
        assert controller.visual_node is None

        # Free entity
        entity.stop()
        entity.free()
        assert entity.is_freed

        self.p("Lifecycle symmetry and leak prevention verified successfully.", color="green")
        self.space_line()

    def test_kaykit_multi_clip_files_and_state_mapping(self) -> None:
        self.print_subtitle("Testing KayKit multi-clip glTF loading and locomotion state mapping.")
        entity = Entity("KayKitHero")
        input_handler = InputHandler()
        controller = CharacterControllerHandler(walk_speed=5.0, sprint_speed=10.0)
        handler = ActorAnimationHandler.kaykit_rig_medium("Knight", air_threshold=0.0)
        entity.add_handler(input_handler)
        entity.add_handler(controller)
        entity.add_handler(handler)

        names = handler.get_anim_names()
        for clip in ("Idle_A", "Walking_A", "Running_A", "Jump_Idle", "Interact", "PickUp"):
            assert clip in names, f"Missing clip {clip}: {names}"
        assert len(names) == len(set(names)), f"Duplicate clip bindings: {names}"
        assert not any(".1" in n for n in names), f"Clips bound more than once: {names}"

        entity.start()
        assert handler.current_animation == "Idle_A"

        # Walk, then sprint (grounded state is forced by a huge air threshold)
        handler.air_threshold = 1e9
        input_handler.set_move_vector(0.0, 1.0)
        entity.update(0.016)
        assert handler.current_animation == "Walking_A", handler.current_animation
        input_handler.set_action_state("sprint", True)
        entity.update(0.016)
        assert handler.current_animation == "Running_A", handler.current_animation
        input_handler.set_action_state("sprint", False)
        input_handler.set_move_vector(0.0, 0.0)
        for _ in range(60):
            entity.update(0.016)
        assert handler.current_animation == "Idle_A", handler.current_animation

        # Airborne: Jump clip once the controller has been off the ground past threshold
        handler.air_threshold = 0.05
        controller.controller_node.isOnGround = lambda: False
        # Small dt below threshold: should still be Idle_A
        entity.update(0.02)
        assert handler.current_animation == "Idle_A", handler.current_animation
        # Accumulate air time past threshold: switches to Jump_Idle
        entity.update(0.04)
        assert handler.current_animation == "Jump_Idle", handler.current_animation
        # Landing: controller is on ground again
        controller.controller_node.isOnGround = lambda: True
        entity.update(0.016)
        assert handler.current_animation == "Idle_A", handler.current_animation

        entity.stop()
        entity.free()
        self.p("KayKit multi-clip loading and state mapping verified successfully.", color="green")
        self.space_line()

    def on_stop(self) -> None:
        self.print_subtitle("TestActorAnimation completed.")


if __name__ == "__main__":
    from direct.showbase.ShowBase import ShowBase

    # Bootstrap a headless ShowBase for Loader support when running standalone.
    if not hasattr(builtins, "base") or builtins.base is None:
        ShowBase(windowType="none")

    test = TestActorAnimation()
    test.on_start()
    test.on_stop()
