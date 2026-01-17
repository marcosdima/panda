from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3

from ..__test import Test
from src.globals import GlobalLoader, Physics, Tasks, GlobalClock


class TestPhysics(Test):
    def on_start(self):
        self.print_title('TestPhysics started.', color='cyan')
        base = Physics.get_instance().base

        super().on_start()

        # Test collision between two bodies
        self._create_collision_test()


    def _create_box_setup(self) -> tuple:
        '''Create a single falling box.'''
        base = Physics.get_instance().base
        
        # Create a cube model
        cube_model = GlobalLoader.load_panda_asset('box')
        cube_model.setScale(10, 10, 10)
        
        # Create a physics body
        body = Physics.create_body('test_cube', mass=10.0)
        
        # Add a box shape to the body
        shape = BulletBoxShape(Vec3(5, 5, 5))  # Half extents for 10x10x10 cube
        body.addShape(shape)
        
        # Create a node path and attach the body
        body_np = base.render.attachNewNode(body)
        body_np.setPos(0, 100, 50)
        
        # Attach the visual model to the physics body
        cube_model.reparentTo(body_np)
        
        self.p(f'Cube created at position: {body_np.getPos()}', color='green')
        self.p(f'Mass: {body.getMass()}', color='green')
        
        return cube_model, body_np, body


    def _create_collision_test(self):
        '''Create two boxes: static (mass=0) and dynamic (mass=10) for collision test.'''
        base = Physics.get_instance().base
        
        # Create static base box (mass = 0)
        base_model = GlobalLoader.load_panda_asset('box')
        base_model.setScale(15, 2, 15)
        
        base_body = Physics.create_body('static_base', mass=0.0)
        base_shape = BulletBoxShape(Vec3(7.5, 1, 7.5))
        base_body.addShape(base_shape)
        
        base_np = base.render.attachNewNode(base_body)
        base_np.setPos(0, 0, 0)
        base_model.reparentTo(base_np)
        
        self.p('Static base created (mass=0)', color='cyan')
        self.p(f'Base position: {base_np.getPos()}', color='green')
        
        # Create dynamic falling box (mass = 10)
        falling_model = GlobalLoader.load_panda_asset('box')
        falling_model.setScale(8, 8, 8)
        
        falling_body = Physics.create_body('falling_cube', mass=10.0)
        falling_shape = BulletBoxShape(Vec3(4, 4, 4))
        falling_body.addShape(falling_shape)
        
        falling_np = base.render.attachNewNode(falling_body)
        falling_np.setPos(0, 0, 40)
        falling_model.reparentTo(falling_np)
        
        self.p('Dynamic falling cube created (mass=10)', color='cyan')
        self.p(f'Falling cube start position: {falling_np.getPos()}', color='green')
        self.p('Collision test: cube will fall and collide with base', color='yellow')
        
        # Store references
        self.base_model = base_model
        self.base_np = base_np
        self.falling_model = falling_model
        self.falling_np = falling_np


    def on_stop(self):
        self.print_subtitle('TestPhysics stopped.')
        Physics.remove_body('static_base')
        Physics.remove_body('falling_cube')