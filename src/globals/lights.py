from panda3d.core import AmbientLight, DirectionalLight, Vec3, NodePath
from .__global import Global


class GlobalLights(Global):
    ''' A singleton class to manage global lighting. '''
    
    @classmethod
    def setup_default_lights(cls):
        '''Setup default lighting for the scene.'''
        base = cls._instance.base
        render = base.render
        
        # Remove default lights if they exist
        render.clearLight()
        
        # Ambient light (overall brightness)
        ambient_light = AmbientLight("ambient_light")
        ambient_light.setColor((0.6, 0.6, 0.6, 1))
        ambient_node = render.attachNewNode(ambient_light)
        render.setLight(ambient_node)
        
        # Directional light (main light source)
        directional_light = DirectionalLight("directional_light")
        directional_light.setColor((1, 1, 1, 1))
        directional_light.setShadowCaster(True, 2048, 2048)
        directional_node = render.attachNewNode(directional_light)
        directional_node.setPos(50, 50, 100)
        directional_node.lookAt(0, 0, 0)
        render.setLight(directional_node)
    
    
    @classmethod
    def add_ambient_light(cls, color: tuple = (0.5, 0.5, 0.5, 1)) -> NodePath:
        '''Add an ambient light to the scene.'''
        base = cls._instance.base
        render = base.render
        
        ambient_light = AmbientLight("ambient_light")
        ambient_light.setColor(color)
        ambient_node = render.attachNewNode(ambient_light)
        render.setLight(ambient_node)
        
        return ambient_node
    
    
    @classmethod
    def add_directional_light(
        cls,
        pos: tuple = (0, 0, 0),
        direction: tuple = (0, 0, -1),
        color: tuple = (1, 1, 1, 1)
    ) -> NodePath:
        '''Add a directional light to the scene.'''
        base = cls._instance.base
        render = base.render
        
        directional_light = DirectionalLight("directional_light")
        directional_light.setColor(color)
        directional_node = render.attachNewNode(directional_light)
        directional_node.setPos(*pos)
        directional_node.lookAt(direction[0], direction[1], direction[2])
        render.setLight(directional_node)
        
        return directional_node
