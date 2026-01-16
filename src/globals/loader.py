from direct.showbase.Loader import Loader


from .__global import Global


class GlobalLoader(Global):
    ''' A singleton class to manage the global loader object. '''
    _assets_path = "assets/" # Path to the assets directory.


    @classmethod
    def get_global_loader(cls) -> Loader:
        '''Get the global loader object.'''
        loader = cls._instance.base.loader
        if loader is None:
            raise Exception("Loader is not initialized.")
        return loader
    

    @classmethod
    def load_panda_asset(cls, asset_path: str):
        '''Load an asset from the assets directory.'''
        full_path = cls._assets_path + asset_path
        return cls.get_global_loader().loadModel(full_path)
    


