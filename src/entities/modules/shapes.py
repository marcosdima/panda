from panda3d.bullet import (
    BulletShape, BulletBoxShape, BulletSphereShape, 
    BulletCylinderShape, BulletCapsuleShape, BulletPlaneShape
)
from panda3d.core import Vec3
from .__module import Module


class Shapes(Module):
    ''' Module for managing bullet physics shapes. '''

    def __init__(self) -> None:
        super().__init__()
        self.__shapes: dict[str, BulletShape] = {}


    def free(self) -> None:
        '''Frees the shapes module and clears all shapes.'''
        self.__shapes.clear()
        super().free()


    def add_box_shape(self, name: str, size: Vec3) -> BulletBoxShape:
        '''Add a box shape.'''
        if name in self.__shapes:
            raise ValueError(f'Shape "{name}" already exists')
        shape = BulletBoxShape(size)
        self.__shapes[name] = shape
        return shape


    def add_sphere_shape(self, name: str, radius: float) -> BulletSphereShape:
        '''Add a sphere shape.'''
        if name in self.__shapes:
            raise ValueError(f'Shape "{name}" already exists')
        shape = BulletSphereShape(radius)
        self.__shapes[name] = shape
        return shape


    def add_cylinder_shape(self, name: str, radius: float, height: float, axis: str = 'z') -> BulletCylinderShape:
        '''Add a cylinder shape.'''
        if name in self.__shapes:
            raise ValueError(f'Shape "{name}" already exists')
        shape = BulletCylinderShape(radius, height, axis)
        self.__shapes[name] = shape
        return shape


    def add_capsule_shape(self, name: str, radius: float, height: float, axis: str = 'z') -> BulletCapsuleShape:
        '''Add a capsule shape.'''
        if name in self.__shapes:
            raise ValueError(f'Shape "{name}" already exists')
        shape = BulletCapsuleShape(radius, height, axis)
        self.__shapes[name] = shape
        return shape


    def add_plane_shape(self, name: str, normal: Vec3, d: float = 0.0) -> BulletPlaneShape:
        '''Add a plane shape.'''
        if name in self.__shapes:
            raise ValueError(f'Shape "{name}" already exists')
        shape = BulletPlaneShape(normal, d)
        self.__shapes[name] = shape
        return shape


    def get_shape(self, name: str) -> BulletShape | None:
        '''Get a shape by name.'''
        return self.__shapes.get(name)
    

    def get_shapes(self) -> dict[str, BulletShape]:
        '''Get all shapes as a dictionary.'''
        return self.__shapes.copy()
    

    def remove_shape(self, name: str) -> bool:
        '''Remove a shape by name. Returns True if removed, False if not found.'''
        if name in self.__shapes:
            del self.__shapes[name]
            return True
        return False
    

    def has_shape(self, name: str) -> bool:
        '''Check if a shape exists.'''
        return name in self.__shapes
