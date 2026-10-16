"""Typing regressions: imports and output are isolated from the real desktop."""
import importlib.util
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import patch


class RecordingKeys(types.ModuleType):
    def __init__(self):
        super().__init__("pyautogui")
        self.text = ""
        self.events = []

    def write(self, text):
        self.events.append(("write", text))
        self.text += text

    def press(self, key):
        self.events.append(("press", key))
        if key != "backspace":
            raise AssertionError(f"Unexpected key: {key}")
        self.text = self.text[:-1]

    def hotkey(self, *keys):
        self.events.append(("hotkey", keys))

    def sleep(self, seconds):
        self.events.append(("sleep", seconds))


_keys = RecordingKeys()
_windows = types.ModuleType("pywinauto")
_windows.Desktop = lambda **kwargs: (_ for _ in ()).throw(
    AssertionError("Tests must never access the desktop")
)
_spec = importlib.util.spec_from_file_location(
    "typing_test_ui", Path(__file__).resolve().parents[1] / "core" / "ui.py"
)
ui_module = importlib.util.module_from_spec(_spec)
with patch.dict(sys.modules, {"pyautogui": _keys, "pywinauto": _windows}):
    _spec.loader.exec_module(ui_module)


class Timing:
    def check(self):
        pass

    def delay(self):
        pass

    def typing_delay(self, char):
        pass


class ModeRng(random.Random):
    def __init__(self, mode):
        super().__init__(10)
        self.mode = mode

    def random(self):
        return 0.0

    def choices(self, population, weights=None, k=1):
        if self.mode not in population:
            raise AssertionError(f"{self.mode} is unavailable for {population}")
        return [self.mode]


class TypingTests(unittest.TestCase):
    def setUp(self):
        self.keys = RecordingKeys()
        self.patch_keys = patch.object(ui_module, "pyautogui", self.keys)
        self.patch_keys.start()
        self.addCleanup(self.patch_keys.stop)
        self.patch_foreground = patch.object(
            ui_module.ctypes, "windll", types.SimpleNamespace(
                user32=types.SimpleNamespace(GetForegroundWindow=lambda: 10)
            )
        )
        self.patch_foreground.start()
        self.addCleanup(self.patch_foreground.stop)
        self.ui = ui_module.UI(Timing(), random.Random(42))
        # Pure text tests replace only OS keyboard preparation and foreground.
        self.layout_calls = []
        def prepare_keyboard():
            self.layout_calls.append("")
            return 10
        self.ui.ensure_english_keyboard = prepare_keyboard

    def test_all_correction_modes_restore_original_text_and_consumption(self):
        for mode, char, next_char, expected, consumed in (
            ("replace", "a", None, "a", 1),
            ("repeat", "a", None, "a", 1),
            ("omit", "a", "b", "ab", 2),
            ("swap", "a", "b", "ab", 2),
            ("omit", "a", "a", "aa", 2),
            ("replace", "A", None, "A", 1),
            ("repeat", "A", None, "A", 1),
            ("omit", "A", "b", "Ab", 2),
            ("swap", "a", "B", "aB", 2),
        ):
            with self.subTest(mode=mode, char=char, next_char=next_char):
                self.keys.text = "prefix:"
                self.ui.rng = ModeRng(mode)
                self.assertEqual(self.ui.typo(char, next_char), consumed)
                self.assertEqual(self.keys.text, "prefix:" + expected)

    def test_corpus_loop_does_not_drop_or_duplicate_pair_characters(self):
        for mode in ("replace", "repeat", "omit", "swap"):
            with self.subTest(mode=mode):
                self.keys.text = ""
                self.ui.rng = ModeRng(mode)
                # Every letter is in a pair so forced pair modes are available.
                with patch.dict(ui_module.TEXT_CORPUS, {"fixture": ["ab cd ef!"]}):
                    self.assertEqual(self.ui.type_from_corpus("fixture", 1), "ab cd ef!")
                self.assertEqual(self.keys.text, "ab cd ef!")

    def test_empty_text_produces_no_keys(self):
        with patch.dict(ui_module.TEXT_CORPUS, {"fixture": [""]}):
            self.assertEqual(self.ui.type_from_corpus("fixture", 1), "")
        self.assertEqual(self.keys.events, [])
        self.assertEqual(self.layout_calls, [""])

    def test_rate_zero_produces_original_without_backspaces(self):
        with patch.dict(ui_module.TEXT_CORPUS, {"fixture": ["ab cd!"]}):
            self.assertEqual(self.ui.type_from_corpus("fixture", 0), "ab cd!")
        self.assertEqual(self.keys.text, "ab cd!")
        self.assertFalse(any(event[0] == "press" for event in self.keys.events))

    def test_seeded_typing_preserves_text_at_rate_boundaries_and_default(self):
        for seed in range(40):
            for rate in (0, 0.2, 1):
                for text in ("a", "aa", "ab", "A bC! 12?", "print(\"Hello, world!\")"):
                    with self.subTest(seed=seed, rate=rate, text=text):
                        self.keys.text = ""
                        self.ui.rng = random.Random(seed)
                        with patch.dict(ui_module.TEXT_CORPUS, {"fixture": [text]}):
                            self.ui.type_from_corpus("fixture", rate)
                        self.assertEqual(self.keys.text, text)

    def test_invalid_rates_raise_before_keyboard_preparation_or_output(self):
        for rate in (-0.01, 1.01, float("nan"), float("inf"), -float("inf")):
            with self.subTest(rate=rate):
                with self.assertRaises(ValueError):
                    self.ui.type_from_corpus("sentence", rate)
        self.assertEqual(self.layout_calls, [])
        self.assertEqual(self.keys.events, [])

    def test_unknown_category_preserves_value_error_interface(self):
        with self.assertRaises(ValueError):
            self.ui.choose_text("not-a-category")

    def test_empty_category_preserves_value_error_interface(self):
        with patch.dict(ui_module.TEXT_CORPUS, {"fixture": []}):
            with self.assertRaises(ValueError):
                self.ui.choose_text("fixture")

    def test_helloworld_category_types_exact_script(self):
        self.assertEqual(self.ui.type_from_corpus("helloworld", 0), 'print("Hello, world!")')
        self.assertEqual(self.keys.text, 'print("Hello, world!")')

    def test_search_templates_are_fully_formatted(self):
        for seed in range(40):
            text = self.ui.choose_text("search", random.Random(seed))
            self.assertTrue(text)
            self.assertNotIn("{", text)
            self.assertNotIn("}", text)

    def test_invalid_typo_input_emits_nothing(self):
        for char in ("", "ab", "1", " ", "é"):
            with self.subTest(char=char):
                with self.assertRaises(ValueError):
                    self.ui.typo(char)
        self.assertEqual(self.keys.events, [])

    def test_keyboard_layout_switch_still_precedes_typing(self):
        from test_keyboard import FakeWindows
        del self.ui.ensure_english_keyboard
        user32 = FakeWindows(delay=1)
        self.ui.timing.sleep = user32.sleep
        with patch.object(ui_module.ctypes, "windll", types.SimpleNamespace(user32=user32)), \
                patch.object(ui_module.time, "monotonic", lambda: user32.now):
            ui_module.UI.type_text(self.ui, "ab")
        self.assertEqual(self.keys.text, "ab")
        self.assertEqual(user32.posts, [(10, 0x0050, 0, 0x4090409)])
        self.assertEqual(user32.layouts[10], 0x4090409)

    def test_unavailable_english_layout_raises_without_typing(self):
        from test_keyboard import FakeWindows
        del self.ui.ensure_english_keyboard
        user32 = FakeWindows(installed=(0x8040804,))
        with patch.object(ui_module.ctypes, "windll", types.SimpleNamespace(user32=user32)):
            with self.assertRaises(RuntimeError):
                ui_module.UI.type_text(self.ui, "ab")
        self.assertEqual(self.keys.text, "")


if __name__ == "__main__":
    unittest.main()
