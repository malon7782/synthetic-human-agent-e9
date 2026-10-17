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
        self.desktop_item_bounds = []
        self.desktop_item_bounds_by_name = {}
        self.last_created_text_path = None

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
        # LVM_GETITEMSPACING: use Explorer's actual grid (including DPI/view size).
        spacing = list_view.send_message(0x1033, 0, 0)
        self.desktop_grid_spacing = (spacing & 0xFFFF, (spacing >> 16) & 0xFFFF)

        icons = {}
        item_bounds = []
        bounds_by_name = {}

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
            full_rect = item.rectangle(area="all")
            full_left, full_top = list_view.client_to_screen(
                (full_rect.left, full_rect.top))
            full_right, full_bottom = list_view.client_to_screen(
                (full_rect.right, full_rect.bottom))
            item_bounds.append((full_left, full_top, full_right, full_bottom))
            bounds_by_name[name] = item_bounds[-1]

        self.desktop_icons = icons
        self.desktop_item_bounds = item_bounds
        self.desktop_item_bounds_by_name = bounds_by_name

    def desktop_work_area(self):
        """Primary desktop bounds, excluding taskbar and screen-edge fail-safes."""
        from ctypes import wintypes
        work = wintypes.RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):
            raise RuntimeError("Cannot read desktop work area")
        width, height = pyautogui.size()
        return (max(8, work.left + 8), max(8, work.top + 8),
                min(width - 9, work.right - 9), min(height - 9, work.bottom - 9))

    def desktop_creation_point(self, *, ordered=False, exclude_name=None):
        """Choose a free icon-sized slot: column order or corner-weighted."""
        if ordered:
            return self.first_free_desktop_slot(exclude_name)
        left, top, right, bottom = self.desktop_work_area()
        items = (self.desktop_item_bounds if exclude_name is None else
                 [bounds for name, bounds in self.desktop_item_bounds_by_name.items()
                  if name != exclude_name])
        # Respect Windows' configured icon spacing and the observed item sizes.
        cell_w = max(ctypes.windll.user32.GetSystemMetrics(38),
                     max((r - l for l, t, r, b in items), default=64) + 8)
        cell_h = max(ctypes.windll.user32.GetSystemMetrics(39),
                     max((b - t for l, t, r, b in items), default=64) + 8)
        # Align the candidate grid with the existing top-left item, when present.
        x0 = max(left + cell_w / 2,
                 min((l for l, t, r, b in items if l >= left), default=left) + cell_w / 2)
        y0 = max(top + cell_h / 2,
                 min((t for l, t, r, b in items if t >= top), default=top) + cell_h / 2)
        columns = list(range(round(x0), round(right - cell_w / 2) + 1, cell_w))
        rows = list(range(round(y0), round(bottom - cell_h / 2) + 1, cell_h))
        if self.rng.choice((False, True)):
            columns.reverse()
        free = []
        for x in columns:
            for y in rows:
                # Reserve the full cell, including enough room for the filename.
                if all(x + cell_w / 2 < l or x - cell_w / 2 > r
                       or y + cell_h / 2 < t or y - cell_h / 2 > b
                       for l, t, r, b in items):
                    free.append((x, y))
        if not free:
            return None
        if self.rng.random() < 0.5:
            return free[0]  # Top to bottom, then the next inward column.
        # Keep random placement in the outer quarter; prioritize the corners.
        edge_slots = [(x, y) for x, y in free
                      if min(x - left, right - x) <= (right - left) / 4
                      or min(y - top, bottom - y) <= (bottom - top) / 4]
        if not edge_slots:
            return free[0]
        weights = [(1 - min(x - left, right - x) / (right - left)) ** 4
                   * (1 - min(y - top, bottom - y) / (bottom - top)) ** 4
                   for x, y in edge_slots]
        return self.rng.choices(edge_slots, weights=weights, k=1)[0]

    def first_free_desktop_slot(self, exclude_name):
        """Fill holes top-to-bottom in each column, starting at the left."""
        left, top, right, bottom = self.desktop_work_area()
        cell_w, cell_h = self.desktop_grid_spacing
        if cell_w <= 0 or cell_h <= 0:
            raise RuntimeError("Cannot read desktop icon grid spacing")
        centers = {name: ((l + r) / 2, (t + b) / 2)
                   for name, (l, t, r, b) in self.desktop_icons.items()
                   if left <= (l + r) / 2 <= right and top <= (t + b) / 2 <= bottom}
        if not centers:
            return None
        # Include the moving icon when finding the grid origin, but not occupancy.
        x0 = min(x for x, y in centers.values())
        y0 = min(y for x, y in centers.values())
        while x0 - cell_w >= left:
            x0 -= cell_w
        while y0 - cell_h >= top:
            y0 -= cell_h
        occupied = {(round((x - x0) / cell_w), round((y - y0) / cell_h))
                    for name, (x, y) in centers.items() if name != exclude_name}
        # Leave room for the icon and label without reserving an extra grid cell.
        right_margin = max(self.desktop_item_bounds_by_name[name][2] - x
                           for name, (x, y) in centers.items())
        bottom_margin = max(self.desktop_item_bounds_by_name[name][3] - y
                            for name, (x, y) in centers.items())
        columns = max(0, math.floor((right - right_margin - x0) / cell_w) + 1)
        rows = max(0, math.floor((bottom - bottom_margin - y0) / cell_h) + 1)
        for column in range(columns):
            for row in range(rows):
                if (column, row) not in occupied:
                    return round(x0 + column * cell_w), round(y0 + row * cell_h)
        return None

    def play(self):
        """Draw one desktop selection, optionally moving its endpoint repeatedly."""
        min_side = math.ceil(min(pyautogui.size()) / 8)

        def center_axis(low, high, rng):
            """Flat maximum in the central half; linear falloff to zero at edges."""
            while True:
                fraction = rng.random()
                if rng.random() < min(1.0, 4 * fraction, 4 * (1 - fraction)):
                    return round(low + fraction * (high - low))

        def clear_rectangle(points, bounds, obstacles):
            left = min(point[0] for point in points)
            right = max(point[0] for point in points)
            top = min(point[1] for point in points)
            bottom = max(point[1] for point in points)
            if not (bounds[0] <= left <= right <= bounds[2]
                    and bounds[1] <= top <= bottom <= bounds[3]):
                return False
            return all(right < x1 or left > x2 or bottom < y1 or top > y2
                       for x1, y1, x2, y2 in obstacles)

        def continuation_probability(completed):
            """After endpoints 1..10, continuation falls linearly from 0.8 to 0."""
            return max(0.0, 0.8 * (10 - completed) / 9)

        def sample_endpoint(start, bounds, obstacles, rng, previous=None):
            # Keeping the same quadrant ensures intermediate aspect ratios are also
            # within the limits during a straight move between two endpoints.
            for _ in range(200):
                if previous is None:
                    sx, sy = rng.choice((-1, 1)), rng.choice((-1, 1))
                else:
                    sx = 1 if previous[0] > start[0] else -1
                    sy = 1 if previous[1] > start[1] else -1
                max_width = bounds[2] - \
                    start[0] if sx > 0 else start[0] - bounds[0]
                max_height = bounds[3] - \
                    start[1] if sy > 0 else start[1] - bounds[1]
                # Favor near-square shapes, but keep at least a 1.05 aspect ratio.
                # Preserve the long axis between endpoints to avoid crossing a square.
                wide = (rng.choice((False, True)) if previous is None else
                        abs(previous[0] - start[0]) > abs(previous[1] - start[1]))
                aspect = math.exp(rng.triangular(
                    math.log(1.05), math.log(5), math.log(1.05)))
                ratio = aspect if wide else 1 / aspect
                low = max(min_side, min_side / ratio)
                high = min(max_height, max_width / ratio)
                if high < low:
                    continue
                height = round(rng.uniform(low, high))
                width = round(height * ratio)
                if not (min(width, height) >= min_side and max(width, height) <= 5 * min(width, height)):
                    continue
                if 20 * max(width, height) < 21 * min(width, height):
                    continue
                end = start[0] + sx * width, start[1] + sy * height
                if previous is not None and math.dist(end, previous) < 12:
                    continue
                # This envelope contains every selection rectangle swept by the move.
                points = (start, end) if previous is None else (
                    start, previous, end)
                if clear_rectangle(points, bounds, obstacles):
                    return end
            return None

        def sample_selection(bounds, obstacles, rng):
            if bounds[2] - bounds[0] < min_side or bounds[3] - bounds[1] < min_side:
                return None
            for _ in range(200):
                start = (center_axis(bounds[0], bounds[2], rng),
                         center_axis(bounds[1], bounds[3], rng))
                if not clear_rectangle((start,), bounds, obstacles):
                    continue
                end = sample_endpoint(start, bounds, obstacles, rng)
                if end is not None:
                    return start, end
            return None

        if not self.is_on_desktop():
            pyautogui.hotkey("win", "d")
            self.timing.delay()
        self.wait_until(self.is_on_desktop, "desktop to receive focus")
        self.fetch_desktop()
        bounds = self.desktop_work_area()
        obstacles = [(left - 8, top - 8, right + 8, bottom + 8)
                     for left, top, right, bottom in self.desktop_item_bounds]
        selection = sample_selection(bounds, obstacles, self.rng)
        if selection is None:
            return False
        start, end = selection
        continuous = self.rng.choices((False, True), weights=(2, 3), k=1)[0]
        self.timing.delay()
        self.curve_move(*start, smooth=True,
                        speed_scale=self.rng.uniform(0.7, 0.8))
        if not self.is_on_desktop():
            return False
        try:
            pyautogui.mouseDown(button="left")
            for completed in range(1, 11):
                if not self.is_on_desktop():
                    return False

                def safe_path(points):
                    if not clear_rectangle((start, *points), bounds, obstacles):
                        return False
                    for px, py in points:
                        w, h = abs(px - start[0]), abs(py - start[1])
                        # The first drag necessarily grows from zero size.
                        if completed > 1 and min(w, h) < min_side:
                            return False
                        if min(w, h) >= min_side and 20 * max(w, h) < 21 * min(w, h):
                            return False
                        if min(w, h) >= 8 and max(w, h) > 5 * min(w, h):
                            return False
                    return True

                if self.curve_move(*end, correction=False, path_validator=safe_path,
                                   smooth=True, speed_scale=self.rng.uniform(0.7, 0.8)) is False:
                    return False
                self.timing.play_pause()
                if not continuous or self.rng.random() >= continuation_probability(completed):
                    break
                next_end = sample_endpoint(
                    start, bounds, obstacles, self.rng, previous=end)
                if next_end is None:
                    break
                self.timing.delay()
                end = next_end
        finally:
            # Release even when an exception or the corner fail-safe interrupts.
            original_failsafe = pyautogui.FAILSAFE
            try:
                pyautogui.FAILSAFE = False
                pyautogui.mouseUp(button="left")
            finally:
                pyautogui.FAILSAFE = original_failsafe
        return True

    def get_coords_desktop(self, element_id):
        left, top, right, bottom = self.desktop_icons[element_id]

        x = sample_axis(left, right, self.rng)
        y = sample_axis(top, bottom, self.rng)

        return x, y

    def curve_move(self, x, y, correction=True, path_validator=None, *,
                   smooth=False, speed_scale=1.0):
        """Move toward the supplied screen coordinates without clicking."""
        if x is None or y is None:
            raise ValueError("curve_move requires both x and y coordinates")
        if not math.isfinite(speed_scale) or speed_scale <= 0:
            raise ValueError("speed_scale must be positive and finite")

        screen_width, screen_height = pyautogui.size()

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
            if smooth:
                steps *= 2
            parameters = [index / steps for index in range(1, steps + 1)]
            if smooth:
                parameters = [t * t * (3 - 2 * t) for t in parameters]
            return [
                (
                    (1 - t) ** 2 * start[0]
                    + 2 * (1 - t) * t * control[0]
                    + t ** 2 * end[0],
                    (1 - t) ** 2 * start[1]
                    + 2 * (1 - t) * t * control[1]
                    + t ** 2 * end[1],
                )
                for t in parameters
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
                    # Offset denser sampling, then apply the requested speed scale.
                    self.timing.curve_step_delay(
                        progress, duration_scale=1 / ((2 if smooth else 1) * speed_scale))
            finally:
                pyautogui.PAUSE = original_pause

        current = pyautogui.position()
        start = (current.x, current.y)

        if path_validator is not None:
            target = clamp(x, y)
            # Validate the exact rounded path before pressing ahead. Reduce bend
            # near obstacles; the final fallback retains the same movement timing.
            for attempt in range(17):
                bend = self.rng.uniform(0.015, 0.055) if attempt < 16 else 0
                points = [clamp(round(px), round(py))
                          for px, py in curve_points(start, target, bend)]
                if path_validator([start, *points]):
                    move_points(points)
                    return True
            return False

        if math.hypot(x - start[0], y - start[1]) < 3:
            pyautogui.moveTo(*clamp(x, y))
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
                self.curve_move(end_x, end_y, correction=False)
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

    def typo(self, char, next_char=None, *, address_bar=False):
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

        def erase_character():
            if address_bar:
                # Inline completion is selected after the typed prefix. Delete
                # clears that suffix (or does nothing at the end) before Backspace.
                pyautogui.press("delete")
            pyautogui.press("backspace")

        if mode == "repeat":
            erase_character()
            self.timing.delay()

            return len(correct)

        for _ in wrong:
            erase_character()
            self.timing.delay()

        for typed_char in correct:
            self.timing.typing_delay(typed_char)
            pyautogui.write(typed_char)

        return len(correct)

    def type_from_corpus(self, category="search", typo_rate=0.1, *, address_bar=False):
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

                consumed = self.typo(char, next_char, address_bar=address_bar)
                index += consumed

            else:
                self.timing.typing_delay(char)
                pyautogui.write(char)
                index += 1

        if address_bar:
            # Submit the intended text, without an appended inline suggestion.
            pyautogui.press("delete")
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
        point = self.desktop_creation_point()
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
        self.timing.pause()
        process_id = self.foreground_window().process_id()
        pyautogui.hotkey("ctrl", "shift", "s")
        dialog = self.wait_until(
            lambda: (window if (window := self.foreground_window()
                                ).process_id() == process_id
                     and window.class_name() == "#32770"
                     and window.window_text().strip().casefold() in ("save as", "另存为") else None),
            "Notepad Save As dialog")
        dialog.set_focus()
        self.timing.pause()
        # Navigate using the portable shell folder name, even when the user's
        # desktop path contains characters PyAutoGUI cannot type (e.g. Chinese).
        pyautogui.hotkey("alt", "d")
        self.type_text("shell:Desktop")
        pyautogui.press("enter")
        self.timing.pause()
        # Type the filename visibly; quotes prevent Notepad appending .txt.
        filename = Desktop(backend="win32").window(handle=dialog.handle).child_window(
            class_name="Edit", control_id=1001).wrapper_object()
        filename.set_focus()
        pyautogui.hotkey("ctrl", "a")
        self.type_text('"' + path.name + '"')
        self.wait_until(lambda: filename.window_text() == '"' + path.name + '"',
                        "typed Save As filename")
        self.timing.pause()
        pyautogui.press("enter")
        self.wait_until(path.is_file, f"new desktop file {path.name}")
        self.wait_until(lambda: self.foreground_window().handle !=
                        dialog.handle, "Save As to close")
        self.timing.pause()

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
        self.last_created_text_path = None
        path = self.new_text_document()
        if path is None:
            return None
        self.last_created_text_path = path

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
        self.timing.pause()
        editor.set_focus()
        pyautogui.hotkey("ctrl", "s")
        self.timing.pause()
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
        # Explicitly save the current document again before closing its tab.
        # For Hello World this is the PY; the original TXT was saved above.
        self.timing.pause()
        pyautogui.hotkey("ctrl", "s")
        self.timing.pause()
        self.wait_until(saved, f"final saved contents of {path.name}")
        self.timing.pause()
        pyautogui.hotkey("ctrl", "w")

        def document_closed():
            window = self.foreground_window()
            if window.process_id() == editor.process_id() and window.class_name() == "#32770":
                return False  # Never proceed to desktop dragging over a save prompt.
            return (window.class_name() != "Notepad" or
                    not any(window.window_text().startswith(name + " - ")
                            for name in (path.name, path.stem)))

        self.wait_until(document_closed, f"Notepad tab {path.name} to close")
        return path

    def write_sentences(self):
        count = self.rng.choices(
            (3, 4, 5, 6, 7, 8, 9, 10, 11), weights=(2, 3, 5, 8, 12, 8, 5, 3, 2), k=1)[0]
        return self.write_desktop_document("notes", count=count)

    def write_hello_world(self):
        return self.write_desktop_document(
            "helloworld", ".py", text='print("Hello, world!")')

    def organize_desktop_file(self, path):
        """Drag the just-created TXT to the first free slot, left column first."""
        if path is None or not Path(path).is_file():
            return False
        path = Path(path)
        if not self.is_on_desktop():
            pyautogui.hotkey("win", "d")
            self.timing.pause()
        self.wait_until(self.is_on_desktop, "desktop before organizing the TXT")

        def find_icon():
            self.fetch_desktop()
            return next((name for name in (path.name, path.stem)
                         if name in self.desktop_icons), None)

        name = self.wait_until(find_icon, f"desktop icon {path.name}")
        target = self.desktop_creation_point(ordered=True, exclude_name=name)
        if target is None:
            print(f"No free desktop slot for {path.name}")
            return False
        left, top, right, bottom = self.desktop_icons[name]
        source = (round((left + right) / 2), round((top + bottom) / 2))
        if math.dist(source, target) < 12:
            return True
        # Select only this file before dragging, avoiding moving a group selection.
        self.move_and_click(*source)
        self.timing.pause()
        if not self.is_on_desktop():
            return False
        try:
            pyautogui.mouseDown(button="left")
            self.timing.delay()
            self.curve_move(*target, correction=False, smooth=True,
                            speed_scale=self.rng.uniform(0.7, 0.8))
            self.timing.delay()
        finally:
            original_failsafe = pyautogui.FAILSAFE
            try:
                pyautogui.FAILSAFE = False
                pyautogui.mouseUp(button="left")
            finally:
                pyautogui.FAILSAFE = original_failsafe
        self.timing.pause()

        def positioned():
            current_name = find_icon()
            if not current_name:
                return False
            l, t, r, b = self.desktop_icons[current_name]
            # Explorer may snap the drop to its configured icon grid.
            return (abs((l + r) / 2 - target[0]) <= max(r - l, 48)
                    and abs((t + b) / 2 - target[1]) <= max(b - t, 48))

        self.wait_until(positioned, f"{path.name} to occupy the left-side slot")
        return True
