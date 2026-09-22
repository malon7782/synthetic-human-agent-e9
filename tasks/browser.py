import pyautogui

class BrowserTask:
    def __init__(self, process, ui, timing):
        self.process = process
        self.ui = ui
        self.timing = timing

    def run(self):
        self.ui.fetch_desktop()

        x, y = self.ui.get_coords_desktop("Microsoft Edge")
        self.ui.move_and_click(x, y, "move")
        self.timing.delay()

        self.ui.move_and_click(x, y, "double")
        self.timing.pause()

        pyautogui.hotkey('win', 'up')
        self.timing.delay()

        self.ui.type_text("676767")
        self.timing.pause()

        pyautogui.press('enter')
        self.timing.delay()

        self.ui.move_and_click(x, y)
        self.ui.move_and_click(x, y, "scroll", None, None, -500)
        self.ui.move_and_click(x, y, "scroll", None, None, -500)
        self.ui.move_and_click(x, y, "scroll", None, None, -500)
        self.ui.move_and_click(x, y, "scroll", None, None, -500)
