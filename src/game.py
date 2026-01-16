from direct.showbase.ShowBase import ShowBase

class Game(ShowBase):
    def __init__(self):
        super().__init__()

        self.scene = self.loader.loadModel("models/environment")
        self.scene.reparentTo(self.render)
        self.scene.setScale(0.25)
        self.scene.setPos(-8, 42, 0)
