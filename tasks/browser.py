class BrowserTask:
    def __init__(self, process, ui, timing):
        self.process = process
        self.ui = ui
        self.timing = timing

    def run(self):
        self.ui.fetch_desktop()


        x, y = self.ui.get_coords_desktop("Microsoft Edge")

        print(x, y)
        # move_and_click()...?

        self.process.launch("msedge.exe")
        

        self.timing.pause()
 