"""Windows observation and physical mouse/keyboard primitives only."""

import ctypes
import re
from ctypes import wintypes

import pyautogui
import win32gui
import win32process
import win32con
from pywinauto import Desktop
from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.findwindows import find_elements


_get_shell_window = ctypes.windll.user32.GetShellWindow
_get_shell_window.restype = wintypes.HWND
_get_shell_window.argtypes = []

_get_dwm_attribute = ctypes.windll.dwmapi.DwmGetWindowAttribute
_get_dwm_attribute.restype = ctypes.c_long
_get_dwm_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_DWMWA_CLOAKED = 14


class UI:
    def __init__(self, timing):
        self.timing = timing

    # Observation: metadata and positions, with no window activation.
    def get_window(self, handle):
        if not handle or not win32gui.IsWindow(handle):
            return None
        process_id = win32process.GetWindowThreadProcessId(handle)[1]
        class_name = win32gui.GetClassName(handle)
        shell = _get_shell_window()
        shell_process = win32process.GetWindowThreadProcessId(shell)[1] if shell else None
        left, top, right, bottom = win32gui.GetWindowRect(handle)
        desktop_host = (
            process_id == shell_process
            and class_name in ("Progman", "WorkerW")
            and (handle == shell or bool(win32gui.FindWindowEx(
                handle, 0, "SHELLDLL_DefView", None
            )))
        )
        return {
            "handle": handle,
            "title": win32gui.GetWindowText(handle),
            "process_id": process_id,
            "class_name": class_name,
            "is_desktop": desktop_host,
            "is_taskbar": process_id == shell_process and class_name == "Shell_TrayWnd",
            "is_auxiliary": right <= left or bottom <= top,
        }

    def get_current(self):
        return self.get_window(win32gui.GetForegroundWindow())

    def get_desktop(self):
        return self.get_window(_get_shell_window())

    def is_desktop(self, current):
        if current is None:
            return False
        if current["is_desktop"]:
            return True
        shell_or_auxiliary = current.get("is_taskbar", False) or current.get("is_auxiliary", False)
        return bool(
            shell_or_auxiliary
            and not self.list_visible_application_windows()
            and self.get_desktop() is not None
        )

    def list_visible_application_windows(self):
        """Observe unminimized task windows in Z order, excluding shell helpers."""
        result = []
        for window in self.list_windows():
            handle = window["handle"]
            if window["is_desktop"] or window.get("is_taskbar") or window.get("is_auxiliary") or self.is_minimized(handle):
                continue
            if not win32gui.IsWindowVisible(handle):
                continue
            if win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE) & win32con.WS_EX_NOACTIVATE:
                continue
            if not HwndWrapper(handle).is_in_taskbar():
                continue
            cloaked = wintypes.DWORD()
            status = _get_dwm_attribute(handle, _DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if status != 0:
                raise RuntimeError(f"Cannot determine window visibility: {handle}, HRESULT={status}")
            if not cloaked.value:
                result.append(window)
        return result

    def is_minimized(self, handle):
        return bool(win32gui.IsWindow(handle) and win32gui.IsIconic(handle))

    def list_windows(self, title_re=None):
        windows = []

        def collect(handle, _):
            if win32gui.IsWindowVisible(handle) or win32gui.IsIconic(handle):
                window = self.get_window(handle)
                if window is not None and (
                    title_re is None or re.fullmatch(title_re, window["title"])
                ):
                    windows.append(window)

        win32gui.EnumWindows(collect, None)
        return windows

    def find_window(self, **selector):
        window = Desktop(backend="uia").window(**selector)
        if not window.exists(timeout=0):
            return None
        return self.get_window(window.wrapper_object().handle)

    @staticmethod
    def _describe_element(wrapper, window_handle):
        info = wrapper.element_info
        rect = wrapper.rectangle()
        return {
            "window_handle": window_handle,
            "name": info.name,
            "auto_id": info.automation_id,
            "control_type": info.control_type,
            "rect": (rect.left, rect.top, rect.right, rect.bottom),
            "visible": wrapper.is_visible(),
            "enabled": wrapper.is_enabled(),
        }

    def find_elements(self, window_handle, **selector):
        window = Desktop(backend="uia").window(handle=window_handle)
        if not window.exists(timeout=0):
            return []
        return [
            self._describe_element(UIAWrapper(info), window_handle)
            for info in find_elements(
                parent=window_handle, top_level_only=False, backend="uia", **selector
            )
        ]

    def find_element(self, window_handle, **selector):
        elements = [
            item for item in self.find_elements(window_handle, **selector)
            if item["visible"] and item["enabled"]
            and item["rect"][2] > item["rect"][0]
            and item["rect"][3] > item["rect"][1]
        ]
        if len(elements) > 1:
            raise RuntimeError(f"Multiple visible controls match {selector!r}")
        return elements[0] if elements else None

    @staticmethod
    def get_coords(element):
        if element is None or not element["visible"] or not element["enabled"]:
            raise RuntimeError("Element is not visible and enabled")
        left, top, right, bottom = element["rect"]
        if right <= left or bottom <= top:
            raise RuntimeError("Element has no visible screen area")
        return ((left + right) // 2, (top + bottom) // 2)

    # Mouse: no application-specific decisions or direct window-state APIs.
    def move_and_click(
        self, x, y, button="right", scroll=0, clicks=1, expected_window=None
    ):
        if button not in ("left", "right", None):
            raise ValueError("button must be 'left', 'right', or None")
        if not isinstance(scroll, int):
            raise TypeError("scroll must be an integer number of wheel steps")
        if not isinstance(clicks, int) or clicks < 1:
            raise ValueError("clicks must be a positive integer")
        self.timing.delay()
        self._check_foreground(expected_window)
        pyautogui.moveTo(x, y, duration=0.5)
        self._check_foreground(expected_window)
        if button is not None:
            pyautogui.click(button=button, clicks=clicks, interval=0.15)
        if scroll:
            pyautogui.scroll(scroll)

    @staticmethod
    def _check_foreground(expected_window):
        if expected_window is not None and win32gui.GetForegroundWindow() != expected_window:
            raise RuntimeError("Foreground window changed before mouse action")

    # Keyboard: input goes to the focused control.
    def press_keys(self, *keys, expected_window=None):
        self._check_foreground(expected_window)
        pyautogui.hotkey(*keys)

    def type_text(self, text, expected_window=None):
        if not text.isascii():
            raise ValueError("This keyboard input implementation supports ASCII text only")
        for char in text:
            self.timing.delay()
            self._check_foreground(expected_window)
            pyautogui.write(char)
