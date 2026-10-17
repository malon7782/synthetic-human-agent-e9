import argparse
import math
import random
import time
import pyautogui
from core.timing import Timing
from core.process import Process
from core.ui import UI
from tasks.browser import BrowserTask
from tasks.default import DefaultTask
from tasks.writing import WritingTask
from tasks.helloworld import HelloWorldTask
from tasks.play import PlayTask


def positive_minutes(value):
    minutes = float(value)
    if minutes <= 0 or not math.isfinite(minutes * 60):
        raise argparse.ArgumentTypeError(
            "minutes must be a positive, finite number")
    return minutes


def main(minutes=15):
    minutes = positive_minutes(minutes)
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
        'play': PlayTask(ui, timing),
    }

    deadline = time.monotonic() + minutes * 60
    count = 0
    print(
        f"Running for {minutes:g} minutes; the last task will finish before exit.")
    while time.monotonic() < deadline:
        available = [task for task in task_list.values(
        ) if getattr(task, "enabled", True)]
        if not available:
            break
        # Always try Edge once before randomly choosing subsequent tasks.
        task = task_list['browser'] if count == 0 else random.choice(available)
        count += 1
        try:
            # Reset before each attempt, including after a failed task.
            default_task.run()
            ui.wait_until(ui.is_on_desktop, "desktop to receive focus")
            if time.monotonic() >= deadline:
                break
            succeeded = task.run() is True
            print(
                f"{type(task).__name__}: {'done' if succeeded else 'failed or skipped'}.")
        except pyautogui.FailSafeException:
            raise  # Preserve the user's emergency stop.
        except Exception as error:
            print(f"{type(task).__name__}: failed ({type(error).__name__}: {error}).")
        if time.monotonic() < deadline:
            timing.pause()
    print("Run finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run desktop tasks for a limited time.")
    parser.add_argument("--minutes", type=positive_minutes, default=15,
                        help="run duration in minutes (default: 15); finishes the current task before exit")
    main(parser.parse_args().minutes)
