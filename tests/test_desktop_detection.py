import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.ui import UI


class DesktopDetectionTests(unittest.TestCase):
    def test_zero_area_foreground_does_not_block_desktop_when_apps_are_gone(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        current = {"is_desktop": False, "is_taskbar": False, "is_auxiliary": True}
        with patch.object(ui, "list_visible_application_windows", return_value=[]), patch.object(
            ui, "get_desktop", return_value={"handle": 65910, "is_desktop": True}
        ):
            self.assertTrue(ui.is_desktop(current))
        with patch.object(ui, "list_visible_application_windows", return_value=[{"handle": 10}]):
            self.assertFalse(ui.is_desktop(current))

    def test_observed_zero_rectangle_is_classified_as_auxiliary(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        with patch("core.ui.win32gui.IsWindow", return_value=True), patch(
            "core.ui.win32gui.GetClassName", return_value="MiPcContinuity"
        ), patch("core.ui.win32gui.GetWindowText", return_value=""), patch(
            "core.ui.win32gui.GetWindowRect", return_value=(-10000, 0, -10000, 0)
        ), patch("core.ui.win32process.GetWindowThreadProcessId", return_value=(1, 17256)), patch(
            "core.ui._get_shell_window", return_value=65910
        ):
            current = ui.get_window(132920)
        self.assertTrue(current.get("is_auxiliary", False))

    def test_observed_shell_taskbar_is_recognized_without_guessing_from_title(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        with patch("core.ui.win32gui.IsWindow", return_value=True), patch(
            "core.ui.win32gui.GetClassName", return_value="Shell_TrayWnd"
        ), patch("core.ui.win32gui.GetWindowText", return_value=""), patch(
            "core.ui.win32process.GetWindowThreadProcessId", return_value=(1, 13948)
        ), patch("core.ui._get_shell_window", return_value=65910), patch(
            "core.ui.win32gui.GetWindowRect", return_value=(0, 900, 1440, 960)
        ):
            current = ui.get_window(65870)
        self.assertTrue(current.get("is_taskbar", False))

    def test_taskbar_is_desktop_only_after_application_windows_are_minimized(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        current = {"is_desktop": False, "is_taskbar": True}
        with patch.object(ui, "list_visible_application_windows", return_value=[]), patch.object(
            ui, "get_desktop", return_value={"handle": 65910}
        ):
            self.assertTrue(ui.is_desktop(current))
        with patch.object(ui, "list_visible_application_windows", return_value=[{"handle": 10}]):
            self.assertFalse(ui.is_desktop(current))

    def test_arbitrary_empty_title_is_not_desktop(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        self.assertFalse(ui.is_desktop({"title": "", "is_desktop": False}))

    def test_same_class_from_non_shell_process_is_not_taskbar(self):
        ui = UI(SimpleNamespace(delay=lambda: None))
        with patch("core.ui.win32gui.IsWindow", return_value=True), patch(
            "core.ui.win32gui.GetClassName", return_value="Shell_TrayWnd"
        ), patch("core.ui.win32gui.GetWindowText", return_value=""), patch(
            "core.ui.win32process.GetWindowThreadProcessId",
            side_effect=lambda handle: (1, 13948 if handle == 65910 else 100),
        ), patch("core.ui._get_shell_window", return_value=65910), patch(
            "core.ui.win32gui.GetWindowRect", return_value=(0, 900, 1440, 960)
        ):
            current = ui.get_window(65870)
        self.assertFalse(current.get("is_taskbar", False))


if __name__ == "__main__":
    unittest.main()
