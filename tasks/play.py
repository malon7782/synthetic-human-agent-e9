import math

import pyautogui


class PlayTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def _work_area(self, screen_width, screen_height):
        """Return a desktop area that excludes edges and the taskbar."""
        return (
            round(screen_width * 0.05),
            round(screen_height * 0.06),
            round(screen_width * 0.95),
            round(screen_height * 0.82),
        )

    def _clamp_to_work_area(self, x, y, screen_width, screen_height):
        left, top, right, bottom = self._work_area(screen_width, screen_height)
        return max(left, min(right, x)), max(top, min(bottom, y))

    def _random_work_area_point(self, screen_width, screen_height):
        left, top, right, bottom = self._work_area(screen_width, screen_height)
        return self.ui.rng.randint(left, right), self.ui.rng.randint(top, bottom)

    def _move_freely(self, x, y):
        # Play movements are not target acquisition, so they do not use the
        # intentional miss-and-correct behavior used before real clicks.
        self.ui.curve_move(x, y, correction=False)

    def _wreath_burst(self):
        """Draw a small flower-shaped loop entirely inside the work area."""
        screen_width, screen_height = pyautogui.size()
        left, top, right, bottom = self._work_area(
            screen_width, screen_height
        )
        radius = round(0.05 * min(screen_width, screen_height))
        center_x = self.ui.rng.randint(left + radius, right - radius)
        center_y = self.ui.rng.randint(top + radius, bottom - radius)
        petals = self.ui.rng.choice((4, 5, 6))
        point_count = petals * 8

        # Start on the loop so the movement toward the play area is separate
        # from the shape itself.
        self._move_freely(center_x + radius, center_y)
        original_pause = pyautogui.PAUSE
        try:
            pyautogui.PAUSE = 0
            for index in range(1, point_count + 1):
                angle = 2 * math.pi * index / point_count
                loop_radius = radius * (
                    0.70 + 0.30 * math.sin(petals * angle)
                )
                x = round(center_x + loop_radius * math.cos(angle))
                y = round(center_y + loop_radius * math.sin(angle))
                pyautogui.moveTo(x, y, duration=0)
                self.timing.curve_step_delay(index / point_count)
        finally:
            pyautogui.PAUSE = original_pause

    def _free_wander_burst(self):
        """Make a sustained, high-amplitude sequence with irregular reversals."""
        screen_width, screen_height = pyautogui.size()
        current = pyautogui.position()
        current_x, current_y = current.x, current.y
        minimum_jump = 0.16 * min(screen_width, screen_height)

        for _ in range(self.ui.rng.randint(6, 14)):
            destination = None
            for _ in range(20):
                point = self._random_work_area_point(screen_width, screen_height)
                distance = ((point[0] - current_x) ** 2
                            + (point[1] - current_y) ** 2) ** 0.5
                if distance >= minimum_jump:
                    destination = point
                    break
            if destination is None:
                destination = self._random_work_area_point(
                    screen_width, screen_height
                )

            self._move_freely(*destination)
            current_x, current_y = destination
            if self.ui.rng.random() < 0.20:
                self.timing.play_pause()

    def _axis_zigzag_burst(self):
        """Make three to five fast horizontal or vertical round trips."""
        screen_width, screen_height = pyautogui.size()
        left, top, right, bottom = self._work_area(
            screen_width, screen_height
        )
        horizontal = self.ui.rng.choice((True, False))
        round_trips = self.ui.rng.randint(3, 5)

        for index in range(round_trips * 2):
            if horizontal:
                x = right if index % 2 == 0 else left
                base_y = (top + bottom) // 2
                y = base_y + (
                    round(screen_height * 0.04)
                    if index % 2 == 0 else -round(screen_height * 0.04)
                )
            else:
                base_x = (left + right) // 2
                x = base_x + (
                    round(screen_width * 0.04)
                    if index % 2 == 0 else -round(screen_width * 0.04)
                )
                y = bottom if index % 2 == 0 else top

            x, y = self._clamp_to_work_area(
                x, y, screen_width, screen_height
            )
            pyautogui.moveTo(
                x,
                y,
                duration=self.ui.rng.uniform(0.12, 0.20),
            )

    def _short_adjustment_burst(self):
        """Make one to three short relocations followed by a brief hold."""
        screen_width, screen_height = pyautogui.size()
        for _ in range(self.ui.rng.randint(1, 3)):
            current = pyautogui.position()
            x = current.x + self.ui.rng.randint(-420, 420)
            y = current.y + self.ui.rng.randint(-280, 280)
            x, y = self._clamp_to_work_area(
                x, y, screen_width, screen_height
            )
            self._move_freely(x, y)
        self.timing.play_pause()

    def _is_empty_desktop_point(self, x, y, margin=16):
        for left, top, right, bottom in self.ui.desktop_icons.values():
            if (left - margin <= x <= right + margin
                    and top - margin <= y <= bottom + margin):
                return False
        return True

    def _find_empty_desktop_point(self, screen_width, screen_height):
        left, top, right, bottom = self._work_area(
            screen_width, screen_height
        )
        for _ in range(40):
            x = self.ui.rng.randint(left, right)
            y = self.ui.rng.randint(top, bottom)
            if self._is_empty_desktop_point(x, y):
                return x, y
        return None

    def _drag_selection_burst(self):
        """Draw several differently sized selection rectangles."""
        screen_width, screen_height = pyautogui.size()
        for _ in range(self.ui.rng.randint(2, 5)):
            start = self._find_empty_desktop_point(
                screen_width, screen_height
            )
            if start is None:
                self._short_adjustment_burst()
                return

            mostly_horizontal = self.ui.rng.random() < 0.55
            direction_x = self.ui.rng.choice((-1, 1))
            direction_y = self.ui.rng.choice((-1, 1))
            if mostly_horizontal:
                delta_x = direction_x * self.ui.rng.randint(
                    round(screen_width * 0.25),
                    round(screen_width * 0.70),
                )
                delta_y = direction_y * self.ui.rng.randint(
                    round(screen_height * 0.01),
                    round(screen_height * 0.08),
                )
                duration = self.ui.rng.uniform(0.30, 0.85)
            else:
                delta_x = direction_x * self.ui.rng.randint(
                    round(screen_width * 0.08),
                    round(screen_width * 0.35),
                )
                delta_y = direction_y * self.ui.rng.randint(
                    round(screen_height * 0.06),
                    round(screen_height * 0.30),
                )
                duration = self.ui.rng.uniform(0.15, 0.65)

            end_x, end_y = self._clamp_to_work_area(
                start[0] + delta_x,
                start[1] + delta_y,
                screen_width,
                screen_height,
            )

            self._move_freely(*start)
            self.timing.play_pause()
            pyautogui.mouseDown(button="left")
            try:
                pyautogui.moveTo(end_x, end_y, duration=duration)
            finally:
                pyautogui.mouseUp(button="left")
            self.timing.play_pause()

    def run(self):
        if not self.ui.is_on_desktop():
            pyautogui.hotkey("win", "d")
            self.timing.delay()

        self.ui.fetch_desktop()
        behaviors = (
            self._free_wander_burst,
            self._drag_selection_burst,
            self._axis_zigzag_burst,
            self._short_adjustment_burst,
            self._wreath_burst,
        )
        weights = (37, 28, 17, 10, 8)

        self.timing.play_pause()
        for index in range(self.ui.rng.randint(2, 4)):
            if index:
                self.timing.play_pause()
            behavior = self.ui.rng.choices(
                behaviors,
                weights=weights,
                k=1,
            )[0]
            behavior()
