import time
import random
import math

class Timing:
    def pause(self):
        # pause for 2 ~ 5 seconds
        # to simulate 'thinking' behavior
        time.sleep(random.uniform(1.0, 3.0))
        
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
