from direct.showbase.Loader import Loader
from panda3d.core import NodePath
from typing import Literal


from .__global import Global


class GlobalLoader(Global):
    ''' A singleton class to manage the global loader object. '''
    _assets_path = 'assets/' # Path to the assets directory.
    __models: dict[str, NodePath] = {} # Cache for loaded models.

    ModelKey = Literal['box', 'panda', 'environment', 'teapot']


    @classmethod
    def get_global_loader(cls) -> Loader:
        '''Get the global loader object.'''
        loader = cls._instance.base.loader
        if loader is None:
            raise Exception('Loader is not initialized.')
        return loader
    

    @classmethod
    def __load(cls, asset_path: str) -> NodePath:
        '''Internal loader with caching.'''
        if asset_path in cls.__models:
            return cls.__models[asset_path]

        model = cls.get_global_loader().loadModel(asset_path)
        cls.__models[asset_path] = model
        return model


    @classmethod
    def load_panda_asset(cls, model: ModelKey) -> NodePath:
        '''Load a default Panda3D model by key using caching.'''
        default_models = {
            'box': 'models/box',
            'panda': 'models/panda',
            'environment': 'models/environment',
            'teapot': 'models/teapot',
        }

        asset_path = default_models[model]
        return cls.__load(asset_path)

