from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3

from src.globals import GlobalLoader, Physics

from ..__test import Test


class TestPhysics(Test):
    def on_start(self) -> None:
        self.print_title("TestPhysics started.", color="cyan")

        super().on_start()
        self.physics_debug = True

        # Test collision between two bodies
        self._create_collision_test()

    def _create_collision_test(self) -> None:
        """Create two boxes: static (mass=0) and dynamic (mass=10) for collision test."""
        base = Physics.get_instance().base

        # Create static base box (mass = 0)
        base_body = Physics.create_body("static_base", mass=0.0)
        base_shape = BulletBoxShape(Vec3(7.5, 1, 7.5))
        base_body.addShape(base_shape)

        base_np = base.render.attachNewNode(base_body)
        base_np.setPos(0, 0, 0)

        # Instance the cached model so both bodies can share its geometry.
        cached_box = GlobalLoader.load_panda_asset("box")
        base_model = base_np.attachNewNode(cached_box.node())
        base_model.setScale(15, 2, 15)

        self.p("Static base created (mass=0)", color="cyan")
        self.p(f"Base position: {base_np.getPos()}", color="green")

        # Create dynamic falling box (mass = 10)
        falling_body = Physics.create_body("falling_cube", mass=10.0)
        falling_shape = BulletBoxShape(Vec3(4, 4, 4))
        falling_body.addShape(falling_shape)

        falling_np = base.render.attachNewNode(falling_body)
        falling_np.setPos(0, 0, 40)

        falling_model = falling_np.attachNewNode(cached_box.node())
        falling_model.setScale(8, 8, 8)

        self.p("Dynamic falling cube created (mass=10)", color="cyan")
        self.p(f"Falling cube start position: {falling_np.getPos()}", color="green")
        self.p("Collision test: cube will fall and collide with base", color="yellow")

        # Store references
        self.base_np = base_np
        self.falling_np = falling_np

    def on_stop(self) -> None:
        self.print_subtitle("TestPhysics stopped.")
        Physics.remove_body("static_base")
        Physics.remove_body("falling_cube")

        # Remove body NodePaths; the cached model geometry is shared and stays untouched.
        for np_name in ("base_np", "falling_np"):
            node_path = getattr(self, np_name, None)
            if node_path is not None and not node_path.isEmpty():
                node_path.removeNode()


if __name__ == "__main__":
    from src import game

    app = game.Game()
    sandbox = TestPhysics()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
