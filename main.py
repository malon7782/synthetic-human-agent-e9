import random
from core.timing import Timing
from core.process import Process
from core.ui import UI
from tasks.browser import BrowserTask
from tasks.default import DefaultTask
from tasks.play import PlayTask



def main():
    timing = Timing()
    process = Process()
    ui = UI(timing)

    # the special one
    default_task = DefaultTask(ui, timing)
    # registry of tasks
    task_list = {
        'browser': BrowserTask(process, ui, timing),
        'play': PlayTask(ui, timing),
    }

    for count in range(2):
        # set everything to the default status
        default_task.run()
        task_list[random.choice(list(task_list.keys()))].run()
        timing.pause()
        print("done.")

if __name__ == "__main__":
    main()
