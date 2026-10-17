import pyautogui


class BrowserTask:
    def __init__(self, process, ui, timing):
        self.process = process
        self.ui = ui
        self.timing = timing
        self.enabled = True

    def run(self):
        if not self.enabled:
            return
        self.ui.fetch_desktop()

        x, y = self.ui.get_coords_desktop("Microsoft Edge")
        self.ui.curve_move(x, y)
        self.timing.delay()

        self.ui.move_and_click(x, y, "double")
        self.timing.pause()

        self.ui.maximize_browser()

        self.enabled = self.ui.edge_has_internet(check_page=False)
        if not self.enabled:
            self.timing.pause()
            self.ui.close_window()
            print("Browser offline; disabled for this run.")
            return

        pyautogui.hotkey('ctrl', 'l')
        self.ui.type_from_corpus("search")
        self.timing.delay()
        self.timing.delay()

        pyautogui.press('enter')
        self.timing.delay()

        self.enabled = self.ui.edge_has_internet(timeout=2)
        if not self.enabled:
            self.ui.close_window()
            print("Browser offline; disabled for this run.")
            return

        x, y = self.ui.center_of_desktop()
        self.ui.scroll_page(x, y)
        self.ui.close_window()
