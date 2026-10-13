from ..__test import Test
from src.globals import GlobalLoader
from config import ASSETS_PATH


class TestModels(Test):
    def on_start(self):
        self.print_title('TestModels started.', color='cyan')
        self.base = GlobalLoader.get_instance().base
        

        super().on_start()

        # Attempt to load several model types (using loader defaults)
        self.models = []
        model_specs = [
            {'name': 'box', 'key': 'box', 'scale': 10, 'pos': (-20, 50, 0)},
            {'name': 'panda', 'key': 'panda', 'scale': 0.5, 'pos': (30, 50, 0)},
            #{'name': 'environment', 'key': 'environment', 'scale': 0.25, 'pos': (60, 50, 0)},
            {'name': 'teapot', 'key': 'teapot', 'scale': 5, 'pos': (90, 50, 0)},
        ]

        for spec in model_specs:
            try:
                model = GlobalLoader.load_panda_asset(spec['key'])
                model.setScale(spec['scale'])
                model.setPos(*spec['pos'])
                model.reparentTo(self.base.render)
                self.models.append(model)
                self.p(f"Loaded {spec['name']} at {model.getPos()}", color='green')
            except Exception as exc:  # noqa: BLE001
                self.p(f"Failed to load {spec['name']} ({spec['key']}): {exc}", color='red')

        # Also create BaseModel actors with animations
        self.__create_base_model()


    def __create_base_model(self):
        try:
            actor = GlobalLoader.load_actor(
                asset_path="X Bot.glb",
                animations={
                    "Idle": "anims/X Bot@Idle.glb",
                }
            )
            #actor.setScale(0)
            actor.setHpr(0, 90, 0)
            actor.setPos(0, 30, 0)
            actor.reparentTo(self.base.render)
            
            print(f"Animation names: {actor.getAnimNames()}")
            anim = actor.getAnimControl("Idle")
            if anim:
                print(f"Frames: {anim.getNumFrames()}")
                print(f"Frame rate: {anim.getFrameRate()}")
            else:
                print("No animation control found for 'Idle'")
                return
            
            print("Attempting to loop animation...")
            #actor.loop("Idle")
            print("Animation loop commented out for testing")
        except Exception as exc:
            self.p(f"Error creating base model: {exc}", color='red')
            import traceback
            traceback.print_exc()


    def on_stop(self):
        self.print_subtitle('TestModels stopped.')
        for model in getattr(self, 'models', []):
            model.removeNode()
        self.models = []
