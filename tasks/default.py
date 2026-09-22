import ctypes
import pyautogui

class DefaultTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        if not self.ui.is_on_desktop():
            pyautogui.hotkey('win', 'd')
            # self.ui.press_hotkey()
            self.timing.delay()

        # this doesn't deserve a standalone api...
        # currently useless tho
        x = ctypes.windll.user32.GetSystemMetrics(0) / 2
        y = ctypes.windll.user32.GetSystemMetrics(1) / 2

        self.ui.move_and_click(x, y, "move")