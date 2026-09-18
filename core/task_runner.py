import time
import logging

from tasks.return_to_desktop import ReturnToDesktopTask


class TaskRunner:
    """Run business tasks implementing is_ready, prepare and run.

    Desktop and application setup steps are called directly via run().
    """

    def __init__(self, ui, timeout=10, desktop_task=None):
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        self.ui = ui
        self.timeout = timeout
        self.desktop_task = desktop_task

    def run(self, task):
        logging.info("Checking task: %s", type(task).__name__)
        if not task.is_ready(self.ui.get_current()):
            if getattr(task, "requires_desktop", True):
                (self.desktop_task or ReturnToDesktopTask(self.ui)).run()
            logging.info("Preparing task: %s", type(task).__name__)
            task.prepare()
            deadline = time.monotonic() + self.timeout
            while not task.is_ready(self.ui.get_current()):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"{type(task).__name__}: required interface is not ready"
                    )
                time.sleep(min(0.2, remaining))
        logging.info("Executing task: %s", type(task).__name__)
        return task.run()
