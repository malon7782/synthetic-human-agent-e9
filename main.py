from core.timing import Timing
from core.process import Process
from core.ui import UI
from tasks.browser import BrowserTask

def main():
    timing = Timing()
    process = Process()
    ui = UI(timing)
    
    task = BrowserTask(process, ui, timing)
    task.run()
    print("done.")

if __name__ == "__main__":
    main()