from .__test import Test
from src.globals import GlobalLoader


class TestModels(Test):
    def on_start(self):
        self.print_title('TestModels started.', color='cyan')
        base = GlobalLoader.get_instance().base

        super().on_start()

        # Load a model
        model = GlobalLoader.load_panda_asset('models/box')
        model.setScale(10, 10, 10)
        model.setPos(0, 50, 0)
        model.reparentTo(base.render)
        
        # Store reference
        self.model = model

        self.p(f'Model loaded at position: {model.getPos()}', color='green')
        self.p(f'Model scale: {model.getScale()}', color='green')


    def on_stop(self):
        self.print_subtitle('TestModels stopped.')
