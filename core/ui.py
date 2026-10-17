import math
import random
import ctypes
import pyautogui
import time
from pathlib import Path
from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError
from pywinauto.uia_defines import NoPatternInterfaceError
from comtypes import COMError
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
            return (
                max(0, min(screen_width - 1, point_x)),
                max(0, min(screen_height - 1, point_y)),
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

        if button == "double":
            pyautogui.doubleClick(
                interval=self.rng.uniform(0.15, 0.3), button="left")
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

    def type_text(self, text):
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        window = user32.GetForegroundWindow()
        thread = user32.GetWindowThreadProcessId(ctypes.c_void_p(window), None)

        # Check English (0x09); Win+Space cycles through installed input languages.
        for _ in range(user32.GetKeyboardLayoutList(0, None)):
            if (user32.GetKeyboardLayout(thread) or 0) & 0x3FF == 0x09:
                break
            pyautogui.hotkey("win", "space")
            pyautogui.sleep(0.3)
        else:
            raise RuntimeError("Could not switch to an English keyboard")

        for char in text:
            self.timing.delay()
            pyautogui.write(char)

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

        text = rng.choice(TEXT_CORPUS[category])

        if category == "search":
            text = text.format(**{
                name: rng.choice(options)
                for name, options in SEARCH_PARTS.items()
                if "{" + name + "}" in text
            })

        return text.strip()

    def typo(self, char, next_char=None):
        letters = "abcdefghijklmnopqrstuvwxyz"

        if char.lower() not in letters or len(char) != 1:
            raise ValueError("typo expects one ASCII letter")

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
            pyautogui.write(typed_char)

        self.timing.delay()

        if mode == "repeat":
            pyautogui.press("backspace")
            self.timing.delay()

            return len(correct)

        for _ in wrong:
            pyautogui.press("backspace")
            self.timing.delay()

        for typed_char in correct:
            self.timing.typing_delay(typed_char)
            pyautogui.write(typed_char)

        return len(correct)

    def type_from_corpus(self, category="search", typo_rate=0.1):
        text = self.choose_text(category, rng=self.rng)

        self.type_text("")

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

                consumed = self.typo(char, next_char)
                index += consumed

            else:
                self.timing.typing_delay(char)
                pyautogui.write(char)
                index += 1

        return text

    def random_scroll(self, x, y, direction=None):
        """Scroll 400-600 notches; negative means down, positive means up."""
        if direction is None:
            direction = self.rng.choice((-1, 1))
        amount = direction * self.rng.randint(400, 600)
        self.move_and_click(x, y, "move")
        self.smooth_scroll(amount)
        self.timing.pause()

    def smooth_scroll(self, amount):
        """Mix irregular wheel bursts and pauses, preserving total distance."""
        fast = self.rng.random() < 0.45
        steps = self.rng.randint(6, 12) if fast else self.rng.randint(16, 28)
        weights = [self.rng.uniform(0.3, 1.8) for _ in range(steps)]
        # A sudden burst can occur anywhere, rather than always in the middle.
        weights[self.rng.randrange(steps)] *= self.rng.uniform(2, 4)
        total = sum(weights)
        accumulated = 0
        previous = 0
        move_at = self.rng.randrange(
            1, steps) if self.rng.random() < 0.4 else None
        original_pause = pyautogui.PAUSE
        try:
            pyautogui.PAUSE = 0
            for index, weight in enumerate(weights, start=1):
                accumulated += weight
                position = amount if index == steps else round(
                    amount * accumulated / total)
                if position != previous:
                    pyautogui.scroll(position - previous)
                previous = position
                time.sleep(self.rng.uniform(0.012, 0.035) if fast
                           else self.rng.uniform(0.04, 0.10))
                if self.rng.random() < 0.12:
                    self.timing.delay()
                if index == move_at:
                    self.browse_mouse(1)
        finally:
            pyautogui.PAUSE = original_pause

    def browse_mouse(self, count=None):
        """Move across page content without clicking links or browser controls."""
        width, height = pyautogui.size()
        for _ in range(count if count is not None else self.rng.randint(1, 3)):
            x = round(width * self.rng.uniform(0.18, 0.80))
            y = round(height * self.rng.uniform(0.25, 0.82))
            self.move_and_click(x, y, "move")
            self.timing.delay()

    def scroll_page(self, x, y):
        self.random_scroll(x, y, -1)
        self.browse_mouse()
        self.random_scroll(*pyautogui.position())
        for index, probability in enumerate((0.8, 0.6, 0.4, 0.2), start=3):
            if self.rng.random() >= probability:
                break
            self.browse_mouse()
            self.random_scroll(*pyautogui.position(),
                               direction=-1 if index == 3 else None)
        self.browse_mouse()

    def close_window(self):
        """Click the upper-right X of the maximized foreground window."""
        width, _ = pyautogui.size()
        # No overshoot near a screen corner: keep the existing fail-safe intact.
        self.curve_move(width - 25, 15, correction=False)
        self.timing.delay()
        pyautogui.click()
        self.timing.delay()

    def maximize_browser(self):
        """Wait for Edge, then maximize explicitly instead of using Win+Up."""
        def edge_window():
            window = self.foreground_window()
            title = window.window_text().replace("\u200b", "")
            if window.class_name() == "Chrome_WidgetWin_1" and title.endswith("Microsoft Edge"):
                return window
            return None

        window = self.wait_until(
            edge_window, "Microsoft Edge to become active")
        self.maximize_window(window)

    def maximize_window(self, window):
        """Use the native maximized state, avoiding snap-related keyboard shortcuts."""
        window.set_focus()
        window.maximize()
        self.wait_until(window.is_maximized, "window to maximize")
        self.timing.delay()

    def foreground_window(self, backend="win32"):
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        handle = user32.GetForegroundWindow()
        if not handle:
            raise ElementNotFoundError(
                "No foreground window during transition")
        return Desktop(backend=backend).window(handle=handle).wrapper_object()

    def edge_has_internet(self, timeout=8, *, check_page=True):
        """Check Windows connectivity and Edge's visible network-error page.

        Uses the browser's actual page, without probing an unrelated public site.
        A connected adapter alone is not proof that the Internet is reachable.
        """
        flags = ctypes.c_ulong()
        if not ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0):
            return False
        if not check_page:
            # Before searching, only check an explicitly disconnected adapter.
            return True
        errors = ("err_internet_disconnected", "err_name_not_resolved",
                  "err_connection_timed_out", "err_connection_refused",
                  "dns_probe_finished_no_internet", "dns_probe_finished_nxdomain",
                  "you're not connected", "you’re not connected", "你未连接", "未连接到 internet")
        end = time.monotonic() + timeout
        observed = False
        while time.monotonic() < end:
            pyautogui.failSafeCheck()
            try:
                for document in self.foreground_window(backend="uia").descendants(control_type="Document"):
                    text = " ".join(control.window_text() for control in [
                                    document] + document.descendants())
                    observed = True
                    if any(error in text.casefold() for error in errors):
                        return False
            except (COMError, ElementNotFoundError):
                pass  # Edge may replace its UIA tree during navigation.
            time.sleep(0.5)
        if not observed:
            raise RuntimeError(
                "Cannot read Edge's page; network status is unknown")
        return True

    def wait_until(self, predicate, description, timeout=10):
        end = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < end:
            pyautogui.failSafeCheck()
            try:
                result = predicate()
                if result:
                    return result
            except (COMError, ElementNotFoundError) as error:
                last_error = error
            time.sleep(0.2)
        raise RuntimeError(
            f"Timed out waiting for {description}") from last_error

    def click_context_menu_item(self, *names, process_id, expand=False):
        """Act on an exact Explorer menu item, never a cached screen position."""
        wanted = {name.casefold() for name in names}

        def find_item():
            desktop = Desktop(backend="uia")
            roots = desktop.windows(process=process_id)
            # Explorer sometimes attaches its menu to the desktop, not a popup.
            for class_name in ("Progman", "WorkerW"):
                roots.extend(desktop.windows(
                    process=process_id, class_name=class_name, visible_only=False))
            matches = {}
            for root in roots:
                try:
                    menus = (
                        [root] if root.element_info.control_type == "Menu" else [])
                    menus += root.descendants(control_type="Menu")
                    for menu in menus:
                        # Windows 11 can mark the host Menu offscreen while its
                        # actual MenuItems are visible. Validate the item itself.
                        for control in menu.descendants(control_type="MenuItem"):
                            label = control.window_text().replace("&", "").strip().casefold()
                            if (label in wanted and control.is_visible() and control.is_enabled()
                                    and control.process_id() == process_id):
                                # Deduplicate menus exposed through multiple desktop roots.
                                identity = tuple(
                                    control.element_info.runtime_id or ())
                                if not identity:
                                    raise RuntimeError(
                                        "Menu item has no stable UIA identity")
                                matches[identity] = control
                except (COMError, ElementNotFoundError):
                    continue
            if len(matches) > 1:
                raise RuntimeError(f"Ambiguous context menu item: {names}")
            return next(iter(matches.values()), None)

        control = self.wait_until(find_item, f"Explorer menu item {names}")
        pyautogui.failSafeCheck()
        # Revalidate the same control immediately before acting; no mouse fallback.
        if (self.foreground_window().process_id() != process_id
                or control.process_id() != process_id
                or control.element_info.control_type != "MenuItem"
                or control.window_text().replace("&", "").strip().casefold() not in wanted
                or not control.is_visible() or not control.is_enabled()):
            raise RuntimeError("Context menu changed before the action")
        if expand:
            try:
                control.expand()
            except NoPatternInterfaceError:
                # Some Explorer versions expose New as Invoke only.
                control.invoke()
        else:
            control.invoke()
        self.timing.delay()

    def new_text_document(self):
        """Use desktop right-click > New > Text Document, as in the teammate version."""
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            desktop = Path(winreg.ExpandEnvironmentStrings(
                winreg.QueryValueEx(key, "Desktop")[0]))
        if not self.is_on_desktop():
            pyautogui.hotkey("win", "d")
            self.timing.pause()
        self.wait_until(self.is_on_desktop, "desktop to receive focus")
        self.wait_until(lambda: self.fetch_desktop() or True, "desktop icons")
        width, height = pyautogui.size()
        point = next(((round(width * x), round(height * y))
                      for x in (0.7, 0.8, 0.6, 0.9) for y in (0.55, 0.45, 0.65)
                      if all(not (left - 70 <= width * x <= right + 70 and
                                  top - 45 <= height * y <= bottom + 45)
                             for left, top, right, bottom in self.desktop_icons.values())), None)
        if point is None:
            raise RuntimeError("No clear desktop area for a new text document")
        previous = set(desktop.iterdir())
        desktop_window = self.foreground_window()
        if desktop_window.class_name() not in ("Progman", "WorkerW"):
            print("TXT creation skipped: desktop lost focus before right-click")
            return None
        process_id = desktop_window.process_id()
        pyautogui.press("esc")
        self.move_and_click(*point, "right")

        def created():
            files = [path for path in set(desktop.iterdir()) - previous
                     if path.suffix.lower() == ".txt" and path.is_file()]
            return files[0] if len(files) == 1 and files[0].stat().st_size == 0 else None

        try:
            self.timing.delay()
            self.click_context_menu_item("New", "新建", "新建(W)",
                                         process_id=process_id, expand=True)
            self.timing.delay()
            self.click_context_menu_item("Text Document", "文本文档",
                                         process_id=process_id)
            # Check creation before Enter; never send Enter to an unexpected menu.
            path = self.wait_until(created, "one new empty desktop TXT")
            self.timing.delay()
            if self.foreground_window().process_id() != process_id:
                raise RuntimeError("Desktop lost focus while creating the TXT")
            # Finish the default filename, preserving .txt.
            pyautogui.press("enter")
            self.timing.pause()
            return path
        except (RuntimeError, COMError, ElementNotFoundError, NoPatternInterfaceError) as error:
            try:
                if self.foreground_window().process_id() == process_id:
                    pyautogui.press("esc", presses=2, interval=0.1)
            except (COMError, ElementNotFoundError):
                pass
            print(f"TXT creation skipped: {error}")
            return None

    def save_new_document(self, path):
        process_id = self.foreground_window().process_id()
        pyautogui.hotkey("ctrl", "shift", "s")
        dialog = self.wait_until(
            lambda: (window if (window := self.foreground_window()
                                ).process_id() == process_id
                     and window.class_name() == "#32770"
                     and window.window_text().strip().casefold() in ("save as", "另存为") else None),
            "Notepad Save As dialog")
        dialog.set_focus()
        # Standard Windows Save As filename edit; quoted paths preserve .py.
        filename = Desktop(backend="win32").window(handle=dialog.handle).child_window(
            class_name="Edit", control_id=1001).wrapper_object()
        filename.set_focus()
        filename.set_edit_text('"' + str(path) + '"')
        pyautogui.press("enter")
        self.wait_until(path.is_file, f"new desktop file {path.name}")
        self.wait_until(lambda: self.foreground_window().handle !=
                        dialog.handle, "Save As to close")

    def prepare_document_keyboard(self, editor):
        """Select an installed English layout before calling the original typing API."""
        user32 = ctypes.windll.user32
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        count = user32.GetKeyboardLayoutList(0, None)
        layouts = (ctypes.c_void_p * count)()
        user32.GetKeyboardLayoutList(count, layouts)
        english = next(
            (layout for layout in layouts if layout and layout & 0x3FF == 0x09), None)
        if english is None:
            raise RuntimeError("No installed English keyboard layout")
        editor.set_focus()
        thread = user32.GetWindowThreadProcessId(
            ctypes.c_void_p(editor.handle), None)
        if not user32.PostMessageW(ctypes.c_void_p(editor.handle), 0x0050, 0, ctypes.c_ssize_t(english)):
            raise RuntimeError(
                "Could not request the installed English keyboard")
        self.wait_until(lambda: (user32.GetKeyboardLayout(thread) or 0) & 0x3FF == 0x09,
                        "English keyboard for the document", timeout=5)

    def write_desktop_document(self, stem, suffix=".txt", count=1, text=None):
        """Create a desktop TXT, double-click it, write through existing typing APIs."""
        path = self.new_text_document()
        if path is None:
            return None

        def document_icon():
            self.fetch_desktop()
            return next((name for name in (path.name, path.stem) if name in self.desktop_icons), None)

        icon = self.wait_until(document_icon, f"desktop icon {path.name}")
        self.move_and_click(*self.get_coords_desktop(icon), "double")
        editor = self.wait_until(
            lambda: (window if (window := self.foreground_window()).class_name() == "Notepad"
                     and any(window.window_text().startswith(name + " - ") for name in (path.name, path.stem)) else None),
            f"Notepad showing {path.name}")
        self.maximize_window(editor)
        self.prepare_document_keyboard(editor)
        self.timing.pause()
        lines = []
        for index in range(count):
            if index:
                pyautogui.press("enter")
                self.timing.pause()
            if text is None:
                lines.append(self.type_from_corpus("sentence"))
            else:
                self.type_text(text)
                lines.append(text)
        pyautogui.hotkey("ctrl", "s")
        expected = "\n".join(lines)

        def saved():
            try:
                return path.read_text(encoding="utf-8-sig").rstrip("\n") == expected
            except (OSError, UnicodeError):
                return False

        self.wait_until(saved, f"saved writing in {path.name}")
        editor.set_focus()
        if suffix != ".txt":
            target = path.with_name(stem + suffix)
            number = 2
            while target.exists():
                target = path.with_name(f"{stem}_{number}{suffix}")
                number += 1
            self.save_new_document(target)
            path = target
            self.wait_until(saved, f"saved script in {path.name}")
            editor.set_focus()
        self.timing.pause()
        pyautogui.hotkey("ctrl", "w")
        return path

    def write_sentences(self):
        count = self.rng.choices(
            (3, 4, 5, 6, 7, 8, 9, 10, 11), weights=(2, 3, 5, 8, 12, 8, 5, 3, 2), k=1)[0]
        return self.write_desktop_document("notes", count=count)

    def write_hello_world(self):
        # Write a script directly; do not rename an extension or execute it.
        return self.write_desktop_document("helloworld", ".py", text='print("Hello, world!")')
