import unittest

from core.session_state import SessionState
from tasks.browser import BrowserTask


PROFILE = {
    "application": {"id": "browser", "title_re": "Example browser"},
    "browser": {
        "search_box": {"auto_id": "search"},
        "ready_tab": {"auto_id": "existing-tab"},
    },
}


class BrowserUI:
    def __init__(self, search_visible=False, tab_visible=False):
        self.current = {
            "handle": 10, "process_id": 20, "title": "Example browser",
            "class_name": "ExampleWindow", "is_desktop": False,
        }
        self.search_visible = search_visible
        self.tab_visible = tab_visible
        self.events = []

    def get_current(self):
        return self.current

    def list_windows(self):
        return [self.current]

    def find_element(self, handle, **selector):
        if selector == PROFILE["browser"]["search_box"] and self.search_visible:
            return {"point": (100, 200)}
        if selector == PROFILE["browser"]["ready_tab"] and self.tab_visible:
            return {"point": (20, 30)}
        return None

    def get_coords(self, element):
        if element is None:
            raise RuntimeError("No visible element")
        return element["point"]

    def move_and_click(self, x, y, **kwargs):
        self.events.append(("click", x, y))
        if (x, y) == (20, 30):
            self.search_visible = True

    def press_keys(self, *keys, expected_window=None):
        self.events.append(("keys", keys))
        self.search_visible = True

    def type_text(self, text, expected_window=None):
        self.events.append(("text", text))


class BrowserTests(unittest.TestCase):
    def test_reuses_existing_tab_before_opening_new_one(self):
        ui = BrowserUI(tab_visible=True)
        task = BrowserTask(ui, SessionState(), PROFILE)
        task.prepare()
        self.assertTrue(task.is_ready(ui.get_current()))
        self.assertEqual(ui.events, [("click", 20, 30)])

    def test_opens_new_tab_only_when_no_matching_tab_exists(self):
        ui = BrowserUI()
        task = BrowserTask(ui, SessionState(), PROFILE)
        task.prepare()
        self.assertTrue(task.is_ready(ui.get_current()))
        self.assertEqual(ui.events, [("keys", ("ctrl", "t"))])

    def test_clicks_before_typing_and_remembers_observed_window(self):
        ui = BrowserUI(search_visible=True)
        session = SessionState()
        BrowserTask(ui, session, PROFILE, text="hello").run()
        self.assertEqual(ui.events, [("click", 100, 200), ("text", "hello")])
        self.assertEqual(session.get_window("browser", ui.list_windows())["handle"], 10)

    def test_missing_search_box_does_not_type(self):
        ui = BrowserUI()
        with self.assertRaises(RuntimeError):
            BrowserTask(ui, SessionState(), PROFILE).run()
        self.assertEqual(ui.events, [])

    def test_wrong_foreground_does_not_click_or_type(self):
        ui = BrowserUI(search_visible=True)
        ui.current["title"] = "Another application"
        with self.assertRaises(RuntimeError):
            BrowserTask(ui, SessionState(), PROFILE).run()
        self.assertEqual(ui.events, [])


if __name__ == "__main__":
    unittest.main()
