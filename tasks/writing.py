class WritingTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        path = self.ui.write_sentences()
        if path is None:
            return False
        return self.ui.organize_desktop_file(path)
