class BrowserTask:
    def __init__(self, process, ui, timing):
        self.process = process
        self.ui = ui
        self.timing = timing

    def run(self):
        self.ui.fetch_desktop()

        x, y = self.ui.get_coords_desktop("Microsoft Edge")

        self.ui.move_and_click(x, y)

        self.timing.delay()

        self.process.launch("msedge.exe")
        
        self.timing.delay()

        self.ui.type_text("676767")
 