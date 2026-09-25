from core.timing import Timing
from core.process import Process
from core.ui import UI
from tasks.browser import BrowserTask
from tasks.default import DefaultTask
from tasks.helloworld import HelloWorldTask
from tasks.play import PlayTask


def main():
    timing = Timing()
    process = Process()
    ui = UI(timing)
    play_task = PlayTask(ui, timing)
    timing.pause_action = play_task.move_locally

    # the special one
    default_task = DefaultTask(ui, timing)
    # registry of tasks
    task_list = {
        'browser': BrowserTask(process, ui, timing),
        'python': HelloWorldTask(ui, timing),
    }
    timing.pause(0)
    for _ in range(1):
            # set everything to the default status
            default_task.run()
            task_list['python'].run()
            # task_list[random.choice(list(task_list.keys()))].run()
            timing.pause()
            print("done.")

if __name__ == "__main__":
    main()
