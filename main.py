import random
from core.timing import Timing
from core.process import Process
from core.ui import UI
from tasks.browser import BrowserTask



def main():
    timing = Timing()
    process = Process()
    ui = UI(timing)

    # registry of tasks
    task_list = {
        'browser': BrowserTask(process, ui, timing)
    }

    while True:
        # randomly select a task
        task_list[random.choice(list(task_list.keys()))].run()
        timing.pause()
        print("done.")

if __name__ == "__main__":
    main()