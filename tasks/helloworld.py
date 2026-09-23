import pyautogui
import re
from pywinauto import Desktop


class HelloWorldTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def _blank_desktop_point(self):
        """Find a point away from the cached desktop icons and taskbar."""
        screen_width, screen_height = pyautogui.size()
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

    def _find_created_text_document(self):
        names = tuple(self.ui.desktop_icons)
        prefixes = ("new text document", "新建文本文档")
        matches = [
            name for name in names
            if name.casefold().startswith(prefixes)
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise RuntimeError(
                "Expected one text document on the desktop; "
                f"matching names: {matches}; desktop items: {list(names)}"
            )
        return matches[0]

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

    def run(self):
        if not self.ui.is_on_desktop():
            pyautogui.hotkey("win", "d")
            self.timing.delay()

        self.ui.fetch_desktop()
        document_name = self._find_created_text_document()
        if document_name is None:
            x, y = self._blank_desktop_point()

            # Open the desktop context menu, then choose New > Text Document.
            pyautogui.press("esc")
            self.ui.move_and_click(x, y, "right")
            self.timing.delay()
            self.ui.click_context_menu_item("New")
            self.timing.delay()
            self.ui.click_context_menu_item("Text Document")
            pyautogui.press("enter")
            self.timing.delay()

            self.ui.fetch_desktop()
            document_name = self._find_created_text_document()
            if document_name is None:
                raise RuntimeError("The new text document did not appear on the desktop")

        x, y = self.ui.get_coords_desktop(document_name)
        self.ui.move_and_click(x, y, "double")
        self._open_editor(document_name)

        pyautogui.hotkey("ctrl", "a")
        self.ui.type_text('print("Hello world!")')
        pyautogui.hotkey("ctrl", "s")
        self.timing.delay()
        self.ui.click_window_button("close")
        self.timing.pause()

        self.ui.fetch_desktop()
        x, y = self.ui.get_coords_desktop(document_name)
        self.ui.move_and_click(x, y, "right")
        self.timing.delay()
        self.ui.click_context_menu_item("Rename")
        self.timing.delay()
        pyautogui.hotkey("ctrl", "a")
        self.ui.type_text("helloworld.py")
        pyautogui.press("enter")
        self.timing.delay()
        pyautogui.press("enter")
        

