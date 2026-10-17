import random
from core.timing import Timing
from core.process import Process
from core.ui import UI
from tasks.browser import BrowserTask
from tasks.default import DefaultTask
from tasks.writing import WritingTask
from tasks.helloworld import HelloWorldTask


def main():
    timing = Timing()
    process = Process()
    ui = UI(timing)

    # the special one
    default_task = DefaultTask(ui, timing)
    # registry of tasks
    task_list = {
        'browser': BrowserTask(process, ui, timing),
        'writing': WritingTask(ui, timing),
        'helloworld': HelloWorldTask(ui, timing),
    }

    for count in range(3):

        available = [task for task in task_list.values(
        ) if getattr(task, "enabled", True)]
        if not available:
            break
        # set everything to the default status
        default_task.run()
        # Always try Edge once before randomly choosing subsequent tasks.
        task = task_list['browser'] if count == 0 else random.choice(available)
        task.run()
        timing.pause()
        print("done.")
        count += 1


if __name__ == "__main__":
    main()
