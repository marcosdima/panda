from panda3d.bullet import BulletWorld, BulletRigidBodyNode, BulletGhostNode
from panda3d.core import Vec3


from .__global import Global
from .clock import GlobalClock


class Physics(Global):
    ''' A singleton class to manage the Bullet Physics world. '''
    _world: BulletWorld = None
    _bodies = {}
    _ghosts = {}


    def __init__(self) -> None:
        super().__init__()
        if Physics._world is None:
            Physics._world = BulletWorld()
            Physics._world.setGravity(Vec3(0, 0, -9.81))
            self.base.task_mgr.add(self._update_world, "physics_world_updater")


    def _update_world(self, task):
        dt = GlobalClock.get_dt()
        Physics._world.doPhysics(dt)
        return task.cont


    @classmethod
    def get_world(cls) -> BulletWorld:
        '''Get the Bullet Physics world.'''
        return cls._world


    @classmethod
    def create_body(cls, name: str, mass: float = 1.0) -> BulletRigidBodyNode:
        '''Create a rigid body, add it to the world, and return it.'''
        node = BulletRigidBodyNode(name)
        node.setMass(mass)
        cls._world.attachRigidBody(node)
        cls._bodies[name] = node
        return node


    @classmethod
    def create_ghost(cls, name: str) -> BulletGhostNode:
        '''Create a ghost body, add it to the world, and return it.'''
        node = BulletGhostNode(name)
        cls._world.attachGhost(node)
        cls._ghosts[name] = node
        return node


    @classmethod
    def remove_body(cls, name_or_node: BulletRigidBodyNode | str):
        '''Remove a rigid body from the world by name or node reference.'''
        if isinstance(name_or_node, str):
            if name_or_node in cls._bodies:
                cls._world.removeRigidBody(cls._bodies[name_or_node])
                del cls._bodies[name_or_node]
        else:
            cls._world.removeRigidBody(name_or_node)


    @classmethod
    def remove_ghost(cls, name_or_node: BulletGhostNode | str):
        '''Remove a ghost body from the world by name or node reference.'''
        if isinstance(name_or_node, str):
            if name_or_node in cls._ghosts:
                cls._world.removeGhost(cls._ghosts[name_or_node])
                del cls._ghosts[name_or_node]
        else:
            cls._world.removeGhost(name_or_node)
