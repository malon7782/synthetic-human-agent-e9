class HelloWorldTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        return self.ui.write_hello_world() is not None
