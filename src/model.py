from .entities import Entity
from .globals.loader import GlobalLoader

class Model:
    def __init__(
        self,
        model_path: str,
    ):
        self.model_path = model_path
        self.model = GlobalLoader.load_from_assets('/Basic/' + model_path)

        
