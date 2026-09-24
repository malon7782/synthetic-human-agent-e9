class DefaultTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        if not self.ui.is_on_desktop():
            self.hotkey('win', 'd')
            # self.ui.press_hotkey()
            self.timing.delay()

        x, y = self.ui.center_of_desktop()
        self.ui.curve_move(x, y)

        x, y = self.ui.center_of_desktop()
        self.ui.curve_move(x, y)

