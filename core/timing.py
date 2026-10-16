import math
import random
import time


class DeadlineReached(Exception):
    """The activity budget ended at a cooperative cancellation point."""


class Timing:
    def __init__(self, pause_action=None, *, check=None, clock=None, sleep=None, rng=None):
        self.pause_action = pause_action
        self._check = check
        self.clock = clock if clock is not None else time.monotonic
        self._sleep = sleep if sleep is not None else time.sleep
        self.rng = rng if rng is not None else random
        self.deadline = None

    def check(self):
        """Check user cancellation, then the session's cooperative deadline."""
        if self._check is not None:
            self._check()
        if self.deadline is not None and self.clock() >= self.deadline:
            raise DeadlineReached("activity duration elapsed")

    def _wait(self, seconds, action):
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("seconds must be a finite, non-negative number")
        end = self.clock() + seconds
        while True:
            self.check()
            remaining = end - self.clock()
            if remaining <= 0:
                return
            if self.deadline is not None:
                remaining = min(remaining, self.deadline - self.clock())
            action(min(0.05, max(0.0, remaining)))

    def sleep(self, seconds):
        """Sleep in short chunks, checking cancellation before every chunk."""
        self._wait(seconds, self._sleep)

    def pause(self, t=None, play=False):
        """Pause for t seconds (default 1-2); play=False keeps the mouse still."""
        if t is None:
            t = self.rng.uniform(1.0, 2.0)
        action = self.pause_action if play and self.pause_action is not None else self._sleep
        self._wait(t, action)

    def delay(self):
        self.sleep(self.rng.uniform(0.1, 0.4))

    def typing_delay(self, char):
        self.sleep(self.rng.uniform(0.04, 0.15))
        if char == " " and self.rng.random() < 0.3:
            self.delay()

    def curve_step_delay(self, progress):
        """Pause briefly between curve points, with slower endpoints."""
        if not 0 < progress <= 1:
            raise ValueError("progress must be in (0, 1]")
        speed = 0.45 + 0.55 * math.sin(math.pi * progress)
        self.sleep(self.rng.uniform(0.004, 0.008) / speed)

    def correction_pause(self):
        self.sleep(self.rng.uniform(0.1, 0.3))
