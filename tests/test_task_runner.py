import unittest

from core.task_runner import TaskRunner
from tasks.return_to_desktop import ReturnToDesktopTask


class ExampleTask:
    def __init__(self, ui, preparation_succeeds=True, requires_desktop=True):
        self.ui = ui
        self.preparation_succeeds = preparation_succeeds
        self.requires_desktop = requires_desktop
        self.events = []

    def is_ready(self, current):
        return current is not None and current["handle"] == "target"

    def prepare(self):
        self.events.append("prepare")
        if self.requires_desktop and not self.ui.is_desktop(self.ui.get_current()):
            raise AssertionError("Preparation must start from the desktop")
        if self.preparation_succeeds:
            self.ui.current = {"handle": "target", "title": "Target"}

    def run(self):
        self.events.append("run")
        return "finished"


class TaskRunnerUI:
    def __init__(self, current):
        self.current = current
        self.events = []
        self.minimized = set()

    def get_current(self):
        return self.current

    def is_desktop(self, current):
        return current is not None and current["handle"] == "desktop"

    def find_element(self, handle, **selector):
        self.events.append(("find", handle, selector))
        return {"handle": handle, "rect": (0, 0, 10, 10)}

    def get_coords(self, element):
        self.events.append(("coords", element))
        return (5, 5)

    def move_and_click(self, x, y, **kwargs):
        self.events.append(("click", x, y, kwargs))
        handle = kwargs["expected_window"]
        self.minimized.add(handle)
        self.current = {"handle": "desktop", "title": "Desktop"}

    def is_minimized(self, handle):
        return handle in self.minimized


class TaskRunnerTests(unittest.TestCase):
    def test_ready_task_runs_without_desktop_reset_or_preparation(self):
        ui = TaskRunnerUI({"handle": "target", "title": "Target"})
        task = ExampleTask(ui)

        self.assertEqual(TaskRunner(ui).run(task), "finished")
        self.assertEqual(task.events, ["run"])
        self.assertEqual(ui.events, [])

    def test_unready_task_returns_to_desktop_before_preparing(self):
        ui = TaskRunnerUI({"handle": "other", "title": "Other"})
        task = ExampleTask(ui)

        self.assertEqual(TaskRunner(ui).run(task), "finished")
        self.assertEqual(task.events, ["prepare", "run"])
        self.assertEqual(
            ui.events[0],
            ("find", "other", {"title": "Minimize", "control_type": "Button"}),
        )
        self.assertEqual(ui.events[-1][0], "click")

    def test_unready_task_never_runs_after_timeout(self):
        ui = TaskRunnerUI({"handle": "desktop", "title": "Desktop"})
        task = ExampleTask(ui, preparation_succeeds=False)

        with self.assertRaises(TimeoutError):
            TaskRunner(ui, timeout=0).run(task)
        self.assertEqual(task.events, ["prepare"])

    def test_preparation_error_stops_execution(self):
        class BrokenTask(ExampleTask):
            def prepare(self):
                raise RuntimeError("Cannot open application")

        ui = TaskRunnerUI({"handle": "desktop", "title": "Desktop"})
        task = BrokenTask(ui)
        with self.assertRaises(RuntimeError):
            TaskRunner(ui).run(task)
        self.assertEqual(task.events, [])

    def test_task_without_desktop_prerequisite_skips_return_task(self):
        ui = TaskRunnerUI({"handle": "other", "title": "Other"})
        task = ExampleTask(ui, requires_desktop=False)

        self.assertEqual(TaskRunner(ui).run(task), "finished")
        self.assertEqual(task.events, ["prepare", "run"])
        self.assertEqual(ui.events, [])

    def test_injected_desktop_task_runs_before_preparation(self):
        ui = TaskRunnerUI({"handle": "other", "title": "Other"})
        task = ExampleTask(ui)

        class DesktopTask:
            def __init__(self):
                self.runs = 0

            def run(self):
                self.runs += 1
                ui.current = {"handle": "desktop", "title": "Desktop"}

        desktop_task = DesktopTask()
        self.assertEqual(TaskRunner(ui, desktop_task=desktop_task).run(task), "finished")
        self.assertEqual(desktop_task.runs, 1)
        self.assertEqual(task.events, ["prepare", "run"])

    def test_return_to_desktop_step_runs_directly(self):
        ui = TaskRunnerUI({"handle": "other", "title": "Other"})

        self.assertIsNone(ReturnToDesktopTask(ui).run())
        self.assertEqual(
            [event[0] for event in ui.events], ["find", "coords", "click"]
        )
        self.assertTrue(ui.is_desktop(ui.get_current()))


if __name__ == "__main__":
    unittest.main()
