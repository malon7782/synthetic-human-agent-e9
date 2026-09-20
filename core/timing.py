import time
import random

class Timing:
    def pause(self):
        # pause for 2 ~ 5 seconds
        # to simulate 'thinking' behavior
        time.sleep(random.uniform(1.0, 3.0))
        
    def delay(self):
        # shorter pause = delay
        # to simulate unconscious lag between mouse movements
        time.sleep(random.uniform(0.1, 0.4))