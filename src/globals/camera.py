from panda3d.core import NodePath, Vec3
from .__global import Global


class Camera(Global):
    ''' A singleton class to manage the global camera. '''
    
    @classmethod
    def get_camera(cls) -> NodePath:
        '''Get the camera NodePath.'''
        return cls._instance.base.camera
    
    
    @classmethod
    def set_pos(cls, x: float, y: float, z: float):
        '''Set the camera position.'''
        cls.get_camera().setPos(x, y, z)
    
    
    @classmethod
    def set_pos_vec(cls, pos: Vec3):
        '''Set the camera position using a Vec3.'''
        cls.get_camera().setPos(pos)
    
    
    @classmethod
    def get_pos(cls) -> Vec3:
        '''Get the camera position.'''
        return cls.get_camera().getPos()
    
    
    @classmethod
    def look_at(cls, x: float, y: float, z: float):
        '''Make the camera look at a point.'''
        cls.get_camera().lookAt(x, y, z)
    
    
    @classmethod
    def look_at_vec(cls, pos: Vec3):
        '''Make the camera look at a point using a Vec3.'''
        cls.get_camera().lookAt(pos)
    
    
    @classmethod
    def look_at_node(cls, node: NodePath):
        '''Make the camera look at a NodePath.'''
        cls.get_camera().lookAt(node)
    
    
    @classmethod
    def set_hpr(cls, h: float, p: float, r: float):
        '''Set the camera heading, pitch, and roll.'''
        cls.get_camera().setHpr(h, p, r)
    
    
    @classmethod
    def get_hpr(cls) -> Vec3:
        '''Get the camera heading, pitch, and roll.'''
        return cls.get_camera().getHpr()
