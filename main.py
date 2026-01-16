from src import game
from tests import Tests

if __name__ == "__main__":
    app = game.Game()

    test = Tests().get_target()
    if test is not None:
        app.add_scene(test, set_as_main=True)
    
    app.run()
