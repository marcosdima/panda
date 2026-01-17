from direct.showbase.Loader import Loader
from panda3d.core import NodePath


from .__global import Global


class GlobalLoader(Global):
    ''' A singleton class to manage the global loader object. '''
    _assets_path = 'assets/' # Path to the assets directory.
    

    def __init__(self) -> None:
        super().__init__()
        self.__models: dict[str, NodePath] = {}


    @classmethod
    def get_global_loader(cls) -> Loader:
        '''Get the global loader object.'''
        loader = cls._instance.base.loader
        if loader is None:
            raise Exception('Loader is not initialized.')
        return loader
    

    @classmethod
    def load_panda_asset(cls, asset_path: str) -> NodePath:
        '''Load an asset from the assets directory.'''
        return cls.get_global_loader().loadModel(asset_path)
    


