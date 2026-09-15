import os

class Process:
    def launch(self, target_path):
        # simply for bypassing Sysnom monitoring
        os.startfile(target_path)