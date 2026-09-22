import math
import random
import ctypes
import pyautogui
import time
from pywinauto import Desktop

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
            raise ValueError("button must be left, double, drag, scroll, middle, or right")
        if button == "drag" and (end_x is None or end_y is None):
            raise ValueError("drag requires end_x and end_y")

        self.timing.delay()
        self.curve_move(x, y)

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
        if range == "mid" :
            return (0.5 * random.random() + 0.25)*x, (0.5 * random.random() + 0.25)*y

    def press(self, *keys):
        return pyautogui.press(list(keys))

    def hotkey(self, *keys):
        return pyautogui.hotkey(list(keys))