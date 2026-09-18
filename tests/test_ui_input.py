import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.ui import UI


class KeyboardGuardTests(unittest.TestCase):
    def test_wrong_foreground_prevents_hotkey(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        sent = []
        with patch("core.ui.win32gui.GetForegroundWindow", return_value=22), patch(
            "core.ui.pyautogui.hotkey", side_effect=lambda *keys: sent.append(keys)
        ):
            with self.assertRaises(RuntimeError):
                ui.press_keys("ctrl", "a", expected_window=11)
        self.assertEqual(sent, [])

    def test_focus_change_during_typing_stops_remaining_characters(self):
        state = {"handle": 11, "delays": 0}

        def delay():
            state["delays"] += 1
            if state["delays"] == 2:
                state["handle"] = 22

        sent = []
        ui = UI(SimpleNamespace(delay=delay))
        with patch("core.ui.win32gui.GetForegroundWindow", side_effect=lambda: state["handle"]), patch(
            "core.ui.pyautogui.write", side_effect=sent.append
        ):
            with self.assertRaises(RuntimeError):
                ui.type_text("hello", expected_window=11)
        self.assertEqual(sent, ["h"])

    def test_unicode_rejected_before_partial_input(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        sent = []
        with patch("core.ui.pyautogui.write", side_effect=sent.append):
            with self.assertRaises(ValueError):
                ui.type_text("hello 中文")
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
