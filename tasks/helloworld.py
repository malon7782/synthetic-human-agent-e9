class HelloWorldTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        path = self.ui.write_hello_world()
        if path is None:
            return False
        # Save As creates a separate PY; arrange only the original TXT.
        return self.ui.organize_desktop_file(self.ui.last_created_text_path)
