import os

class Process:
    def launch(self, target_path):
        # simply for bypassing Sysnom monitoring
        # this function is currently not used...
        os.startfile(target_path)