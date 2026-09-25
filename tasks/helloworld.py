import os
import re

import pyperclip
from pywinauto import Desktop


class HelloWorldTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def _blank_desktop_point(self):
        """Find a point away from the cached desktop icons and taskbar."""
        screen_width, screen_height = self.ui.screen_size()
        icon_bounds = tuple(self.ui.desktop_icons.values())

        for y_ratio in (0.55, 0.45, 0.65, 0.35, 0.75):
            for x_ratio in (0.70, 0.80, 0.60, 0.90, 0.50):
                x = round(screen_width * x_ratio)
                y = round(screen_height * y_ratio)
                if all(
                    not (left - 70 <= x <= right + 70 and top - 45 <= y <= bottom + 45)
                    for left, top, right, bottom in icon_bounds
                ):
                    return x, y

        raise RuntimeError("Could not find a clear point on the desktop")

    def _find_new_desktop_item(self, previous_names):
        new_names = set(self.ui.desktop_icons) - previous_names
        if len(new_names) != 1:
            raise RuntimeError(
                "Expected exactly one new desktop item after creating a text document; "
                f"new items: {sorted(new_names)}"
            )
        return new_names.pop()

    @staticmethod
    def _open_editor(document_name):
        title_pattern = f".*{re.escape(document_name)}.*"
        editor = Desktop(backend="uia").window(title_re=title_pattern)
        try:
            editor.wait("visible", timeout=15)
            editor.set_focus()
        except Exception as error:
            raise RuntimeError(
                f"The editor window for {document_name!r} did not appear"
            ) from error

    def _run_with_powershell(self):
        """Copy the script path from its context menu and run it in PowerShell."""
        self.ui.fetch_desktop()
        x, y = self.ui.get_coords_desktop("helloworld.py")
        """self.ui.key_down("shift")
        try:
            self.ui.move_and_click(x, y, "right")
        finally:
            self.ui.key_up("shift")"""
        self.ui.move_and_click(x, y, "right")
        self.timing.pause()
        self.ui.click_context_menu_item("Copy as path")
        self.timing.pause()

        script_path = pyperclip.paste().strip()
        script_name = os.path.basename(script_path.strip('"')).casefold()
        if script_name != "helloworld.py":
            raise RuntimeError(
                "Copy as path did not copy the expected helloworld.py file; "
                f"clipboard contents: {script_path!r}"
            )

        self.timing.delay()
        self.ui.hotkey("win", "r")
        self.timing.delay()
        self.ui.type_text("powershell")
        self.ui.press("enter")

        powershell = Desktop(backend="uia").window(title_re=".*PowerShell.*")
        try:
            powershell.wait("visible", timeout=15)
            powershell.set_focus()
        except Exception as error:
            raise RuntimeError("The PowerShell window did not appear") from error

        self.timing.pause()
        self.ui.type_text("python ")
        self.ui.hotkey("ctrl", "v")
        self.timing.pause()
        self.ui.press("enter")

    def run(self):
        """Create and run the script after DefaultTask prepares the desktop."""
        self.ui.fetch_desktop()
        if any(
            name.casefold() == "helloworld.py"
            for name in self.ui.desktop_icons
        ):
            raise RuntimeError(
                "helloworld.py already exists on the desktop; "
                "move or rename it before running this task"
            )

        previous_names = set(self.ui.desktop_icons)
        x, y = self._blank_desktop_point()

        # Open the desktop context menu, then choose New > Text Document.
        self.ui.press("esc")
        self.ui.move_and_click(x, y, "right")
        self.timing.delay()
        self.ui.click_context_menu_item("New")
        self.timing.delay()
        self.ui.click_context_menu_item("Text Document")
        self.ui.press("enter")
        self.timing.delay()

        self.ui.fetch_desktop()
        document_name = self._find_new_desktop_item(previous_names)

        x, y = self.ui.get_coords_desktop(document_name)
        self.ui.move_and_click(x, y, "double")
        self._open_editor(document_name)

        self.ui.press("enter")
        self.ui.hotkey("ctrl", "a")
        self.ui.type_text('print("Hello world!")')
        self.ui.hotkey("ctrl", "s")
        self.timing.delay()
        self.ui.click_window_button("close")
        self.timing.pause()

        self.ui.fetch_desktop()
        x, y = self.ui.get_coords_desktop(document_name)
        self.ui.move_and_click(x, y, "right")
        self.timing.delay()
        self.ui.click_context_menu_item("Rename")
        self.timing.delay()
        self.ui.hotkey("ctrl", "a")
        self.ui.type_text("helloworld.py")
        self.ui.press("enter")
        self.timing.delay()
        if not self.ui.is_on_desktop():
            self.ui.press("enter")
            self.timing.delay()

        self.ui.fetch_desktop()
        if "helloworld.py" not in self.ui.desktop_icons:
            raise RuntimeError(
                "Renaming the new document to helloworld.py did not finish"
            )
        self._run_with_powershell()
        self.timing.pause()
        self.ui.click_window_button("close")
