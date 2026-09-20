import ctypes

class DefaultTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        if not self.ui.is_on_desktop():
            self.ui.press_hotkey('win', 'd')
            self.timing.delay()

        # this doesn't deserve a standalone api...
        # currently useless tho
        x = ctypes.windll.user32.GetSystemMetrics(0) / 2
        y = ctypes.windll.user32.GetSystemMetrics(1) / 2

        self.ui.move_and_click(x , y)