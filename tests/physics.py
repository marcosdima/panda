from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3

from .__test import Test
from src.globals import GlobalLoader, Physics, Tasks, GlobalClock


class TestPhysics(Test):
    def on_start(self):
        self.print_title('TestPhysics started.', color='cyan')
        base = Physics.get_instance().base

        super().on_start()

        # Create a cube model
        cube_model = GlobalLoader.load_panda_asset('models/box')
        cube_model.setScale(10, 10, 10)
        
        # Create a physics body
        body = Physics.create_body('test_cube', mass=10.0)
        
        # Add a box shape to the body
        shape = BulletBoxShape(Vec3(5, 5, 5))  # Half extents for 10x10x10 cube
        body.addShape(shape)
        
        # Create a node path and attach the body
        body_np = base.render.attachNewNode(body)
        body_np.setPos(0, 100, 10)
        
        # Attach the visual model to the physics body
        cube_model.reparentTo(body_np)
        
        # Store references
        self.cube_model = cube_model
        self.body_np = body_np
        self.body = body

        self.p(f'Cube created at position: {body_np.getPos()}', color='green')
        self.p(f'Mass: {body.getMass()}', color='green')
        self.p('Physics simulation active - cube will fall', color='yellow')


    def on_stop(self):
        self.print_subtitle('TestPhysics stopped.')