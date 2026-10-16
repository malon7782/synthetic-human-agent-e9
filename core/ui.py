import math
import random
import ctypes
from ctypes import wintypes
import pyautogui
import time
from contextlib import contextmanager
from pywinauto import Desktop
from core.text_corpus import TEXT_CORPUS, SEARCH_PARTS

VK_MAP = {'win': 0x5B, 'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10,
          'esc': 0x1B, 'enter': 0x0D, 'tab': 0x09}

# {'a': 65, 'b': 66, 'c': 67....}
VK_MAP.update({c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"})
KEYEVENTF_KEYUP = 0x0002


def sample_axis(start, stop, rng):
    """sampling in [start, stop); the weights of two sites are zero"""
    if stop - start < 3:
        raise ValueError("sampling area too small")

    positions = range(start, stop)

    weights = [
        ((p - start) * (stop - 1 - p)) ** 2
        for p in positions
    ]

    return rng.choices(positions, weights=weights, k=1)[0]


class UI:
    def __init__(self, timing, rng=None):
        self.timing = timing
        self.rng = rng if rng is not None else random.Random()
        self.desktop_icons = {}

    def fetch_desktop(self):
        # Locate the desktop icon list
        desktop = Desktop(backend="uia")
        icon_list = desktop.window(
            class_name="Progman"
        ).child_window(
            auto_id="1",
            control_type="List",
        ).wrapper_object()

        # Access the same list through the Win32 backend
        list_view = Desktop(backend="win32").window(
            handle=icon_list.handle
        ).wrapper_object()

        icons = {}

        for index in range(list_view.item_count()):
            item = list_view.get_item(index)
            name = item.text()

            # convert the icon bounds to screen coordinates
            rect = item.rectangle(area="icon")
            left, top = list_view.client_to_screen(
                (rect.left, rect.top)
            )
            right, bottom = list_view.client_to_screen(
                (rect.right, rect.bottom)
            )

            # Cache the bounds, without sampling a point yet
            icons[name] = (left, top, right, bottom)

        self.desktop_icons = icons

    def get_coords_desktop(self, element_id):
        left, top, right, bottom = self.desktop_icons[element_id]

        x = sample_axis(left, right, self.rng)
        y = sample_axis(top, bottom, self.rng)

        return x, y

    def curve_move(self, x, y, correction=True):
        """Move toward the supplied screen coordinates without clicking."""
        self.timing.check()
        if x is None or y is None:
            raise ValueError("curve_move requires both x and y coordinates")

        screen_width, screen_height = pyautogui.size()

        def curve_step_delay(self, progress):
            """Pause briefly between curve points, with slower endpoints."""
            if not 0 < progress <= 1:
                raise ValueError("progress must be in (0, 1]")

            speed = 0.45 + 0.55 * math.sin(math.pi * progress)
            time.sleep(random.uniform(0.004, 0.008) / speed)

        def correction_pause(self):
            """Pause briefly before correcting an intentionally inaccurate move."""
            time.sleep(random.uniform(0.1, 0.3))

        def clamp(point_x, point_y):
            inset = 2
            return (
                max(inset, min(screen_width - 1 - inset, point_x)),
                max(inset, min(screen_height - 1 - inset, point_y)),
            )

        def curve_points(start, end, bend_ratio):
            dx, dy = end[0] - start[0], end[1] - start[1]
            distance = math.hypot(dx, dy)
            if distance < 2:
                return [end]

            # A perpendicular offset creates a shallow quadratic Bezier arc.
            normal_x, normal_y = -dy / distance, dx / distance
            bend = self.rng.uniform(-bend_ratio, bend_ratio) * distance
            control = (
                (start[0] + end[0]) / 2 + normal_x * bend,
                (start[1] + end[1]) / 2 + normal_y * bend,
            )
            steps = max(12, min(30, round(distance / 25)))
            return [
                (
                    (1 - t) ** 2 * start[0]
                    + 2 * (1 - t) * t * control[0]
                    + t ** 2 * end[0],
                    (1 - t) ** 2 * start[1]
                    + 2 * (1 - t) * t * control[1]
                    + t ** 2 * end[1],
                )
                for t in (index / steps for index in range(1, steps + 1))
            ]

        def move_points(points):
            point_count = len(points)
            original_pause = pyautogui.PAUSE
            try:
                # PyAutoGUI normally waits after every public call.  Curve
                # points use the short timing policy below instead.
                pyautogui.PAUSE = 0
                for index, point in enumerate(points, start=1):
                    self.timing.check()
                    progress = index / point_count
                    point_x, point_y = clamp(round(point[0]), round(point[1]))
                    pyautogui.moveTo(point_x, point_y, duration=0)
                    self.timing.curve_step_delay(progress)
            finally:
                pyautogui.PAUSE = original_pause

        current = pyautogui.position()
        start = (current.x, current.y)

        if math.hypot(x - start[0], y - start[1]) < 3:
            return

        if not correction:
            target = clamp(x, y)
            move_points(curve_points(
                start,
                target,
                bend_ratio=self.rng.uniform(0.015, 0.055),
            ))
            return

        # Use the shorter screen dimension so the circular area stays a
        # 5% radius regardless of aspect ratio.
        radius = 0.05 * min(screen_width, screen_height)
        angle = self.rng.uniform(0, 2 * math.pi)
        distance = radius * math.sqrt(self.rng.random())
        approach = clamp(
            x + distance * math.cos(angle),
            y + distance * math.sin(angle),
        )

        move_points(curve_points(start, approach, bend_ratio=0.04))
        self.timing.correction_pause()
        # The final, shorter leg uses less curvature and lands exactly on
        # the supplied target before the caller performs any action.
        move_points(curve_points(approach, (x, y), bend_ratio=0.02))

    def move_and_click(self, x, y, button="left", end_x=None, end_y=None, scroll=0):
        # button: left, double, drag, scroll, middle, right.
        # For drag, (x, y) is the start and (end_x, end_y) is the end.
        # For scroll, positive values scroll up and negative values scroll down.
        if button not in ("left", "double", "drag", "scroll", "middle", "right", "move"):
            raise ValueError(
                "button must be left, double, drag, scroll, middle, or right")
        if button == "drag" and (end_x is None or end_y is None):
            raise ValueError("drag requires end_x and end_y")

        self.timing.delay()
        self.curve_move(x, y)
        self.timing.delay()
        if button == "double":
            pyautogui.doubleClick(interval=0.1, button="left")
        elif button == "drag":
            pyautogui.mouseDown(button="left")
            try:
                pyautogui.moveTo(end_x, end_y, duration=0.3)
            finally:
                pyautogui.mouseUp(button="left")
        elif button == "scroll":
            pyautogui.scroll(scroll)
        elif button == "move":
            pass
        else:
            pyautogui.click(button=button)

    def click_window_button(self, action):
        """Click a title-bar button on the active window by action name."""
        button_names = {
            "minimize": ("Minimize", "最小化"),
            "maximize": ("Maximize", "最大化"),
            "restore": ("Restore", "还原"),
            "close": ("Close", "关闭"),
        }
        try:
            wanted = {name.casefold() for name in button_names[action.casefold()]}
        except KeyError as error:
            raise ValueError(f"Unsupported window action: {action}") from error
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        handle = user32.GetForegroundWindow()
        window_spec = Desktop(backend="uia").window(handle=handle)
        window = window_spec.wrapper_object()
        window_rect = window.rectangle()
        title_bars = window.descendants(control_type="TitleBar")
        roots = title_bars + [window]
        labels = []
        matches = []
        for root in roots:
            for button in root.descendants(control_type="Button"):
                try:
                    if not button.is_visible():
                        continue
                    label = button.window_text().replace("&", "").strip().casefold()
                    rect = button.rectangle()
                    labels.append(f"{label}@({rect.left},{rect.top},{rect.right},{rect.bottom})")
                    if (
                        label in wanted
                        and rect.top <= window_rect.top + 120
                        and rect.right >= window_rect.right - 240
                    ):
                        matches.append((rect.right, button, rect))
                except Exception:
                    continue
        if not matches:
            raise RuntimeError(
                f"Could not find the {action} title-bar button on {window.window_text()!r}; "
                f"visible buttons: {', '.join(labels)}"
            )

        _, button, rect = max(matches, key=lambda match: match[0])
        x = sample_axis(rect.left, rect.right, self.rng)
        y = sample_axis(rect.top, rect.bottom, self.rng)
        self.move_and_click(x, y)
        return button

    def click_context_menu_item(self, name):
        """Find a named context-menu item and click it via curve_move."""
        self.timing.pause()
        desktop = Desktop(backend="uia")
        roots = []
        try:
            roots.append(desktop.window(class_name="Progman").wrapper_object())
        except Exception:
            pass
        roots.extend(desktop.windows())

        wanted = name.casefold()
        labels = []
        seen = set()
        for root in roots:
            try:
                controls = root.descendants()
            except Exception:
                continue
            for control in controls:
                try:
                    key = (control.element_info.handle, tuple(control.element_info.runtime_id or ()))
                    if key in seen or not control.is_visible():
                        continue
                    seen.add(key)
                    label = control.window_text().replace("&", "").strip().casefold()
                    if label:
                        labels.append(label)
                except Exception:
                    continue
                if label == wanted:
                    rect = control.rectangle()
                    x = sample_axis(rect.left, rect.right, self.rng)
                    y = sample_axis(rect.top, rect.bottom, self.rng)
                    # Input/cancellation errors must escape the UIA discovery loop.
                    self.move_and_click(x, y)
                    return control
        raise RuntimeError(
            f"Could not find visible context-menu item {name}; "
            f"visible labels: {', '.join(dict.fromkeys(labels))[:1200]}"
        )

    def visible_windows(self):
        return Desktop(backend="uia").windows(visible_only=True)

    @staticmethod
    def desktop_directory():
        """Resolve the redirected Desktop through the Windows known-folder API."""
        from comtypes import GUID
        from win32com.shell import shellcon
        path = wintypes.LPWSTR()
        folder = GUID(shellcon.FOLDERID_Desktop)
        get_path = ctypes.OleDLL("shell32").SHGetKnownFolderPath
        get_path.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)]
        get_path.restype = ctypes.HRESULT
        get_path(ctypes.byref(folder), 0, None, ctypes.byref(path))
        try:
            return path.value
        finally:
            free = ctypes.windll.ole32.CoTaskMemFree
            free.argtypes = [ctypes.c_void_p]
            free(ctypes.cast(path, ctypes.c_void_p))

    def foreground_window(self):
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        return Desktop(backend="uia").window(handle=user32.GetForegroundWindow()).wrapper_object()

    def window_executable(self, window):
        """Read the selected window's actual process image, without title guesses."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        hwnd = window.handle
        pid = window.process_id()

        def process_error(api, code):
            error = ctypes.WinError(code)
            error.strerror = f"{error.strerror} ({api}; observed HWND={hwnd!r}, PID={pid})"
            return error

        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            raise process_error("OpenProcess", ctypes.get_last_error())
        try:
            size = wintypes.DWORD(32768)
            path = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                raise process_error("QueryFullProcessImageNameW", ctypes.get_last_error())
            return path.value.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(handle)

    def wait_until(self, predicate, description, timeout=15):
        deadline = time.monotonic() + timeout
        while True:
            self.timing.check()
            value = predicate()
            if value:
                return value
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for {description}")
            self.timing.sleep(min(0.2, max(0, deadline - time.monotonic())))

    def focus_window(self, window):
        self.timing.check()
        window.set_focus()
        self.wait_until(lambda: self.foreground_window().handle == window.handle,
                        f"window {window.handle} to receive focus", timeout=5)

    @staticmethod
    def control_id(control):
        get_id = ctypes.windll.user32.GetDlgCtrlID
        get_id.argtypes = [wintypes.HWND]
        get_id.restype = ctypes.c_int
        return get_id(control.handle)

    def wait_browser_document(self, window, url, timeout=30):
        """Wait on the live-observed Edge address edit and document root.

        This establishes an accessible loaded document, not network-idle or
        application readiness; certificate/error documents fail explicitly.
        """
        from urllib.parse import urlsplit
        wanted_host = urlsplit(url).hostname
        def ready():
            edits = [control for control in window.descendants(control_type="Edit")
                     if control.element_info.automation_id == "view_1017"]
            documents = [control for control in window.descendants(control_type="Document")
                         if control.element_info.automation_id == "RootWebArea"]
            if not edits or not documents:
                return False
            value = edits[0].get_value()
            parsed = urlsplit(value if "://" in value else "https://" + value)
            if parsed.hostname != wanted_host:
                return False
            document = documents[0]
            properties = document.legacy_properties()
            document_host = urlsplit(properties.get("Value", "")).hostname
            if document_host != wanted_host or properties.get("State", 0) & 0x800:
                return False
            if not document.is_visible() or not document.descendants():
                return False
            # Error-document headings can be exposed only in descendant text,
            # while the document's own name remains the requested URL.
            texts = []
            for control in [document] + document.descendants():
                texts.append(control.window_text())
                try:
                    texts.append(control.iface_text.DocumentRange.GetText(-1))
                except Exception:
                    # Many controls do not implement the UIA Text pattern.
                    continue
            accessible = "\n".join(texts).casefold()
            warnings = ("privacy error", "can't reach this page", "certificate error", "your connection isn't private", "your connection is not private", "net::err_")
            if any(text in accessible for text in warnings):
                raise RuntimeError(f"Edge exposed an error/warning document at {url}")
            return document
        return self.wait_until(ready, f"Edge document at {url}", timeout)

    def ensure_english_keyboard(self, timeout=5):
        """Select an installed English HKL and confirm the target accepted it.

        WM_INPUTLANGCHANGEREQUEST is asynchronous. Poll the actual foreground
        thread instead of cycling languages or assuming a fixed delay suffices.
        Abort if another window takes focus rather than typing into that window.
        """
        self.timing.check()
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        user32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        user32.GetKeyboardLayoutList.restype = ctypes.c_int
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
        user32.PostMessageW.restype = wintypes.BOOL

        window = user32.GetForegroundWindow()
        if not window:
            raise RuntimeError("No foreground window for keyboard preparation")

        def english_is_active():
            if user32.GetForegroundWindow() != window:
                raise RuntimeError("Foreground window changed during keyboard preparation")
            thread = user32.GetWindowThreadProcessId(window, None)
            if not thread:
                raise RuntimeError("Could not obtain the foreground window thread")
            return ((user32.GetKeyboardLayout(thread) or 0) & 0x3FF) == 0x09

        if english_is_active():
            return window

        count = user32.GetKeyboardLayoutList(0, None)
        if count <= 0:
            raise RuntimeError("Could not enumerate installed keyboard layouts")
        layouts = (ctypes.c_void_p * count)()
        copied = user32.GetKeyboardLayoutList(count, layouts)
        english = next((layout for layout in layouts[:copied]
                        if layout and layout & 0x3FF == 0x09), None)
        if english is None:
            raise RuntimeError("No installed English keyboard layout")
        if user32.GetForegroundWindow() != window:
            raise RuntimeError("Foreground window changed during keyboard preparation")
        # Use the exact enumerated handle; do not load layouts or modify settings.
        if not user32.PostMessageW(window, 0x0050, 0, english):
            raise RuntimeError("Could not request the installed English keyboard layout")
        self.wait_until(english_is_active, "foreground English keyboard layout", timeout)
        return window

    def type_text(self, text):
        window = self.ensure_english_keyboard()

        for char in text:
            self.timing.delay()
            self._check_typing_target(window)
            pyautogui.write(char)

    def _check_typing_target(self, window):
        """Check immediately before every text/backspace event, after delays."""
        self.timing.check()
        if ctypes.windll.user32.GetForegroundWindow() != window:
            raise RuntimeError("Foreground window changed before typing")

    def is_on_desktop(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        name = ctypes.create_unicode_buffer(64)
        ctypes.windll.user32.GetClassNameW(hwnd, name, 64)
        # name of the Desktop should be either Program or WorkerW
        return name.value in ("Progman", "WorkerW")

    def center_of_desktop(self, range="mid"):
        x = ctypes.windll.user32.GetSystemMetrics(0)
        y = ctypes.windll.user32.GetSystemMetrics(1)
        xLow, xHigh = 0.25 * x, 0.75 * x
        yLow, yHigh = 0.25 * y, 0.75 * y
        if range == "mid":
            return (0.5 * random.random() + 0.25)*x, (0.5 * random.random() + 0.25)*y

    def choose_text(self, category, rng=None):
        rng = rng if rng is not None else random

        if category not in TEXT_CORPUS:
            raise ValueError(f"Unknown text category: {category}")

        if not TEXT_CORPUS[category]:
            raise ValueError(f"No texts in category: {category}")

        if category == "search" and rng.random() < 0:
            category = "thoughts"

        text = rng.choice(TEXT_CORPUS[category])

        if category == "search":
            text = text.format(**{
                name: rng.choice(options)
                for name, options in SEARCH_PARTS.items()
                if "{" + name + "}" in text
            })

        return text.strip()

    def typo(self, char, next_char=None, *, target_window=None):
        letters = "abcdefghijklmnopqrstuvwxyz"

        if char.lower() not in letters or len(char) != 1:
            raise ValueError("typo expects one ASCII letter")

        if target_window is None:
            target_window = self.ensure_english_keyboard()

        modes = ["replace", "repeat"]
        weights = [0.1, 0.3]

        pair_available = (
            next_char is not None
            and len(next_char) == 1
            and next_char.lower() in letters
        )

        if pair_available:
            modes.append("omit")
            weights.append(0.3)

            if next_char != char:
                modes.append("swap")
                weights.append(0.3)

        mode = self.rng.choices(
            modes,
            weights=weights,
            k=1
        )[0]

        if mode == "replace":
            correct = char
            wrong = self.rng.choice(
                letters.replace(char.lower(), "")
            )

            if char.isupper():
                wrong = wrong.upper()

        elif mode == "repeat":
            correct = char
            wrong = char*2

        elif mode == "swap":
            correct = char + next_char
            wrong = next_char + char

        else:
            correct = char + next_char
            wrong = next_char

        for typed_char in wrong:
            self.timing.typing_delay(typed_char)
            self._check_typing_target(target_window)
            pyautogui.write(typed_char)

        self.timing.delay()

        if mode == "repeat":
            self._check_typing_target(target_window)
            pyautogui.press("backspace")
            self.timing.delay()

            return len(correct)

        for _ in wrong:
            self._check_typing_target(target_window)
            pyautogui.press("backspace")
            self.timing.delay()

        for typed_char in correct:
            self.timing.typing_delay(typed_char)
            self._check_typing_target(target_window)
            pyautogui.write(typed_char)

        return len(correct)

    def type_from_corpus(self, category="search", typo_rate=0.2):
        if not 0 <= typo_rate <= 1:
            raise ValueError("typo_rate must be between 0 and 1")

        text = self.choose_text(category, rng=self.rng)

        target_window = self.ensure_english_keyboard()

        index = 0

        while index < len(text):
            char = text[index]

            if (
                char in "abcdefghijklmnopqrstuvwxyz" and self.rng.random() < typo_rate
            ):
                next_char = (
                    text[index + 1]
                    if index + 1 < len(text)
                    else None
                )

                consumed = self.typo(char, next_char, target_window=target_window)
                index += consumed

            else:
                self.timing.typing_delay(char)
                self._check_typing_target(target_window)
                pyautogui.write(char)
                index += 1

        return text
        if range == "mid" :
            return (0.5 * random.random() + 0.25)*x, (0.5 * random.random() + 0.25)*y

    def press(self, *keys):
        self.timing.check()
        return pyautogui.press(list(keys))

    def hotkey(self, *keys):
        self.timing.check()
        return pyautogui.hotkey(list(keys))

    def key_down(self, key):
        self.timing.check()
        return pyautogui.keyDown(key)

    def key_up(self, key):
        self.timing.check()
        return pyautogui.keyUp(key)

    def screen_size(self):
        return pyautogui.size()

    def mouse_position(self):
        return pyautogui.position()

    def move_to(self, x, y, duration=0):
        """Move directly to a trajectory point without adding a curve."""
        self.timing.check()
        return pyautogui.moveTo(x, y, duration=duration)

    @contextmanager
    def without_mouse_pause(self):
        """Let a timed trajectory manage its own delays; restore on exit."""
        original_pause = pyautogui.PAUSE
        try:
            pyautogui.PAUSE = 0
            yield
        finally:
            pyautogui.PAUSE = original_pause
