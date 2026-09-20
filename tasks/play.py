import pyautogui


class PlayTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def _brief_idle(self):
        """Leave the pointer still for a short period."""
        self.timing.pause()

    def _hover_over_icon(self):
        """Move to a desktop icon without clicking it."""
        if not self.ui.desktop_icons:
            self.ui.curve_move()
            return

        icon_name = self.ui.rng.choice(list(self.ui.desktop_icons))
        x, y = self.ui.get_coords_desktop(icon_name)
        self.ui.curve_move(x, y)
        self.timing.pause()

    def _local_mouse_activity(self):
        """Perform one weighted idle movement selected by the UI layer."""
        self.ui.curve_move()

    def _is_empty_desktop_point(self, x, y, margin=16):
        for left, top, right, bottom in self.ui.desktop_icons.values():
            if (left - margin <= x <= right + margin
                    and top - margin <= y <= bottom + margin):
                return False
        return True

    def _find_empty_desktop_point(self, screen_width, screen_height):
        # Stay away from screen edges and the taskbar.  A bounded search keeps
        # this behavior safe even when the desktop contains many icons.
        for _ in range(40):
            x = self.ui.rng.randint(
                round(screen_width * 0.08),
                round(screen_width * 0.92),
            )
            y = self.ui.rng.randint(
                round(screen_height * 0.08),
                round(screen_height * 0.82),
            )
            if self._is_empty_desktop_point(x, y):
                return x, y
        return None

    def _drag_selection_box(self):
        """Drag a selection rectangle starting from empty desktop space."""
        screen_width, screen_height = pyautogui.size()
        start = self._find_empty_desktop_point(screen_width, screen_height)
        if start is None:
            self._local_mouse_activity()
            return

        direction_x = self.ui.rng.choice((-1, 1))
        direction_y = self.ui.rng.choice((-1, 1))
        width = self.ui.rng.randint(
            round(screen_width * 0.08),
            round(screen_width * 0.20),
        )
        height = self.ui.rng.randint(
            round(screen_height * 0.06),
            round(screen_height * 0.16),
        )
        end_x = max(0, min(screen_width - 1, start[0] + direction_x * width))
        end_y = max(0, min(screen_height - 1, start[1] + direction_y * height))

        self.ui.move_and_click(
            start[0], start[1],
            button="drag",
            end_x=end_x,
            end_y=end_y,
        )

    def run(self):
        if not self.ui.is_on_desktop():
            pyautogui.hotkey("win", "d")
            self.timing.delay()

        self.ui.fetch_desktop()
        behavior = self.ui.rng.choices(
            (
                self._brief_idle,
                self._hover_over_icon,
                self._local_mouse_activity,
                self._drag_selection_box,
            ),
            weights=(30, 30, 25, 15),
            k=1,
        )[0]
        behavior()
