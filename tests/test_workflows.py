"""Workflow regressions; all observations and input are isolated from Windows."""
import importlib.util
from pathlib import Path
import random
import sys
import types
import unittest
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
keys = types.ModuleType("pyautogui")
class FailSafeException(Exception):
    pass
keys.FailSafeException = FailSafeException
windows = types.ModuleType("pywinauto")
windows.Desktop = lambda **kwargs: None
clipboard = types.ModuleType("pyperclip")
clipboard.paste = lambda: '"C:\\Users\\Person\\Desktop\\helloworld_2.py"'
clipboard.copy = lambda text: None

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"pyautogui": keys, "pywinauto": windows, "pyperclip": clipboard}):
        spec.loader.exec_module(module)
    return module

hello = load("workflow_hello", "tasks/helloworld.py")
browser = load("workflow_browser", "tasks/browser.py")
ui_module = load("workflow_ui", "core/ui.py")

class Timing:
    def delay(self): pass
    def pause(self, *args): pass
    def sleep(self, seconds): pass
    def check(self): pass

class Window:
    def __init__(self, handle, executable="msedge.exe"):
        self.handle = handle
        self.executable = executable
    def rectangle(self):
        return types.SimpleNamespace(left=100, top=100, right=1100, bottom=900)
    def is_visible(self): return True

class BrowserUI:
    def __init__(self, fail=False, close_succeeds=True):
        self.rng = random.Random(4)
        self.events = []
        self.existing = Window(10)
        self.owned = Window(20)
        self.active = self.existing
        self.created = False
        self.fail = fail
        self.close_succeeds = close_succeeds
    def fetch_desktop(self): pass
    def get_coords_desktop(self, name): return (15, 30)
    def curve_move(self, *args): pass
    def move_and_click(self, x, y, *args): self.events.append(("pointer", x, y, args))
    def visible_windows(self): return [self.existing] + ([self.owned] if self.created else [])
    def foreground_window(self): return self.active
    def window_executable(self, window): return window.executable
    def focus_window(self, window): self.active = window
    def wait_until(self, predicate, description, timeout=15):
        result = predicate()
        if not result: raise RuntimeError(description)
        return result
    def hotkey(self, *keys):
        self.events.append(("hotkey", keys, self.active.handle))
        if keys == ("ctrl", "n"):
            self.created = True
            self.active = self.owned
        elif keys == ("alt", "f4") and self.close_succeeds:
            self.created = False
            self.active = self.existing
    def press(self, key): self.events.append(("press", key))
    def type_text(self, text): self.events.append(("text", text))
    def wait_browser_document(self, window, url, timeout=30):
        self.events.append(("ready", window.handle, url))
        if self.fail: raise RuntimeError("load failed")

class WorkflowTests(unittest.TestCase):
    def test_owned_browser_disappears_before_successful_return(self):
        ui = BrowserUI()
        browser.BrowserTask(None, ui, Timing(), urls=["https://www.apple.com"]).run()
        self.assertEqual([window.handle for window in ui.visible_windows()], [10])

    def test_ignored_browser_close_times_out_and_is_not_counted_complete(self):
        from core.runner import run_session
        ui = BrowserUI(close_succeeds=False)
        now = [0.0]
        timing = Timing()
        timing.sleep = lambda seconds: now.__setitem__(0, now[0] + seconds)
        ui.timing = timing
        # Exercise production polling with an inert clock rather than sleeping.
        ui.wait_until = types.MethodType(ui_module.UI.wait_until, ui)
        task = browser.BrowserTask(None, ui, timing, urls=["https://www.apple.com"])
        with patch.object(ui_module.time, "monotonic", lambda: now[0]):
            result = run_session({"browser": task}, once=True, duration=20, clock=lambda: now[0])
        self.assertEqual(result.status, "error")
        self.assertEqual(result.completed, 0)
        self.assertIn("owned Microsoft Edge window to close", result.error)
        self.assertGreater(now[0], 0)
        self.assertLessEqual(now[0], 15)
        self.assertEqual([window.handle for window in ui.visible_windows()], [10, 20])

    def test_new_console_accepts_documented_classic_host_and_rejects_existing_or_unrelated(self):
        for executable, handle, accepted in (("conhost.exe", 31, True), ("conhost.exe", 30, False), ("other.exe", 31, False)):
            with self.subTest(executable=executable, handle=handle):
                window = types.SimpleNamespace(handle=handle)
                ui = types.SimpleNamespace(foreground_window=lambda: window, window_executable=lambda observed: executable)
                task = hello.HelloWorldTask(ui, Timing())
                result = task._new_console({30})
                if accepted:
                    self.assertIs(result, window)
                else:
                    self.assertIsNone(result)

    def test_browser_abort_does_not_focus_or_close_after_cancellation(self):
        for error in (KeyboardInterrupt(), FailSafeException("stop"), browser.DeadlineReached("budget")):
            with self.subTest(error=type(error).__name__):
                ui = BrowserUI()
                def aborted(*args):
                    ui.events.append(("aborted",))
                    raise error
                original_focus = ui.focus_window
                def focused(window):
                    ui.events.append(("focus", window.handle))
                    original_focus(window)
                ui.focus_window = focused
                ui.wait_browser_document = aborted
                with self.assertRaises(type(error)):
                    browser.BrowserTask(None, ui, Timing(), urls=["https://www.apple.com"]).run()
                self.assertEqual(ui.events[ui.events.index(("aborted",)) + 1:], [])

    def test_focus_cancellation_precedes_set_focus(self):
        calls = []
        ui = ui_module.UI(Timing())
        ui.timing.check = lambda: (_ for _ in ()).throw(KeyboardInterrupt())
        window = types.SimpleNamespace(handle=1, set_focus=lambda: calls.append("focus"))
        with self.assertRaises(KeyboardInterrupt):
            ui.focus_window(window)
        self.assertEqual(calls, [])

    def test_copied_other_directory_same_name_is_rejected(self):
        with self.assertRaises(RuntimeError):
            hello.HelloWorldTask._validate_script_path('"C:\\Other\\helloworld.py"', "helloworld.py", "C:\\Desktop")

    def test_saved_script_must_match_intended_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "helloworld.py"
            path.write_text('print("different")', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                hello.HelloWorldTask._validate_script_file(str(path), 'print("Hello, world!")')

    def test_existing_editor_with_substring_filename_is_not_selected(self):
        focused = []
        existing = types.SimpleNamespace(handle=7, window_text=lambda: "New Text Document.txt.bak - Editor")
        ui = types.SimpleNamespace(visible_windows=lambda: [existing], focus_window=lambda w: focused.append(w.handle),
            wait_until=lambda predicate, description: predicate())
        task = hello.HelloWorldTask(ui, Timing())
        with self.assertRaises(RuntimeError):
            task._open_editor("New Text Document.txt", {7})
        self.assertEqual(focused, [])

    def test_new_exact_editor_requires_empty_buffer_before_any_input(self):
        for contents, allowed in (("", True), ("unrelated saved content", False)):
            with self.subTest(contents=contents):
                events = []
                buffer = types.SimpleNamespace(element_info=types.SimpleNamespace(name="New Text Document.txt", control_type="Document"),
                    is_visible=lambda: True, iface_text=types.SimpleNamespace(DocumentRange=types.SimpleNamespace(GetText=lambda count: contents)),
                    rectangle=lambda: types.SimpleNamespace(left=20, top=30, right=500, bottom=600))
                window = types.SimpleNamespace(handle=8, descendants=lambda: [buffer])
                ui = types.SimpleNamespace(visible_windows=lambda: [window], focus_window=lambda w: events.append(("focus", w.handle)),
                    move_and_click=lambda *args: events.append(("click", args)), wait_until=lambda predicate, description: predicate())
                task = hello.HelloWorldTask(ui, Timing())
                if allowed:
                    self.assertIs(task._open_editor("New Text Document.txt", {7}), window)
                    self.assertEqual(events, [("focus", 8), ("click", (260, 315))])
                else:
                    with self.assertRaises(RuntimeError):
                        task._open_editor("New Text Document.txt", {7})
                    self.assertEqual(events, [])

    def test_notepad_identity_uses_exact_text_under_selected_visible_tab(self):
        filename = "New Text Document.txt"
        for selected, tab_visible, child_name, child_visible, contents, accepted in (
            (True, True, filename, True, "", True),
            (False, True, filename, True, "", False),
            (True, False, filename, True, "", False),
            (True, True, filename + ".bak", True, "", False),
            (True, True, filename, False, "", False),
            (True, True, filename, True, "existing text", False),
        ):
            with self.subTest(selected=selected, visible=tab_visible, name=child_name, child_visible=child_visible, contents=contents):
                events = []
                label = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Text", name=child_name), is_visible=lambda: child_visible)
                close = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Button", name="Close"), is_visible=lambda: True)
                tab = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="TabItem", name="New Text Document.txt. Unmodified."),
                    is_visible=lambda: tab_visible, is_selected=lambda: selected,
                    descendants=lambda control_type=None: [label] if control_type == "Text" else [label, close])
                restored_label = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Text", name=filename), is_visible=lambda: True)
                restored_tab = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="TabItem", name="restored tab"),
                    is_visible=lambda: True, is_selected=lambda: False, descendants=lambda control_type=None: [restored_label])
                buffer = types.SimpleNamespace(element_info=types.SimpleNamespace(name="Text editor", control_type="Document"), is_visible=lambda: True,
                    iface_text=types.SimpleNamespace(DocumentRange=types.SimpleNamespace(GetText=lambda count: contents)),
                    rectangle=lambda: types.SimpleNamespace(left=20, top=30, right=500, bottom=600))
                window = types.SimpleNamespace(handle=8, descendants=lambda: [tab, label, close, restored_tab, restored_label, buffer])
                ui = types.SimpleNamespace(visible_windows=lambda: [window], focus_window=lambda w: events.append(("focus", w.handle)),
                    move_and_click=lambda *args: events.append(("click", args)), wait_until=lambda predicate, description: predicate())
                task = hello.HelloWorldTask(ui, Timing())
                if accepted:
                    self.assertIs(task._open_editor(filename, {7}), window)
                    self.assertEqual(events, [("focus", 8), ("click", (260, 315))])
                else:
                    with self.assertRaises(RuntimeError):
                        task._open_editor(filename, {7})
                    self.assertEqual(events, [])

    def test_exact_selected_visible_tab_without_text_children_remains_supported(self):
        filename = "New Text Document.txt"
        for tab_name, selected, visible, accepted in (
            (filename, True, True, True),
            (filename, False, True, False),
            (filename, True, False, False),
            (filename + ".bak", True, True, False),
        ):
            with self.subTest(name=tab_name, selected=selected, visible=visible):
                events = []
                tab = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="TabItem", name=tab_name),
                    is_visible=lambda: visible, is_selected=lambda: selected, descendants=lambda control_type=None: [])
                buffer = types.SimpleNamespace(element_info=types.SimpleNamespace(name="Text editor", control_type="Document"), is_visible=lambda: True,
                    iface_text=types.SimpleNamespace(DocumentRange=types.SimpleNamespace(GetText=lambda count: "")),
                    rectangle=lambda: types.SimpleNamespace(left=20, top=30, right=500, bottom=600))
                window = types.SimpleNamespace(handle=8, descendants=lambda: [tab, buffer])
                ui = types.SimpleNamespace(visible_windows=lambda: [window], focus_window=lambda w: events.append(("focus", w.handle)),
                    move_and_click=lambda *args: events.append(("click", args)), wait_until=lambda predicate, description: predicate())
                task = hello.HelloWorldTask(ui, Timing())
                if accepted:
                    self.assertIs(task._open_editor(filename, {7}), window)
                    self.assertEqual(events, [("focus", 8), ("click", (260, 315))])
                else:
                    with self.assertRaises(RuntimeError):
                        task._open_editor(filename, {7})
                    self.assertEqual(events, [])

    def test_browser_warning_in_accessible_body_is_rejected(self):
        edit = types.SimpleNamespace(element_info=types.SimpleNamespace(automation_id="view_1017"), get_value=lambda: "https://www.apple.com")
        warning = types.SimpleNamespace(window_text=lambda: "Your connection isn't private")
        doc = types.SimpleNamespace(element_info=types.SimpleNamespace(automation_id="RootWebArea"),
            legacy_properties=lambda: {"Value": "https://www.apple.com", "State": 0},
            is_visible=lambda: True, descendants=lambda: [warning], window_text=lambda: "https://www.apple.com")
        window = types.SimpleNamespace(descendants=lambda control_type: [edit] if control_type == "Edit" else [doc])
        ui = ui_module.UI(Timing())
        ui.wait_until = lambda predicate, description, timeout: predicate()
        with self.assertRaises(RuntimeError):
            ui.wait_browser_document(window, "https://www.apple.com")
        # Some document providers expose the body through TextPattern while
        # child names and the document title contain no warning text.
        warning.window_text = lambda: ""
        doc.iface_text = types.SimpleNamespace(DocumentRange=types.SimpleNamespace(GetText=lambda count: "Your connection isn't private"))
        with self.assertRaises(RuntimeError):
            ui.wait_browser_document(window, "https://www.apple.com")

    def test_extension_confirmation_requires_new_explorer_dialog_exact_body_and_yes_id(self):
        body = "If you change a file name extension, the file might become unusable.\n\nAre you sure you want to change it?"
        for process, old_handles, message, control_id, expected in (
            ("explorer.exe", set(), body, 6, True),
            ("other.exe", set(), body, 6, False),
            ("explorer.exe", {50}, body, 6, False),
            ("explorer.exe", set(), "Overwrite existing file?", 6, False),
            ("explorer.exe", set(), body, 7, False),
        ):
            with self.subTest(process=process, old=old_handles, message=message, id=control_id):
                events = []
                text = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Text"), window_text=lambda: message)
                button = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Button", automation_id=""), window_text=lambda: "&Yes", is_visible=lambda: True,
                    rectangle=lambda: types.SimpleNamespace(left=10, top=10, right=80, bottom=35))
                window = types.SimpleNamespace(handle=50, is_visible=lambda: True, descendants=lambda: [text, button])
                ui = types.SimpleNamespace(visible_windows=lambda: [window], foreground_window=lambda: window,
                    window_executable=lambda w: process, control_id=lambda c: control_id,
                    move_and_click=lambda *args: events.append(args))
                task = hello.HelloWorldTask(ui, Timing())
                self.assertEqual(task._confirm_extension_change(old_handles), expected)
                self.assertEqual(bool(events), expected)

    def test_extension_confirmation_accepts_live_uia_yes_with_native_id_zero(self):
        body = "If you change a file name extension, the file might become unusable.\n\nAre you sure you want to change it?"
        for automation_id, label, visible, duplicate, foreground, accepted in (
            ("CommandButton_6", "Yes", True, False, True, True),
            ("CommandButton_7", "Yes", True, False, True, False),
            ("CommandButton_7", "No", True, False, True, False),
            ("CommandButton_6", "No", True, False, True, False),
            ("CommandButton_6", "Yes", False, False, True, False),
            ("CommandButton_6", "Yes", True, True, True, False),
            ("CommandButton_6", "Yes", True, False, False, False),
        ):
            with self.subTest(id=automation_id, label=label, visible=visible, duplicate=duplicate, foreground=foreground):
                clicks = []
                text = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Text"), window_text=lambda: body)
                yes = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Button", automation_id=automation_id),
                    window_text=lambda: label, is_visible=lambda: visible,
                    rectangle=lambda: types.SimpleNamespace(left=10, top=10, right=80, bottom=35))
                no = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Button", automation_id="CommandButton_7"),
                    window_text=lambda: "No", is_visible=lambda: True)
                window = types.SimpleNamespace(handle=1837254, is_visible=lambda: True, descendants=lambda: [text, yes, no] + ([yes] if duplicate else []))
                ui = types.SimpleNamespace(visible_windows=lambda: [window],
                    foreground_window=lambda: window if foreground else types.SimpleNamespace(handle=99, is_visible=lambda: True, descendants=lambda: []),
                    window_executable=lambda w: "explorer.exe", control_id=lambda c: 0,
                    move_and_click=lambda *args: clicks.append(args))
                task = hello.HelloWorldTask(ui, Timing())
                self.assertEqual(task._confirm_extension_change(set()), accepted)
                self.assertEqual(bool(clicks), accepted)

    def test_extension_confirmation_finds_foreground_desktop_child_not_in_windows(self):
        body = "If you change a file name extension, the file might become unusable.\n\nAre you sure you want to change it?"
        for visible, previous_handles, accepted in ((True, set(), True), (False, set(), False), (True, {1837254}, False)):
            with self.subTest(visible=visible, previous_handles=previous_handles):
                clicks = []
                text = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Text"), window_text=lambda: body)
                yes = types.SimpleNamespace(element_info=types.SimpleNamespace(control_type="Button", automation_id="CommandButton_6"),
                    window_text=lambda: "Yes", is_visible=lambda: True,
                    rectangle=lambda: types.SimpleNamespace(left=10, top=10, right=80, bottom=35))
                window = types.SimpleNamespace(handle=1837254, is_visible=lambda: visible, descendants=lambda: [text, yes])
                ui = types.SimpleNamespace(visible_windows=lambda: [], foreground_window=lambda: window,
                    window_executable=lambda w: "explorer.exe", control_id=lambda c: 0,
                    move_and_click=lambda *args: clicks.append(args))
                task = hello.HelloWorldTask(ui, Timing())
                self.assertEqual(task._confirm_extension_change(previous_handles), accepted)
                self.assertEqual(bool(clicks), accepted)

    def test_console_success_requires_actual_output_and_zero_exit_line(self):
        verify = hello.HelloWorldTask._execution_succeeded
        self.assertFalse(verify("PS> & 'python' 'script'; Write-Output ('SHA_EXIT_CODE=' + $LASTEXITCODE)"))
        self.assertFalse(verify("Hello, world!\nSHA_EXIT_CODE=1\nPS>"))
        self.assertTrue(verify("PS> command\r\nHello, world!\r\nSHA_EXIT_CODE=0\r\nPS>"))

    def test_browser_readiness_rejects_stale_document_after_address_changes(self):
        edit = types.SimpleNamespace(element_info=types.SimpleNamespace(automation_id="view_1017"), get_value=lambda: "https://www.apple.com")
        props = {"Value": "https://www.samsung.com", "State": 0}
        doc = types.SimpleNamespace(element_info=types.SimpleNamespace(automation_id="RootWebArea"),
            legacy_properties=lambda: props, is_visible=lambda: True, descendants=lambda: [types.SimpleNamespace(window_text=lambda: "Apple content")], window_text=lambda: "Apple")
        window = types.SimpleNamespace(descendants=lambda control_type: [edit] if control_type == "Edit" else [doc])
        ui = ui_module.UI(Timing())
        observations = []
        def wait(predicate, description, timeout):
            observations.append(bool(predicate()))
            props["Value"] = "https://www.apple.com"
            observations.append(bool(predicate()))
            return doc
        ui.wait_until = wait
        ui.wait_browser_document(window, "https://www.apple.com")
        self.assertEqual(observations, [False, True])

    def test_repeated_filename_selection_avoids_case_insensitive_collisions(self):
        task = hello.HelloWorldTask(None, Timing())
        self.assertEqual(task._choose_script_name([]), "helloworld.py")
        self.assertEqual(task._choose_script_name(["HELLOWORLD.PY"]), "helloworld_2.py")
        self.assertEqual(task._choose_script_name(["helloworld.py", "helloworld_2.py"]), "helloworld_3.py")

    def test_copied_path_must_match_exact_selected_script(self):
        self.assertEqual(hello.HelloWorldTask._validate_script_path(
            '"C:\\Users\\Person\\Desktop\\helloworld_2.py"', "helloworld_2.py", "C:\\Users\\Person\\Desktop"),
            "C:\\Users\\Person\\Desktop\\helloworld_2.py")
        for value in ('"C:\\Desktop\\helloworld.py"', "helloworld_2.py", '"C:\\Desktop\\helloworld_2.py"; evil'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                hello.HelloWorldTask._validate_script_path(value, "helloworld_2.py", "C:\\Users\\Person\\Desktop")

    def test_owned_browser_address_and_scroll_order(self):
        ui = BrowserUI()
        browser.BrowserTask(None, ui, Timing(), urls=["https://www.apple.com"]).run()
        address = ui.events.index(("hotkey", ("ctrl", "l"), 20))
        typed = ui.events.index(("text", "https://www.apple.com"))
        ready = ui.events.index(("ready", 20, "https://www.apple.com"))
        self.assertLess(address, typed)
        scrolls = [(i, event) for i, event in enumerate(ui.events) if event[0] == "pointer" and event[3] and event[3][0] == "scroll"]
        self.assertTrue(scrolls)
        for index, event in scrolls:
            self.assertGreater(index, ready)
            self.assertTrue(100 < event[1] < 1100 and 250 < event[2] < 900)
            self.assertTrue(1 <= abs(event[3][-1]) <= 5)
        self.assertIn(("hotkey", ("alt", "f4"), 20), ui.events)
        self.assertNotIn(("hotkey", ("alt", "f4"), 10), ui.events)

    def test_browser_load_failure_still_closes_only_owned_window(self):
        ui = BrowserUI(fail=True)
        with self.assertRaisesRegex(RuntimeError, "load failed"):
            browser.BrowserTask(None, ui, Timing(), urls=["https://www.apple.com"]).run()
        self.assertIn(("hotkey", ("alt", "f4"), 20), ui.events)
        self.assertNotIn(("hotkey", ("alt", "f4"), 10), ui.events)

    def test_browser_cleanup_error_preserves_original_load_error(self):
        ui = BrowserUI(fail=True)
        original_focus = ui.focus_window
        def focus(window):
            if ui.events and ui.events[-1][0] == "ready":
                raise RuntimeError("cleanup focus failed")
            original_focus(window)
        ui.focus_window = focus
        with self.assertRaisesRegex(RuntimeError, "load failed") as caught:
            browser.BrowserTask(None, ui, Timing(), urls=["https://www.apple.com"]).run()
        self.assertTrue(any("cleanup focus failed" in note for note in caught.exception.__notes__))

    def test_browser_cancellation_during_cleanup_propagates_as_abort(self):
        ui = BrowserUI(fail=True)
        original_focus = ui.focus_window
        def focus(window):
            if ui.events and ui.events[-1][0] == "ready":
                raise FailSafeException("stop cleanup")
            original_focus(window)
        ui.focus_window = focus
        with self.assertRaises(FailSafeException):
            browser.BrowserTask(None, ui, Timing(), urls=["https://www.apple.com"]).run()

    def test_context_menu_input_failsafe_propagates(self):
        control = types.SimpleNamespace(element_info=types.SimpleNamespace(handle=1, runtime_id=[1]),
            is_visible=lambda: True, window_text=lambda: "New", rectangle=lambda: types.SimpleNamespace(left=10, top=10, right=40, bottom=40))
        root = types.SimpleNamespace(descendants=lambda: [control])
        desktop = types.SimpleNamespace(window=lambda **kwargs: types.SimpleNamespace(wrapper_object=lambda: root), windows=lambda: [])
        ui = ui_module.UI(Timing())
        ui.move_and_click = lambda *args: (_ for _ in ()).throw(FailSafeException("stop"))
        with patch.object(ui_module, "Desktop", lambda **kwargs: desktop):
            with self.assertRaises(FailSafeException):
                ui.click_context_menu_item("New")

if __name__ == "__main__": unittest.main()
