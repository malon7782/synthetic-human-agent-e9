import ctypes

class DefaultTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        if not self.ui.is_on_desktop():
            self.ui.press_hotkey('win', 'd')
            self.timing.pause()

        # this doesn't deserve a standalone api...
        # currently useless tho
        x = ctypes.windll.user32.GetSystemMetrics(0)
        y = ctypes.windll.user32.GetSystemMetrics(1)