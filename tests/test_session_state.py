import unittest

from core.session_state import SessionState


def window(handle, process_id, title, class_name="MainWindow", is_desktop=False):
    return {
        "handle": handle,
        "process_id": process_id,
        "title": title,
        "class_name": class_name,
        "is_desktop": is_desktop,
    }


class SessionStateTests(unittest.TestCase):
    def test_get_window_returns_fresh_metadata_and_refreshes_title(self):
        state = SessionState()
        state.remember("browser", window(101, 12, "Old title"))
        observed = window(101, 12, "New title")

        found = state.get_window("browser", [observed])

        self.assertEqual(found, observed)
        self.assertIsNot(found, observed)
        self.assertEqual(state.get_window("browser", [observed])["title"], "New title")

    def test_get_window_evicts_missing_handle(self):
        state = SessionState()
        state.remember("browser", window(101, 12, "Browser"))

        self.assertIsNone(state.get_window("browser", [window(102, 12, "Other")]))
        self.assertIsNone(state.get_window("browser", [window(101, 12, "Browser")]))

    def test_get_window_evicts_reused_handle_with_different_identity(self):
        state = SessionState()
        state.remember("browser", window(101, 12, "Browser", "BrowserClass"))

        self.assertIsNone(
            state.get_window("browser", [window(101, 99, "Other", "OtherClass")])
        )
        self.assertIsNone(
            state.get_window("browser", [window(101, 12, "Browser", "BrowserClass")])
        )

    def test_remember_and_lookup_use_defensive_copies(self):
        state = SessionState()
        remembered = window(101, 12, "Browser")
        state.remember("browser", remembered)
        remembered["title"] = "Mutated by caller"
        observed = window(101, 12, "Fresh title")

        found = state.get_window("browser", [observed])
        found["title"] = "Mutated result"

        self.assertEqual(observed["title"], "Fresh title")
        self.assertEqual(state.get_window("browser", [observed])["title"], "Fresh title")

    def test_apps_keep_separate_remembered_windows(self):
        state = SessionState()
        browser = window(101, 12, "Browser")
        editor = window(202, 34, "Editor")
        state.remember("browser", browser)
        state.remember("editor", editor)

        self.assertEqual(state.get_window("browser", [browser, editor]), browser)
        self.assertEqual(state.get_window("editor", [browser, editor]), editor)

if __name__ == "__main__":
    unittest.main()
