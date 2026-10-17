class PlayTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def run(self):
        # Each round selects a fresh anchor and its own single/continuous style.
        for index in range(self.ui.rng.randint(2, 6)):
            if index:
                self.timing.play_pause()
                self.timing.delay()
            if not self.ui.play():
                return False
        return True
