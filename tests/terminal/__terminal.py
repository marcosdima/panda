from ..__test import Test


class TerminalTest(Test):
    def on_start(self):
        super().on_start()
        self.run_tests()


    def run_tests(self):
        for name in dir(self):
            if name.startswith('test'):
                attr = getattr(self, name)
                if callable(attr):
                    attr()