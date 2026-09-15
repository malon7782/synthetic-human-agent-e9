class BrowserTask:
    def __init__(self, process, ui, timing):
        self.process = process
        self.ui = ui
        self.timing = timing

    def run(self):

        # run a certain app
        self.process.launch("msedge.exe")
        

        self.timing.pause()
        

        x, y = self.ui.get_coords("search_box")        # not implemented yet
        self.ui.move_and_click(x, y)                
        self.ui.type_text("NTU Hackathon")