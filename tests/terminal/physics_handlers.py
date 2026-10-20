try:
    from .__terminal import TerminalTest
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from tests.terminal.__terminal import TerminalTest

from panda3d.bullet import BulletBoxShape
from panda3d.core import NodePath, Vec3

from src.entities.entity import Entity
from src.globals.physics import Physics
from src.handlers.physics import (
    CharacterControllerHandler,
    CollisionGroup,
    RigidBodyHandler,
    TriggerZoneHandler,
)


DT = 1.0 / 60.0


class TestPhysicsHandlers(TerminalTest):
    """Terminal test suite for RigidBodyHandler and TriggerZoneHandler subsystems."""

    def on_start(self):
        self.print_title("TestPhysicsHandlers started.", color="cyan")
        super().on_start()

    def test_rigid_body_configuration_and_lifecycle(self) -> None:
        self.print_subtitle("Testing RigidBodyHandler configuration and world lifecycle.")
        world = Physics.get_world()

        entity = Entity("RigidConfig")
        handler = RigidBodyHandler(
            shape=BulletBoxShape(Vec3(1.0, 1.0, 1.0)),
            mass=1.0,
            collision_group=CollisionGroup.PLAYER,
        )
        entity.add_handler(handler)

        assert handler.is_dynamic, "mass > 0 must yield a dynamic body"
        assert handler.collision_group == CollisionGroup.PLAYER
        assert handler.body_node is not None
        assert handler.body_np is not None
        assert handler.body_np.getParent() == entity.node, "Body must hang under the entity node"
        assert handler.body_node.hasPythonTag("entity"), "Body must be tagged for trigger resolution"
        assert handler.body_node in world.getRigidBodies(), "Body must be attached to the Bullet world"

        entity.start()
        assert handler.body_node in world.getRigidBodies()

        entity.stop()
        assert handler.body_node not in world.getRigidBodies(), "Body must leave the world on stop"
        assert handler.body_np is None, "NodePath must be cleaned up on stop"

        entity.start()
        assert handler.body_node in world.getRigidBodies(), "Body must re-attach on restart"
        assert handler.body_np is not None
        assert not handler.body_np.isEmpty()

        entity.remove_handler(handler)
        assert handler.body_node not in world.getRigidBodies()
        assert handler.body_np is None
        assert handler.body_node is None, "Handler must release the body node on detach"

        entity.free()
        assert entity.is_freed
        assert entity.node.isEmpty()

        static_entity = Entity("RigidStaticConfig")
        static_handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(1.0, 1.0, 1.0)), mass=0.0)
        static_entity.add_handler(static_handler)
        assert not static_handler.is_dynamic, "mass == 0 must yield a static body"
        assert static_handler.body_node in world.getRigidBodies()
        static_entity.stop()
        static_entity.free()

        self.p("RigidBodyHandler configuration and lifecycle verified successfully.", color="green")
        self.space_line()

    def test_rigid_body_position_sync_with_entity_node(self) -> None:
        self.print_subtitle("Testing body position sync driven by entity.node transforms.")
        world = Physics.get_world()

        entity = Entity("RigidSync")
        entity.node.setPos(5.0, 2.0, 1.0)
        handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=0.0)
        entity.add_handler(handler)
        entity.start()

        world.doPhysics(DT)
        pos = handler.body_np.getNetTransform().getPos()
        assert (pos - Vec3(5.0, 2.0, 1.0)).length() < 1e-4, f"Spawn transform must be adopted, got {pos}"

        entity.node.setPos(10.0, -3.0, 4.0)
        entity.update(DT)
        world.doPhysics(DT)
        pos = handler.body_np.getNetTransform().getPos()
        assert (pos - Vec3(10.0, -3.0, 4.0)).length() < 1e-4, f"Entity move must propagate to Bullet, got {pos}"

        entity.stop()
        entity.free()
        self.p("RigidBodyHandler entity-node position sync verified successfully.", color="green")
        self.space_line()

    def test_rigid_body_static_stability(self) -> None:
        self.print_subtitle("Testing static body stability under gravity over time.")
        world = Physics.get_world()

        entity = Entity("RigidStaticStable")
        handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(1.0, 1.0, 1.0)), mass=0.0)
        entity.add_handler(handler)
        entity.start()

        for _ in range(60):
            entity.update(DT)
            world.doPhysics(DT)

        pos = handler.body_np.getNetTransform().getPos()
        assert pos.length() < 1e-4, f"Static body must not drift, got {pos}"
        assert handler.linear_velocity.length() < 1e-6

        entity.stop()
        entity.free()
        self.p("RigidBodyHandler static stability verified successfully.", color="green")
        self.space_line()

    def test_rigid_body_dynamic_gravity_simulation(self) -> None:
        self.print_subtitle("Testing dynamic body free fall under world gravity.")
        world = Physics.get_world()

        entity = Entity("RigidDropper")
        handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0)
        entity.add_handler(handler)
        entity.start()

        for _ in range(60):
            entity.update(DT)
            world.doPhysics(DT)

        pos = handler.body_np.getNetTransform().getPos()
        velocity = handler.linear_velocity
        assert -6.0 < pos.z < -4.0, f"Expected ~-4.9m free fall after 1s, got {pos.z}"
        assert velocity.z < -9.0, f"Expected ~-9.81 m/s after 1s, got {velocity.z}"
        assert abs(pos.x) < 1e-3 and abs(pos.y) < 1e-3, f"Fall must stay vertical, got {pos}"

        entity.stop()
        entity.free()
        self.p("RigidBodyHandler dynamic gravity simulation verified successfully.", color="green")
        self.space_line()

    def test_rigid_body_impulse_force_and_velocity(self) -> None:
        self.print_subtitle("Testing impulse, force, and linear velocity APIs.")
        world = Physics.get_world()

        entity = Entity("RigidImpulse")
        handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=1.0)
        entity.add_handler(handler)
        entity.start()

        assert handler.linear_velocity.length() < 1e-6, "Body must start at rest"

        handler.apply_impulse(Vec3(0.0, 10.0, 0.0))
        world.doPhysics(DT)
        velocity = handler.linear_velocity
        assert velocity.y > 5.0, f"Central impulse must raise Y velocity, got {velocity.y}"

        handler.apply_force(Vec3(5.0, 0.0, 0.0))
        world.doPhysics(DT)
        velocity_after_force = handler.linear_velocity
        assert velocity_after_force.x > 0.03, f"Central force must accelerate on X, got {velocity_after_force.x}"

        handler.linear_velocity = Vec3(3.0, 0.0, 0.0)
        velocity_set = handler.linear_velocity
        assert abs(velocity_set.x - 3.0) < 1e-5 and abs(velocity_set.y) < 1e-5 and abs(velocity_set.z) < 1e-5

        world.doPhysics(DT)
        velocity_final = handler.linear_velocity
        assert abs(velocity_final.x - 3.0) < 0.01, f"Expected ~3 m/s on X, got {velocity_final.x}"
        assert abs(velocity_final.y) < 0.01, f"Expected 0 m/s on Y, got {velocity_final.y}"
        assert -0.3 < velocity_final.z < -0.05, f"Gravity must tick Z velocity, got {velocity_final.z}"

        entity.stop()
        entity.free()
        self.p("RigidBodyHandler impulse, force, and velocity verified successfully.", color="green")
        self.space_line()

    def test_rigid_body_shape_added_after_attach(self) -> None:
        self.print_subtitle("Testing add_shape after world attach via resting contact.")
        world = Physics.get_world()

        static_entity = Entity("RigidLateShapeStatic")
        static_handler = RigidBodyHandler(mass=0.0)
        static_entity.add_handler(static_handler)
        static_handler.add_shape(BulletBoxShape(Vec3(2.0, 2.0, 0.5)))
        static_entity.start()

        dynamic_entity = Entity("RigidLateShapeDynamic")
        dynamic_entity.node.setPos(0.0, 0.0, 5.0)
        dynamic_handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.25, 0.25, 0.25)), mass=1.0)
        dynamic_entity.add_handler(dynamic_handler)
        dynamic_entity.start()

        for _ in range(120):
            dynamic_entity.update(DT)
            world.doPhysics(DT)

        pos = dynamic_handler.body_np.getNetTransform().getPos()
        assert 0.6 < pos.z < 0.9, f"Dynamic box must rest on the static top (~0.75), got {pos.z}"
        assert abs(dynamic_handler.linear_velocity.z) < 0.5, "Body must have settled"

        static_entity.stop()
        static_entity.free()
        dynamic_entity.stop()
        dynamic_entity.free()
        self.p("RigidBodyHandler late add_shape contact verified successfully.", color="green")
        self.space_line()

    def test_trigger_detects_character_controller(self) -> None:
        self.print_subtitle("Testing trigger detection of a CharacterControllerHandler entity.")
        world = Physics.get_world()

        zone_entity = Entity("TriggerCharZone")
        zone_handler = TriggerZoneHandler(
            shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)),
            target_groups={CollisionGroup.PLAYER},
        )
        zone_entity.add_handler(zone_handler)
        enter_log: list[str] = []
        zone_handler.on_enter.add_callback(lambda e: enter_log.append(e.name))

        character_entity = Entity("TriggerCharBody")
        character_handler = CharacterControllerHandler(
            radius=0.5,
            height=1.0,
            collision_group=CollisionGroup.PLAYER,
        )
        character_entity.add_handler(character_handler)

        zone_entity.start()
        character_entity.start()

        world.doPhysics(DT)
        zone_entity.update(DT)

        assert enter_log == [character_entity.name], f"Got {enter_log}"
        assert zone_handler.is_overlapping(character_entity), "Character must be tracked as overlapping"
        assert character_handler.controller_node in world.getCharacters()

        zone_entity.stop()
        zone_entity.free()
        character_entity.stop()
        character_entity.free()
        self.p("TriggerZoneHandler character detection verified successfully.", color="green")
        self.space_line()

    def test_trigger_enter_stay_exit_sequence(self) -> None:
        self.print_subtitle("Testing trigger enter/stay/exit edge event sequence.")
        world = Physics.get_world()

        zone_entity = Entity("TriggerSeqZone")
        zone_handler = TriggerZoneHandler(shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)))
        zone_entity.add_handler(zone_handler)

        body_entity = Entity("TriggerSeqBody")
        body_handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=0.0)
        body_entity.add_handler(body_handler)

        log: list[str] = []
        zone_handler.on_enter.add_callback(lambda e: log.append(f"enter:{e.name}"))
        zone_handler.on_stay.add_callback(lambda e: log.append(f"stay:{e.name}"))
        zone_handler.on_exit.add_callback(lambda e: log.append(f"exit:{e.name}"))

        zone_entity.start()
        body_entity.start()

        world.doPhysics(DT)
        zone_entity.update(DT)
        expected_name = body_entity.name
        assert log == [f"enter:{expected_name}", f"stay:{expected_name}"], f"Frame 1 must fire enter+stay, got {log}"
        assert zone_handler.is_overlapping(body_entity)

        world.doPhysics(DT)
        zone_entity.update(DT)
        assert log == [
            f"enter:{expected_name}",
            f"stay:{expected_name}",
            f"stay:{expected_name}",
        ], f"Frame 2 must fire stay only, got {log}"

        body_handler.body_np.setPos(0.0, 0.0, 20.0)
        world.doPhysics(DT)
        zone_entity.update(DT)
        assert log[-1] == f"exit:{expected_name}", f"Frame 3 must fire exit, got {log}"
        assert not zone_handler.is_overlapping(body_entity)
        assert zone_handler.overlapping_entities == []

        zone_entity.stop()
        zone_entity.free()
        body_entity.stop()
        body_entity.free()
        self.p("TriggerZoneHandler enter/stay/exit sequence verified successfully.", color="green")
        self.space_line()

    def test_trigger_group_filters(self) -> None:
        self.print_subtitle("Testing trigger target_groups and avoid_groups filtering.")
        world = Physics.get_world()

        target_zone_entity = Entity("TriggerTargetZone")
        target_zone_handler = TriggerZoneHandler(
            shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)),
            target_groups={CollisionGroup.ENEMY},
        )
        target_zone_entity.add_handler(target_zone_handler)
        enter_log: list[str] = []
        rejected_log: list[str] = []
        target_zone_handler.on_enter.add_callback(lambda e: enter_log.append(e.name))
        target_zone_handler.on_rejected.add_callback(lambda e: rejected_log.append(e.name))

        player_entity = Entity("FilterPlayer")
        player_handler = RigidBodyHandler(
            shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
            mass=0.0,
            collision_group=CollisionGroup.PLAYER,
        )
        player_entity.add_handler(player_handler)

        enemy_entity = Entity("FilterEnemy")
        enemy_handler = RigidBodyHandler(
            shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
            mass=0.0,
            collision_group=CollisionGroup.ENEMY,
        )
        enemy_entity.add_handler(enemy_handler)

        target_zone_entity.start()
        player_entity.start()
        enemy_entity.start()

        world.doPhysics(DT)
        target_zone_entity.update(DT)

        assert enter_log == [enemy_entity.name], f"Only ENEMY must enter, got {enter_log}"
        assert rejected_log == [player_entity.name], f"PLAYER must be rejected, got {rejected_log}"
        assert target_zone_handler.is_overlapping(enemy_entity)
        assert not target_zone_handler.is_overlapping(player_entity)
        assert target_zone_handler.overlapping_entities == [enemy_entity]

        avoid_zone_entity = Entity("TriggerAvoidZone")
        avoid_zone_handler = TriggerZoneHandler(
            shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)),
            avoid_groups={CollisionGroup.ENEMY},
        )
        avoid_zone_entity.add_handler(avoid_zone_handler)
        avoid_enter_log: list[str] = []
        avoid_rejected_log: list[str] = []
        avoid_zone_handler.on_enter.add_callback(lambda e: avoid_enter_log.append(e.name))
        avoid_zone_handler.on_rejected.add_callback(lambda e: avoid_rejected_log.append(e.name))
        avoid_zone_entity.start()

        world.doPhysics(DT)
        avoid_zone_entity.update(DT)

        assert avoid_enter_log == [player_entity.name], f"PLAYER must pass avoid filter, got {avoid_enter_log}"
        assert avoid_rejected_log == [enemy_entity.name], f"ENEMY must be avoided, got {avoid_rejected_log}"

        target_zone_entity.stop()
        target_zone_entity.free()
        avoid_zone_entity.stop()
        avoid_zone_entity.free()
        player_entity.stop()
        player_entity.free()
        enemy_entity.stop()
        enemy_entity.free()
        self.p("TriggerZoneHandler group filters verified successfully.", color="green")
        self.space_line()

    def test_trigger_selective_zone_skips_default_environment(self) -> None:
        self.print_subtitle("Testing selective triggers ignore ambient DEFAULT environment overlaps.")
        world = Physics.get_world()

        zone_entity = Entity("TriggerAmbientZone")
        zone_handler = TriggerZoneHandler(
            shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)),
            target_groups={CollisionGroup.ENEMY},
        )
        zone_entity.add_handler(zone_handler)

        env_entity = Entity("TriggerAmbientGround")
        env_entity.add_handler(RigidBodyHandler(shape=BulletBoxShape(Vec3(4.0, 4.0, 0.25)), mass=0.0))
        env_entity.node.setPos(0.0, 0.0, -2.25)

        enemy_entity = Entity("TriggerAmbientEnemy")
        enemy_entity.add_handler(
            RigidBodyHandler(
                shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)),
                mass=0.0,
                collision_group=CollisionGroup.ENEMY,
            )
        )

        enter_log: list[str] = []
        rejected_log: list[str] = []
        zone_handler.on_enter.add_callback(lambda e: enter_log.append(e.name))
        zone_handler.on_rejected.add_callback(lambda e: rejected_log.append(e.name))

        zone_entity.start()
        env_entity.start()
        enemy_entity.start()

        world.doPhysics(DT)
        zone_entity.update(DT)

        assert enter_log == [enemy_entity.name], f"Only ENEMY must enter, got {enter_log}"
        assert rejected_log == [], f"Ambient DEFAULT environment must be ignored, got {rejected_log}"
        assert zone_handler.overlapping_entities == [enemy_entity]

        env_entity.node.setPos(0.0, 0.0, 0.0)
        world.doPhysics(DT)
        zone_entity.update(DT)

        assert rejected_log == [], f"Covering DEFAULT ground must not emit rejects, got {rejected_log}"
        assert enter_log == [enemy_entity.name], f"DEFAULT ground must not enter, got {enter_log}"

        zone_entity.stop()
        zone_entity.free()
        env_entity.stop()
        env_entity.free()
        enemy_entity.stop()
        enemy_entity.free()
        self.p("Selective triggers ignore ambient DEFAULT environment verified successfully.", color="green")
        self.space_line()

    def test_trigger_ignores_untagged_and_sibling_triggers(self) -> None:
        self.print_subtitle("Testing trigger blindness to untagged bodies and sibling triggers.")
        world = Physics.get_world()

        zone_entity = Entity("TriggerIgnoreZone")
        zone_handler = TriggerZoneHandler(shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)))
        zone_entity.add_handler(zone_handler)
        events: list[str] = []
        zone_handler.on_enter.add_callback(lambda e: events.append(e.name))
        zone_handler.on_rejected.add_callback(lambda e: events.append(f"rej:{e.name}"))

        env_node = Physics.create_body("trigger_env_box", mass=0.0)
        env_node.addShape(BulletBoxShape(Vec3(1.0, 1.0, 1.0)))
        env_np = NodePath(env_node)
        env_np.setPos(0.5, 0.0, 0.0)

        sibling_entity = Entity("TriggerSiblingZone")
        sibling_handler = TriggerZoneHandler(shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)))
        sibling_entity.add_handler(sibling_handler)

        zone_entity.start()
        sibling_entity.start()
        world.doPhysics(DT)
        zone_entity.update(DT)

        assert events == [], f"Untagged bodies and sibling triggers must be ignored, got {events}"
        assert zone_handler.overlapping_entities == []

        control_entity = Entity("TriggerIgnoreControl")
        control_handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.5, 0.5, 0.5)), mass=0.0)
        control_entity.add_handler(control_handler)
        control_entity.start()

        world.doPhysics(DT)
        zone_entity.update(DT)

        assert events == [control_entity.name], f"Tagged handler body must be detected, got {events}"
        assert zone_handler.is_overlapping(control_entity)

        control_entity.stop()
        control_entity.free()
        sibling_entity.stop()
        sibling_entity.free()
        zone_entity.stop()
        zone_entity.free()
        env_np.removeNode()
        Physics.remove_body("trigger_env_box")
        self.p("TriggerZoneHandler node filtering verified successfully.", color="green")
        self.space_line()

    def test_trigger_lifecycle(self) -> None:
        self.print_subtitle("Testing TriggerZoneHandler world lifecycle and leak prevention.")
        world = Physics.get_world()

        entity = Entity("TriggerLifecycle")
        handler = TriggerZoneHandler(shape=BulletBoxShape(Vec3(1.0, 1.0, 1.0)))
        entity.add_handler(handler)

        ghost_node = handler.ghost_node
        assert ghost_node is not None
        assert ghost_node in world.getGhosts()
        assert handler.ghost_np is not None
        assert handler.ghost_np.getParent() == entity.node
        assert not ghost_node.getCollisionResponse(), "Trigger ghosts must not push bodies"

        entity.start()
        assert ghost_node in world.getGhosts()

        entity.stop()
        assert ghost_node not in world.getGhosts(), "Ghost must leave the world on stop"
        assert handler.ghost_np is None, "Ghost NodePath must be cleaned up on stop"

        entity.start()
        assert ghost_node in world.getGhosts(), "Ghost must re-attach on restart"
        assert handler.ghost_np is not None
        assert not handler.ghost_np.isEmpty()

        entity.remove_handler(handler)
        assert ghost_node not in world.getGhosts()
        assert handler.ghost_np is None
        assert handler.ghost_node is None, "Handler must release the ghost node on detach"

        entity.free()
        assert entity.is_freed
        assert entity.node.isEmpty()

        self.p("TriggerZoneHandler lifecycle and leak prevention verified successfully.", color="green")
        self.space_line()

    def test_trigger_pass_through_dynamic_body(self) -> None:
        self.print_subtitle("Testing collision-response-free pass through of dynamic bodies.")
        world = Physics.get_world()

        zone_entity = Entity("TriggerPassZone")
        zone_handler = TriggerZoneHandler(shape=BulletBoxShape(Vec3(2.0, 2.0, 2.0)))
        zone_entity.add_handler(zone_handler)
        enter_hits: list[str] = []
        exit_hits: list[str] = []
        zone_handler.on_enter.add_callback(lambda e: enter_hits.append(e.name))
        zone_handler.on_exit.add_callback(lambda e: exit_hits.append(e.name))

        fall_entity = Entity("TriggerPassBody")
        fall_entity.node.setPos(0.0, 0.0, 6.0)
        fall_handler = RigidBodyHandler(shape=BulletBoxShape(Vec3(0.3, 0.3, 0.3)), mass=1.0)
        fall_entity.add_handler(fall_handler)

        zone_entity.start()
        fall_entity.start()

        completed = False
        for _ in range(150):
            fall_entity.update(DT)
            world.doPhysics(DT)
            zone_entity.update(DT)
            if enter_hits and exit_hits:
                completed = True
                break

        assert completed, f"Body must fully traverse the zone, got enters={enter_hits} exits={exit_hits}"
        assert enter_hits == [fall_entity.name], f"Expected exactly one enter, got {enter_hits}"
        assert exit_hits == [fall_entity.name], f"Expected exactly one exit, got {exit_hits}"
        assert not zone_handler.is_overlapping(fall_entity)

        final_z = fall_handler.body_np.getNetTransform().getPos().z
        assert final_z < -2.3, f"Body must fall through unimpeded, got z={final_z}"
        assert fall_handler.linear_velocity.z < -1.0, "Body must keep accelerating downward"

        zone_entity.stop()
        zone_entity.free()
        fall_entity.stop()
        fall_entity.free()
        self.p("TriggerZoneHandler pass-through verified successfully.", color="green")
        self.space_line()

    def on_stop(self):
        self.print_subtitle("TestPhysicsHandlers completed.")


if __name__ == "__main__":
    test = TestPhysicsHandlers()
    test.on_start()
    test.on_stop()
