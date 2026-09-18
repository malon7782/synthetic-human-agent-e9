import unittest

from core.session_state import SessionState
from tasks.open_application import OpenApplicationTask


def window(handle, title, process_id=1, class_name="MainWindow", is_desktop=False):
    return {
        "handle": handle,
        "process_id": process_id,
        "title": title,
        "class_name": class_name,
        "is_desktop": is_desktop,
    }


PROFILE = {
    "id": "edge",
    "title_re": r"Microsoft Edge",
    "desktop_selector": {"title": "Edge desktop icon"},
    "taskbar_selector": {"app_id": "MSEdge"},
    "search": None,
}


class FakeUI:
    def __init__(self, current, windows, elements=(), on_click=None):
        self.current = current
        self.windows = windows
        self.elements = list(elements)
        self.on_click = on_click
        self.calls = []

    def get_current(self):
        return self.current

    def list_windows(self):
        return list(self.windows)

    def find_window(self, **selector):
        self.calls.append(("find_window", selector))
        for item in self.windows:
            if all(item.get(key) == value for key, value in selector.items()):
                return item
        return None

    def find_element(self, window_handle, **selector):
        self.calls.append(("find_element", window_handle, selector))
        for item in self.elements:
            if item["window_handle"] == window_handle and all(
                item.get(key) == value for key, value in selector.items()
            ):
                return item
        return None

    def get_coords(self, element):
        return element["coords"]

    def move_and_click(self, x, y, button="left", clicks=1, expected_window=None):
        self.calls.append(("click", x, y, button, clicks, expected_window))
        if self.on_click:
            self.on_click(x, y, clicks)

    def type_text(self, text, expected_window=None):
        self.calls.append(("type", text, expected_window))

    def press_keys(self, *keys, expected_window=None):
        self.calls.append(("keys", keys, expected_window))


def element(window_handle, coords, **selector):
    return {"window_handle": window_handle, "coords": coords, **selector}


class OpenApplicationTaskTests(unittest.TestCase):
    def test_cache_refreshes_when_remembered_window_closes_during_wait(self):
        old_edge = window(11, "Microsoft Edge", process_id=1)
        new_edge = window(12, "Microsoft Edge", process_id=2)
        taskbar = window(20, "", class_name="Shell_TrayWnd")
        class ClosingWindowUI(FakeUI):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.current_reads = 0

            def get_current(self):
                self.current_reads += 1
                if self.current_reads == 3:
                    self.windows = [new_edge, taskbar]
                    return None
                if self.current_reads >= 4:
                    return new_edge
                return self.current

        ui = ClosingWindowUI(
            current=window(99, "Other"),
            windows=[old_edge, taskbar],
            elements=[element(20, (10, 10), app_id="MSEdge")],
        )
        session = SessionState()
        session.remember("edge", old_edge)

        result = OpenApplicationTask(ui, session, PROFILE, timeout=0.2).run()

        self.assertEqual(result, new_edge)
        self.assertEqual(session.get_window("edge", [new_edge]), new_edge)

    def test_route_refuses_to_click_without_a_foreground_window(self):
        taskbar = window(20, "", class_name="Shell_TrayWnd")
        ui = FakeUI(
            current=None,
            windows=[taskbar],
            elements=[element(20, (10, 10), app_id="MSEdge")],
        )

        with self.assertRaisesRegex(RuntimeError, "foreground window"):
            OpenApplicationTask(
                ui, SessionState(), {**PROFILE, "desktop_selector": None}, timeout=0
            ).run()

        self.assertFalse(any(call[0] == "click" for call in ui.calls))

    def test_is_ready_rejects_matching_title_when_valid_cache_has_other_handle(self):
        remembered_edge = window(11, "Microsoft Edge")
        foreground_edge = window(12, "Microsoft Edge")
        ui = FakeUI(current=foreground_edge, windows=[remembered_edge, foreground_edge])
        session = SessionState()
        session.remember("edge", remembered_edge)

        self.assertFalse(OpenApplicationTask(ui, session, PROFILE).is_ready(foreground_edge))

    def test_run_does_not_click_when_requested_application_is_foreground(self):
        edge = window(11, "Microsoft Edge")
        ui = FakeUI(current=edge, windows=[edge])
        session = SessionState()

        result = OpenApplicationTask(ui, session, PROFILE).run()

        self.assertEqual(result, edge)
        self.assertFalse(any(call[0] == "click" for call in ui.calls))

    def test_valid_cache_uses_taskbar_before_desktop(self):
        edge = window(11, "Microsoft Edge")
        taskbar = window(20, "", class_name="Shell_TrayWnd")
        desktop = window(30, "", is_desktop=True)
        ui = FakeUI(
            current=window(99, "Other"),
            windows=[edge, taskbar, desktop],
            elements=[
                element(20, (10, 10), app_id="MSEdge"),
                element(30, (20, 20), title="Edge desktop icon"),
            ],
            on_click=lambda x, y, clicks: setattr(ui, "current", edge),
        )
        session = SessionState()
        session.remember("edge", edge)

        result = OpenApplicationTask(ui, session, PROFILE).run()

        self.assertEqual(result, edge)
        self.assertIn(("click", 10, 10, "left", 1, 99), ui.calls)
        self.assertNotIn(("click", 20, 20, "left", 2, 99), ui.calls)

    def test_stale_cache_falls_back_to_desktop_with_double_click(self):
        edge = window(11, "Microsoft Edge")
        desktop = window(30, "", is_desktop=True)
        ui = FakeUI(
            current=desktop,
            windows=[edge, desktop],
            elements=[element(30, (20, 20), title="Edge desktop icon")],
            on_click=lambda x, y, clicks: setattr(ui, "current", edge),
        )
        session = SessionState()
        session.remember("edge", window(999, "Old Edge"))

        result = OpenApplicationTask(ui, session, PROFILE).run()

        self.assertEqual(result, edge)
        self.assertIn(("click", 20, 20, "left", 2, 30), ui.calls)

    def test_missing_visible_routes_raises(self):
        ui = FakeUI(current=window(30, "", is_desktop=True), windows=[])

        with self.assertRaisesRegex(RuntimeError, "No visible route"):
            OpenApplicationTask(ui, SessionState(), PROFILE, timeout=0).run()

    def test_unverified_desktop_click_does_not_try_taskbar(self):
        desktop = window(30, "", is_desktop=True)
        taskbar = window(20, "", class_name="Shell_TrayWnd")
        ui = FakeUI(
            current=desktop,
            windows=[taskbar, desktop],
            elements=[
                element(30, (20, 20), title="Edge desktop icon"),
                element(20, (10, 10), app_id="MSEdge"),
            ],
        )

        with self.assertRaisesRegex(RuntimeError, "could not verify"):
            OpenApplicationTask(ui, SessionState(), PROFILE, timeout=0).run()

        self.assertIn(("click", 20, 20, "left", 2, 30), ui.calls)
        self.assertNotIn(("click", 10, 10, "left", 1, 30), ui.calls)

    def test_remembers_only_after_foreground_title_matches(self):
        edge = window(11, "Microsoft Edge")
        desktop = window(30, "", is_desktop=True)
        ui = FakeUI(
            current=desktop,
            windows=[edge, desktop],
            elements=[element(30, (20, 20), title="Edge desktop icon")],
            on_click=lambda x, y, clicks: setattr(ui, "current", edge),
        )
        session = SessionState()

        OpenApplicationTask(ui, session, PROFILE).run()

        self.assertEqual(session.get_window("edge", [edge]), edge)

    def test_configured_search_opens_application(self):
        edge = window(11, "Microsoft Edge")
        desktop = window(30, "", is_desktop=True)
        search_panel = window(40, "Search")
        profile = {
            **PROFILE,
            "desktop_selector": None,
            "taskbar_selector": None,
            "search": {
                "entry_window": {"handle": 30},
                "entry": {"name": "Search entry"},
                "panel": {"handle": 40},
                "input": {"name": "Search input"},
                "query": "Microsoft Edge",
                "result": {"name": "Microsoft Edge result"},
            },
        }
        ui = FakeUI(
            current=desktop,
            windows=[edge, desktop, search_panel],
            elements=[
                element(30, (1, 1), name="Search entry"),
                element(40, (2, 2), name="Search input"),
                element(40, (3, 3), name="Microsoft Edge result"),
            ],
        )

        def advance_search(x, y, clicks):
            if (x, y) == (1, 1):
                ui.current = search_panel
            elif (x, y) == (3, 3):
                ui.current = edge

        ui.on_click = advance_search

        result = OpenApplicationTask(ui, SessionState(), profile).run()

        self.assertEqual(result, edge)
        self.assertIn(("keys", ("ctrl", "a"), 40), ui.calls)
        self.assertIn(("type", "Microsoft Edge", 40), ui.calls)
        self.assertIn(("click", 3, 3, "left", 1, 40), ui.calls)


if __name__ == "__main__":
    unittest.main()
