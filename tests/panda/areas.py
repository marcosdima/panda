from panda3d.bullet import BulletBoxShape
from panda3d.core import Vec3

from ..__test import Test
from src.globals import GlobalLoader, Physics, Tasks, GlobalClock, Camera
from src.entities import Area, Solid


class TestAreas(Test):
    def on_start(self):
        self.print_title('TestAreas started.', color='cyan')

        super().on_start()
        
        Camera.set_pos(0, -100, 60)
        Camera.look_at(0, 150, 0)
        self._create_area_test()


    def _create_area_test(self):
        """Two areas at x=-50 and x=50; one solid moves back and forth on X axis."""
        base = Physics.get_instance().base

        self.areas = [
            self._create_area('Area-Left', pos=(-50, 150, 0), color=(0.2, 0.6, 1.0, 0.2), target_groups={'Default'}),
            self._create_area('Area-Right', pos=(50, 150, 0), color=(1.0, 0.5, 0.2, 0.2)),
        ]

        self.solid = Solid(mass=0.0)
        self.solid.set_collision_group(self.solid.CollisionGroup.ENEMY)
        self.solid.add_box_shape(name='solid_shape', size=Vec3(1, 1, 1))
        self.solid.setup()
        solid_body = self.solid.body

        self.solid_np = base.render.attachNewNode(solid_body)
        self.solid_np.setPos(-50, 150, 0)

        self.solid_body = solid_body

        self.direction = 1
        self.speed = 15.0  # units per second along X axis
        self.min_x = -50.0
        self.max_x = 50.0

        Tasks.add_task('area_solid_mover', self._move_solid)

        self.p('Areas ready at x=-50 and x=50. Solid starts at x=-50 and moves along X axis.', color='yellow')


    def _create_area(
        self,
        name: str,
        pos: tuple[float, float, float],
        color: tuple[float, float, float, float],
        target_groups: set = set()
    ):
        base = Physics.get_instance().base
        area = Area()
        area.add_box_shape(name='box_shape', size=Vec3(5, 5, 5))
        area.setup()
        
        # Set target groups if provided.
        if target_groups:
            area.target_groups = target_groups
        
        # Connect overlap events.
        area.on_begin_overlap.add_callback(lambda e: self.p(f'Entered {name} ({e.get_name()})', color='cyan'))
        area.on_overlap.add_callback(lambda e: self.p(f'Overlapping {name} ({e.get_name()})', color='blue'))
        area.on_end_overlap.add_callback(lambda e: self.p(f'Exited {name} ({e.get_name()})', color='magenta'))
        area.on_rejected.add_callback(lambda e: self.p(f'Rejected {name} ({e.get_name()})', color='red'))
        
        ghost = area.ghost

        area_np = base.render.attachNewNode(ghost)
        area_np.setPos(*pos)

        self.p(f'{name} created at {area_np.getPos()}', color='green')
        return {
            'name': name,
            'area': area,
            'ghost': ghost,
            'np': area_np,
        }


    def _move_solid(self, task):
        dt = GlobalClock.get_dt()
        x = self.solid_np.getX() + self.direction * self.speed * dt

        if x >= self.max_x:
            x = self.max_x
            self.direction = -1
        elif x <= self.min_x:
            x = self.min_x
            self.direction = 1

        self.solid_np.setX(x)
        return task.cont


    def on_stop(self):
        self.print_subtitle('TestAreas stopped.')
        Tasks.remove_task('area_solid_mover')

        # Clean up models and nodes.
        if hasattr(self, 'solid_np'):
            self.solid_np.removeNode()
        if hasattr(self, 'solid_body'):
            Physics.remove_body(self.solid_body)

        for area in getattr(self, 'areas', []):
            area['np'].removeNode()
            Physics.remove_ghost(area['ghost'])
            Tasks.remove_task(f'area_overlap_checker_{area["area"].id}')
