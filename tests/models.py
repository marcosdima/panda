from .__test import Test
from src.globals import GlobalLoader


class TestModels(Test):
    def on_start(self):
        self.print_title('TestModels started.', color='cyan')
        base = GlobalLoader.get_instance().base

        super().on_start()

        # Attempt to load several model types (using loader defaults)
        self.models = []
        model_specs = [
            {'name': 'box', 'key': 'box', 'scale': 10, 'pos': (0, 50, 0)},
            {'name': 'panda', 'key': 'panda', 'scale': 0.5, 'pos': (30, 50, 0)},
            #{'name': 'environment', 'key': 'environment', 'scale': 0.25, 'pos': (60, 50, 0)},
            {'name': 'teapot', 'key': 'teapot', 'scale': 5, 'pos': (90, 50, 0)},
        ]

        for spec in model_specs:
            try:
                model = GlobalLoader.load_panda_asset(spec['key'])
                model.setScale(spec['scale'])
                model.setPos(*spec['pos'])
                model.reparentTo(base.render)
                self.models.append(model)
                self.p(f"Loaded {spec['name']} at {model.getPos()}", color='green')
            except Exception as exc:  # noqa: BLE001
                self.p(f"Failed to load {spec['name']} ({spec['key']}): {exc}", color='red')


    def on_stop(self):
        self.print_subtitle('TestModels stopped.')
        for model in getattr(self, 'models', []):
            model.removeNode()
        self.models = []
