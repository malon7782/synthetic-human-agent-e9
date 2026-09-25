import math
import time

class PlayTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    def move_locally(self, t):
        """Make quick, irregular local movements for approximately t seconds."""
        if not math.isfinite(t) or t < 0:
            raise ValueError("t must be a finite, non-negative number of seconds")
        if t == 0:
            return
        started = time.perf_counter()
        origin = self.ui.mouse_position()
        width, height = self.ui.screen_size()
        rng = self.ui.rng
        radius = min(width, height) * rng.uniform(0.09, 0.15)
        left, right = max(2, origin.x - radius), min(width - 3, origin.x + radius)
        top, bottom = max(2, origin.y - radius), min(height - 3, origin.y + radius)

        def clamp(x, y):
            return max(left, min(right, x)), max(top, min(bottom, y))

        x, y = clamp(origin.x, origin.y)
        deadline = started + t
        with self.ui.without_mouse_pause():
            while time.perf_counter() < deadline:
                start_x, start_y = x, y
                end_x, end_y = rng.uniform(left, right), rng.uniform(top, bottom)
                dx, dy = end_x - start_x, end_y - start_y
                bend = rng.uniform(-0.8, 0.8)
                control_x, control_y = clamp(
                    (start_x + end_x) / 2 - dy * bend,
                    (start_y + end_y) / 2 + dx * bend,
                )
                segment_started = time.perf_counter()
                segment_duration = rng.uniform(0.12, 0.20)
                while time.perf_counter() < deadline:
                    progress = min(1.0, (time.perf_counter() - segment_started) / segment_duration)
                    # Ease into and out of each randomly sized, curved stroke.
                    u = progress * progress * (3 - 2 * progress)
                    x = (1 - u) ** 2 * start_x + 2 * (1 - u) * u * control_x + u ** 2 * end_x
                    y = (1 - u) ** 2 * start_y + 2 * (1 - u) * u * control_y + u ** 2 * end_y
                    self.ui.move_to(round(x), round(y), duration=0)
                    remaining = deadline - time.perf_counter()
                    if remaining > 0:
                        time.sleep(min(1 / 60, remaining))
                    if progress >= 1.0:
                        break
