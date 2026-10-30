from src.globals import GlobalLoader

from ..__test import Test


class TestModels(Test):
    def on_start(self) -> None:
        self.print_title("TestModels started.", color="cyan")
        self.base = GlobalLoader.get_instance().base

        super().on_start()

        # Attempt to load several model types (using loader defaults)
        self.models = []
        model_specs = [
            {"name": "box", "key": "box", "scale": 10, "pos": (-20, 50, 0)},
            {"name": "panda", "key": "panda", "scale": 0.5, "pos": (30, 50, 0)},
            {"name": "teapot", "key": "teapot", "scale": 5, "pos": (90, 50, 0)},
        ]

        for spec in model_specs:
            try:
                model = GlobalLoader.load_panda_asset(spec["key"])
                model.setScale(spec["scale"])
                model.setPos(*spec["pos"])
                model.reparentTo(self.base.render)
                self.models.append(model)
                self.p(f"Loaded {spec['name']} at {model.getPos()}", color="green")
            except Exception as exc:  # noqa: BLE001
                self.p(
                    f"Failed to load {spec['name']} ({spec['key']}): {exc}", color="red"
                )

        # Also create BaseModel actors with animations
        self.__create_base_model()

    def __create_base_model(self) -> None:
        try:
            actor = GlobalLoader.load_actor(
                asset_path="X Bot.glb",
                animations={
                    "Idle": "anims/X Bot@Idle.glb",
                },
            )
            actor.setHpr(0, 90, 0)
            actor.setPos(0, 30, 0)
            actor.reparentTo(self.base.render)
            self.actor = actor

            self.p(f"Animation names: {actor.getAnimNames()}", color="green")
            anim = actor.getAnimControl("Idle")
            if anim:
                self.p(f"Frames: {anim.getNumFrames()}", color="green")
                self.p(f"Frame rate: {anim.getFrameRate()}", color="green")
            else:
                self.p("No animation control found for 'Idle'", color="red")
                return

            actor.loop("Idle")
        except Exception as exc:  # noqa: BLE001
            self.p(f"Error creating base model: {exc}", color="red")
            import traceback

            traceback.print_exc()

    def on_stop(self) -> None:
        self.print_subtitle("TestModels stopped.")
        # Detach (not remove) cached models so GlobalLoader's cache stays valid.
        for model in getattr(self, "models", []):
            if model is not None and not model.isEmpty():
                model.detachNode()
        self.models = []

        # The actor instance is unique to this scene, so removing it is safe.
        actor = getattr(self, "actor", None)
        if actor is not None and not actor.isEmpty():
            actor.removeNode()
        self.actor = None


if __name__ == "__main__":
    from src import game

    app = game.Game()
    sandbox = TestModels()
    app.add_scene(sandbox, set_as_main=True)
    app.run()
