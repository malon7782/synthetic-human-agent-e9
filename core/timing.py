import time
import random
import math

class Timing():
    def __init__(self, pause_action=None):
        self.pause_action = pause_action

    def pause(self, t=None, play=False):
        """Pause for t seconds (default 1-2); play=False keeps the mouse still."""
        if t is None:
            t = random.uniform(1.0, 2.0)
        if not math.isfinite(t) or t < 0:
            raise ValueError("t must be a finite, non-negative number of seconds")
        # main.py binds PlayTask.move_locally after creating the shared UI.
        if play and self.pause_action is not None:
            self.pause_action(t)
        else:
            time.sleep(t)
        
    def delay(self):
        # shorter pause = delay
        # to simulate unconscious lag between mouse movements
        time.sleep(random.uniform(0.1, 0.4))

    def curve_step_delay(self, progress):
        """Pause briefly between curve points, with slower endpoints."""
        if not 0 < progress <= 1:
            raise ValueError("progress must be in (0, 1]")

        speed = 0.45 + 0.55 * math.sin(math.pi * progress)
        time.sleep(random.uniform(0.004, 0.008) / speed)

    def correction_pause(self):
        """Pause briefly before correcting an intentionally inaccurate move."""
        time.sleep(random.uniform(0.1, 0.3))

