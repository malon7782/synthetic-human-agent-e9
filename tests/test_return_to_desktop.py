import unittest

from tasks.return_to_desktop import ReturnToDesktopTask


class FakeUI:
    def __init__(self, windows):
        self.windows = list(windows)
        self.current = self.windows.pop(0) if self.windows else None
        self.minimized = set()
        self.calls = []
        self.button = {"rect": (10, 20, 30, 40)}

    def get_current(self):
        self.calls.append(("get_current",))
        return self.current

    def is_desktop(self, current):
        return current is not None and current["handle"] == "desktop"

    def get_desktop(self):
        return window("desktop")

    def find_element(self, handle, **selector):
        self.calls.append(("find_element", handle, selector))
        return self.button

    def get_coords(self, element):
        self.calls.append(("get_coords", element))
        return (20, 30)

    def move_and_click(self, x, y, **kwargs):
        self.calls.append(("move_and_click", x, y, kwargs))
        handle = kwargs["expected_window"]
        self.minimized.add(handle)
        self.current = self.windows.pop(0) if self.windows else None

    def is_minimized(self, handle):
        self.calls.append(("is_minimized", handle))
        return handle in self.minimized


def window(handle):
    return {"handle": handle, "title": str(handle)}


class ReturnToDesktopTaskTests(unittest.TestCase):
    def test_auxiliary_foreground_between_two_apps_does_not_stop_the_loop(self):
        first, second = window("first"), window("second")
        helper = {"handle": "helper", "title": "", "is_auxiliary": True}
        ui = FakeUI([first])
        selected = []
        observations = []

        def visible_windows():
            observations.append(True)
            return [item for item in (first, second) if item["handle"] not in ui.minimized]

        ui.list_visible_application_windows = visible_windows

        def find_element(handle, **selector):
            selected.append(handle)
            return ui.button

        def click(x, y, **kwargs):
            ui.minimized.add(selected[-1])
            ui.current = helper

        ui.find_element = find_element
        ui.move_and_click = click
        ReturnToDesktopTask(ui, poll_interval=0).run()
        self.assertEqual(selected, ["first", "second"])
        self.assertEqual(ui.minimized, {"first", "second"})
        self.assertEqual(len(observations), 2)

    def test_taskbar_focus_minimizes_remaining_app_not_taskbar(self):
        taskbar = {"handle": "taskbar", "title": "", "is_taskbar": True}
        app = window("app")
        ui = FakeUI([taskbar])
        ui.is_desktop = lambda current: current == taskbar and "app" in ui.minimized
        ui.list_visible_application_windows = lambda: [] if "app" in ui.minimized else [app]

        def click(x, y, **kwargs):
            ui.calls.append(("move_and_click", x, y, kwargs))
            ui.minimized.add("app")

        ui.move_and_click = click
        ReturnToDesktopTask(ui, poll_interval=0).run()
        lookups = [call[1] for call in ui.calls if call[0] == "find_element"]
        self.assertEqual(lookups, ["app"])
        clicks = [call for call in ui.calls if call[0] == "move_and_click"]
        self.assertEqual(clicks[0][3]["expected_window"], "taskbar")

    def test_uses_observation_then_single_physical_click_per_window(self):
        ui = FakeUI([window("one"), window("two"), window("desktop")])

        ReturnToDesktopTask(ui, poll_interval=0).run()

        clicks = [call for call in ui.calls if call[0] == "move_and_click"]
        self.assertEqual(len(clicks), 2)
        self.assertEqual([call[1:3] for call in clicks], [(20, 30), (20, 30)])
        self.assertEqual(
            [call[3] for call in clicks],
            [
                {"button": "left", "expected_window": "one"},
                {"button": "left", "expected_window": "two"},
            ],
        )
        self.assertEqual(
            [call for call in ui.calls if call[0] == "find_element"][0],
            ("find_element", "one", {"title": "Minimize", "control_type": "Button"}),
        )

    def test_accepts_a_deployment_specific_minimize_selector(self):
        ui = FakeUI([window("one"), window("desktop")])
        selector = {"auto_id": "minimizeButton", "control_type": "Button"}

        ReturnToDesktopTask(ui, minimize_selector=selector, poll_interval=0).run()

        self.assertIn(("find_element", "one", selector), ui.calls)

    def test_missing_minimize_button_stops_before_click(self):
        ui = FakeUI([window("one")])
        ui.button = None

        with self.assertRaisesRegex(RuntimeError, "Minimize button not found"):
            ReturnToDesktopTask(ui).run()
        self.assertFalse(any(call[0] == "move_and_click" for call in ui.calls))

    def test_no_progress_stops_after_click(self):
        ui = FakeUI([window("one")])
        ui.move_and_click = lambda *args, **kwargs: ui.calls.append(("move_and_click",))

        with self.assertRaisesRegex(RuntimeError, "Window did not minimize"):
            ReturnToDesktopTask(ui, minimize_timeout=0, poll_interval=0).run()

    def test_returning_to_a_previous_foreground_window_stops_progress(self):
        ui = FakeUI([window("one"), window("two")])
        original_get_current = ui.get_current
        observed_second_window = False

        def get_current():
            nonlocal observed_second_window
            current = original_get_current()
            if (
                current is not None
                and current["handle"] == "two"
                and not observed_second_window
            ):
                observed_second_window = True
                ui.current = window("one")
            return current

        ui.get_current = get_current
        with self.assertRaisesRegex(RuntimeError, "did not change"):
            ReturnToDesktopTask(ui, poll_interval=0).run()
        self.assertEqual(
            len([call for call in ui.calls if call[0] == "move_and_click"]), 1
        )

    def test_unknown_foreground_does_not_count_as_desktop(self):
        ui = FakeUI([])

        with self.assertRaisesRegex(RuntimeError, "Cannot identify"):
            ReturnToDesktopTask(ui).run()

    def test_stops_after_maximum_window_count(self):
        ui = FakeUI([window(str(number)) for number in range(31)])

        with self.assertRaisesRegex(RuntimeError, "after minimizing 30 windows"):
            ReturnToDesktopTask(ui, poll_interval=0).run()
        self.assertEqual(
            len([call for call in ui.calls if call[0] == "move_and_click"]), 30
        )


if __name__ == "__main__":
    unittest.main()
