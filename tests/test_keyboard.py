"""Foreground keyboard switching with fake Win32 calls; never sends UI input."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


class Api:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


def value(number):
    return number.value if hasattr(number, "value") else number


class FakeWindows:
    def __init__(self, *, installed=(0x4090409, 0x8040804), delay=4, reject=False):
        self.installed = installed
        self.delay = delay
        self.reject = reject
        self.now = 0.0
        self.window = 10
        self.layouts = {10: 0x8040804, 20: 0x8040804}
        self.pending = {}
        self.posts = []
        self.output = []
        self.GetForegroundWindow = Api(lambda: self.window)
        self.GetWindowThreadProcessId = Api(lambda hwnd, pointer: value(hwnd))
        self.GetKeyboardLayout = Api(lambda thread: self.layouts[value(thread)])
        self.GetKeyboardLayoutList = Api(self.layout_list)
        self.PostMessageW = Api(self.post)

    def layout_list(self, count, buffer):
        if not count:
            return len(self.installed)
        for index, layout in enumerate(self.installed):
            buffer[index] = layout
        return len(self.installed)

    def post(self, hwnd, message, flags, layout):
        hwnd, layout = value(hwnd), value(layout)
        self.posts.append((hwnd, value(message), value(flags), layout))
        if self.reject:
            return 0
        self.pending[hwnd] = (self.now + self.delay * 0.2, layout)
        return 1

    def sleep(self, seconds):
        self.now += seconds
        for hwnd, (ready, layout) in self.pending.items():
            if self.now + 1e-8 >= ready:
                self.layouts[hwnd] = layout

    def write(self, char):
        if self.layouts[self.window] & 0x3FF != 0x09:
            raise AssertionError("Typing occurred before foreground English confirmation")
        self.output.append(char)


_keys = types.ModuleType("pyautogui")
_desktop = types.ModuleType("pywinauto")
_desktop.Desktop = lambda **kwargs: (_ for _ in ()).throw(AssertionError("No desktop access"))
_spec = importlib.util.spec_from_file_location(
    "keyboard_test_ui", Path(__file__).resolve().parents[1] / "core" / "ui.py"
)
ui_module = importlib.util.module_from_spec(_spec)
with patch.dict(sys.modules, {"pyautogui": _keys, "pywinauto": _desktop}):
    _spec.loader.exec_module(ui_module)


class KeyboardTests(unittest.TestCase):
    def run_typing(self, fake, text="ab", sleep=None):
        timing = types.SimpleNamespace(check=lambda: None, delay=lambda: None,
                                       sleep=sleep or fake.sleep)
        keys = types.SimpleNamespace(write=fake.write,
                                     hotkey=lambda *args: None, sleep=fake.sleep)
        with patch.object(ui_module.ctypes, "windll", types.SimpleNamespace(user32=fake)), \
                patch.object(ui_module, "pyautogui", keys), \
                patch.object(ui_module.time, "monotonic", lambda: fake.now):
            ui_module.UI(timing).type_text(text)

    def test_delayed_switch_confirms_installed_english_before_typing(self):
        fake = FakeWindows(delay=4)
        self.run_typing(fake)
        self.assertEqual(fake.output, ["a", "b"])
        self.assertEqual(fake.posts, [(10, 0x0050, 0, 0x4090409)])

    def test_focus_change_aborts_without_typing_into_another_window(self):
        fake = FakeWindows(delay=2)
        def sleep(seconds):
            fake.sleep(seconds)
            if fake.now >= 0.2:
                fake.window = 20
        with self.assertRaises(RuntimeError):
            self.run_typing(fake, sleep=sleep)
        self.assertEqual([post[0] for post in fake.posts], [10])
        self.assertEqual(fake.layouts[20], 0x8040804)
        self.assertEqual(fake.output, [])

    def test_already_english_does_not_send_switch_request(self):
        fake = FakeWindows()
        fake.layouts[10] = 0x4090409
        self.run_typing(fake)
        self.assertEqual(fake.posts, [])
        self.assertEqual(fake.output, ["a", "b"])

    def test_missing_english_never_types_or_posts(self):
        fake = FakeWindows(installed=(0x8040804,))
        with self.assertRaises(RuntimeError):
            self.run_typing(fake)
        self.assertEqual(fake.output, [])
        self.assertEqual(fake.posts, [])

    def test_rejected_post_never_types(self):
        fake = FakeWindows(reject=True)
        with self.assertRaises(RuntimeError):
            self.run_typing(fake)
        self.assertEqual(fake.output, [])

    def test_unprocessed_request_times_out_without_typing(self):
        fake = FakeWindows(delay=100)
        with self.assertRaises(RuntimeError):
            self.run_typing(fake)
        self.assertEqual(fake.output, [])
        self.assertEqual(len(fake.posts), 1)
        self.assertLessEqual(fake.now, 5.2)

    def test_empty_string_still_confirms_keyboard_for_corpus_typing(self):
        fake = FakeWindows(delay=4)
        self.run_typing(fake, text="")
        self.assertEqual(fake.layouts[10], 0x4090409)
        self.assertEqual(fake.output, [])


class ProcessImageDiagnosticsTests(unittest.TestCase):
    def make_kernel(self, *, open_error=None, query_error=None):
        self.closed = []
        def open_process(access, inherit, pid):
            self.assertEqual((access, inherit, pid), (0x1000, False, 5678))
            if open_error is not None:
                ui_module.ctypes.set_last_error(open_error)
                return None
            return 99
        def query(handle, flags, path, size):
            if query_error is not None:
                ui_module.ctypes.set_last_error(query_error)
                return 0
            path.value = r"C:\Windows\System32\notepad.exe"
            return 1
        def close(handle):
            self.closed.append(handle)
            # Cleanup may change last error; the original failure must survive.
            ui_module.ctypes.set_last_error(6)
            return 1
        return types.SimpleNamespace(OpenProcess=Api(open_process),
                                     QueryFullProcessImageNameW=Api(query),
                                     CloseHandle=Api(close))

    def call_image(self, kernel):
        window = types.SimpleNamespace(handle=1234, process_id=lambda: 5678)
        with patch.object(ui_module.ctypes, "WinDLL", return_value=kernel), \
                patch.object(ui_module.ctypes, "windll", types.SimpleNamespace(kernel32=kernel)):
            return ui_module.UI(None).window_executable(window)

    def test_open_process_preserves_native_error_and_observed_window_identity(self):
        kernel = self.make_kernel(open_error=5)
        with self.assertRaises(OSError) as caught:
            self.call_image(kernel)
        self.assertEqual(getattr(caught.exception, "winerror", None), 5)
        self.assertIn("OpenProcess", str(caught.exception))
        self.assertIn("HWND=1234", str(caught.exception))
        self.assertIn("PID=5678", str(caught.exception))
        self.assertEqual(self.closed, [])

    def test_query_error_survives_handle_cleanup_with_window_identity(self):
        kernel = self.make_kernel(query_error=87)
        with self.assertRaises(OSError) as caught:
            self.call_image(kernel)
        self.assertEqual(getattr(caught.exception, "winerror", None), 87)
        self.assertIn("QueryFullProcessImageNameW", str(caught.exception))
        self.assertIn("HWND=1234", str(caught.exception))
        self.assertIn("PID=5678", str(caught.exception))
        self.assertEqual(self.closed, [99])

    def test_success_returns_basename_and_closes_handle(self):
        kernel = self.make_kernel()
        self.assertEqual(self.call_image(kernel), "notepad.exe")
        self.assertEqual(self.closed, [99])
        self.assertIs(kernel.OpenProcess.restype, ui_module.wintypes.HANDLE)
        self.assertIs(kernel.QueryFullProcessImageNameW.restype, ui_module.wintypes.BOOL)
        self.assertIs(kernel.CloseHandle.restype, ui_module.wintypes.BOOL)


class CorpusFocusTests(unittest.TestCase):
    def test_focus_loss_during_each_typing_phase_prevents_next_key(self):
        for mode, phase, trigger, expected_count in (
            (None, "typing", 1, 0),
            (None, "typing", 2, 1),
            ("repeat", "typing", 2, 1),
            ("repeat", "delay", 1, 2),
            ("replace", "delay", 1, 1),
            ("swap", "delay", 2, 3),
            ("omit", "typing", 2, 2),
            ("replace", "typing", 2, 2),
        ):
            with self.subTest(mode=mode, phase=phase, trigger=trigger):
                fake = FakeWindows()
                fake.layouts = {10: 0x4090409, 20: 0x4090409}
                calls = {"typing": 0, "delay": 0}
                events = []
                def pause(kind):
                    calls[kind] += 1
                    if kind == phase and calls[kind] == trigger:
                        fake.window = 20
                timing = types.SimpleNamespace(
                    check=lambda: None,
                    delay=lambda: pause("delay"),
                    typing_delay=lambda char: pause("typing"),
                    sleep=fake.sleep,
                )
                keys = types.SimpleNamespace(
                    write=lambda char: events.append(("write", char, fake.window)),
                    press=lambda key: events.append(("press", key, fake.window)),
                )
                rng = types.SimpleNamespace(
                    random=lambda: 0.0,
                    choice=lambda options: options[0],
                    choices=lambda options, **kwargs: [mode],
                )
                with patch.object(ui_module.ctypes, "windll", types.SimpleNamespace(user32=fake)), \
                        patch.object(ui_module, "pyautogui", keys), \
                        patch.dict(ui_module.TEXT_CORPUS, {"fixture": ["ab"]}):
                    with self.assertRaises(RuntimeError):
                        ui_module.UI(timing, rng).type_from_corpus("fixture", int(mode is not None))
                self.assertEqual(len(events), expected_count)
                self.assertTrue(all(event[2] == 10 for event in events))

    def test_standalone_typo_also_checks_focus_after_correction_pause(self):
        fake = FakeWindows()
        fake.layouts[10] = 0x4090409
        events = []
        timing = types.SimpleNamespace(
            check=lambda: None,
            typing_delay=lambda char: None,
            delay=lambda: setattr(fake, "window", 20),
        )
        rng = types.SimpleNamespace(choices=lambda options, **kwargs: ["repeat"])
        keys = types.SimpleNamespace(
            write=lambda char: events.append(("write", char, fake.window)),
            press=lambda key: events.append(("press", key, fake.window)),
        )
        with patch.object(ui_module.ctypes, "windll", types.SimpleNamespace(user32=fake)), \
                patch.object(ui_module, "pyautogui", keys):
            with self.assertRaises(RuntimeError):
                ui_module.UI(timing, rng).typo("a")
        self.assertEqual(events, [("write", "a", 10), ("write", "a", 10)])


if __name__ == "__main__":
    unittest.main()
