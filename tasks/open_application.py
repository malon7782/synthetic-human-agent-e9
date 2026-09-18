"""Open a configured application through visible shell controls only."""

import re
import time


_UNSET = object()


class OpenApplicationTask:
    """Bring one configured application to the foreground using visible UI."""

    def __init__(self, ui, session, profile, timeout=10):
        self.ui = ui
        self.session = session
        self.profile = profile
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        self.timeout = timeout

    def is_ready(self, current, remembered=_UNSET):
        """Whether the foreground window is the requested application."""
        if remembered is _UNSET:
            remembered = self.session.get_window(
                self.profile["id"], self.ui.list_windows()
            )
        if current is None:
            return False
        if re.fullmatch(self.profile["title_re"], current["title"]) is None:
            return False
        return remembered is None or current["handle"] == remembered["handle"]

    def run(self):
        app_id = self.profile["id"]
        remembered = self.session.get_window(app_id, self.ui.list_windows())
        current = self.ui.get_current()
        if self.is_ready(current, remembered):
            self.session.remember(app_id, current)
            return current

        routes = (
            (self._open_from_taskbar, self._open_from_desktop)
            if remembered is not None
            else (self._open_from_desktop, self._open_from_taskbar)
        )
        for open_route in routes:
            if self._try_route(open_route):
                return self._wait_for_foreground()

        if self._try_search():
            return self._wait_for_foreground()
        raise RuntimeError(
            f"No visible route configured or found for application {app_id!r}"
        )

    def _try_route(self, route):
        launcher = route()
        if launcher is None:
            return False
        element, clicks = launcher
        self._click(element, clicks=clicks)
        return True

    def _open_from_desktop(self):
        selector = self.profile.get("desktop_selector")
        current = self.ui.get_current()
        if selector is None or current is None:
            return None
        if current.get("is_taskbar", False) or current.get("is_auxiliary", False):
            if not self.ui.is_desktop(current):
                return None
            current = self.ui.get_desktop()
        if current is None or not current["is_desktop"]:
            return None
        element = self.ui.find_element(current["handle"], **selector)
        return None if element is None else (element, 2)

    def _open_from_taskbar(self):
        selector = self.profile.get("taskbar_selector")
        if selector is None:
            return None
        taskbar = self.ui.find_window(class_name="Shell_TrayWnd")
        if taskbar is None:
            return None
        element = self.ui.find_element(taskbar["handle"], **selector)
        return None if element is None else (element, 1)

    def _try_search(self):
        search = self.profile.get("search")
        if search is None:
            return False
        required = ("entry_window", "entry", "panel", "input", "query", "result")
        missing = [field for field in required if field not in search]
        if missing:
            raise RuntimeError(
                "Search route is missing configuration fields: " + ", ".join(missing)
            )

        entry_window = self.ui.find_window(**search["entry_window"])
        if entry_window is None:
            return False
        entry = self.ui.find_element(entry_window["handle"], **search["entry"])
        if entry is None:
            return False
        self._click(entry)

        panel = self._wait_for_window(search["panel"])
        if panel is None:
            raise RuntimeError("Search entry was clicked but the configured search panel did not appear")
        input_element = self._wait_for_element(panel["handle"], search["input"])
        if input_element is None:
            raise RuntimeError("Search panel appeared but the configured search input did not appear")
        self._click(input_element)
        self.ui.press_keys("ctrl", "a", expected_window=panel["handle"])
        self.ui.type_text(search["query"], expected_window=panel["handle"])

        panel = self._wait_for_window(search["panel"])
        result = None if panel is None else self._wait_for_element(
            panel["handle"], search["result"]
        )
        if result is None:
            raise RuntimeError("Search query was entered but the configured result did not appear")
        self._click(result)
        return True

    def _click(self, element, clicks=1):
        x, y = self.ui.get_coords(element)
        current = self.ui.get_current()
        if current is None:
            raise RuntimeError("Cannot click a control without a foreground window")
        expected_window = current["handle"]
        self.ui.move_and_click(
            x, y, button="left", clicks=clicks, expected_window=expected_window
        )

    def _wait_for_window(self, selector):
        return self._wait(lambda: self.ui.find_window(**selector))

    def _wait_for_element(self, window_handle, selector):
        return self._wait(lambda: self.ui.find_element(window_handle, **selector))

    def _wait_for_foreground(self):
        deadline = time.monotonic() + self.timeout
        while True:
            current = self.ui.get_current()
            remembered = self.session.get_window(
                self.profile["id"], self.ui.list_windows()
            )
            if self.is_ready(current, remembered):
                self.session.remember(self.profile["id"], current)
                return current
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        raise RuntimeError(
            f"A visible launcher was clicked for {self.profile['id']!r}, "
            "but the requested application could not verify as the foreground window"
        )

    def _wait(self, observe):
        deadline = time.monotonic() + self.timeout
        value = observe()
        while value is None and time.monotonic() < deadline:
            time.sleep(0.05)
            value = observe()
        return value
