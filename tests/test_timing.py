import unittest
from core.timing import Timing


class TimingTests(unittest.TestCase):
    def test_pause_observes_abort_between_small_sleep_chunks(self):
        state = {"time": 0.0, "sleeps": []}
        def sleep(seconds):
            state["sleeps"].append(seconds)
            state["time"] += seconds
        def check():
            if state["time"] >= 0.1:
                raise KeyboardInterrupt()
        try:
            timing = Timing(clock=lambda: state["time"], sleep=sleep, check=check)
        except TypeError:
            self.fail("Timing does not support cooperative checks")
        with self.assertRaises(KeyboardInterrupt):
            timing.pause(10)
        self.assertAlmostEqual(state["time"], 0.1)
        self.assertLessEqual(max(state["sleeps"]), 0.05)

    def test_zero_pause_checks_before_returning(self):
        def check():
            raise KeyboardInterrupt()
        try:
            timing = Timing(check=check)
        except TypeError:
            self.fail("Timing does not support cooperative checks")
        with self.assertRaises(KeyboardInterrupt):
            timing.pause(0)
