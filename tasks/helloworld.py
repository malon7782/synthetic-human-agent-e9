import os
import ntpath
import sys

import pyperclip


class HelloWorldTask:
    def __init__(self, ui, timing):
        self.ui = ui
        self.timing = timing

    @staticmethod
    def _choose_script_name(names):
        existing = {name.casefold() for name in names}
        if "helloworld.py" not in existing:
            return "helloworld.py"
        number = 2
        while f"helloworld_{number}.py" in existing:
            number += 1
        return f"helloworld_{number}.py"

    @staticmethod
    def _validate_script_path(copied, script_name, desktop_directory):
        path = copied.strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if (not ntpath.isabs(path) or '"' in path or "\n" in path or "\r" in path
                or ntpath.normcase(ntpath.normpath(path)) != ntpath.normcase(ntpath.normpath(ntpath.join(desktop_directory, script_name)))):
            raise RuntimeError(f"Copy as path did not copy the expected {script_name!r}: {copied!r}")
        return path

    @staticmethod
    def _validate_script_file(path, expected_content):
        try:
            with open(path, encoding="utf-8-sig") as script:
                content = script.read()
        except (OSError, UnicodeError) as error:
            raise RuntimeError(f"Could not read the created script {path!r}") from error
        if content not in (expected_content, expected_content + "\n"):
            raise RuntimeError(f"The created script content differs from the intended script: {path!r}")

    def _wait_desktop(self, predicate, description):
        def observed():
            self.ui.fetch_desktop()
            return predicate()
        return self.ui.wait_until(observed, description)

    @staticmethod
    def _execution_succeeded(output):
        lines = {line.strip() for line in output.splitlines()}
        return "Hello, world!" in lines and "SHA_EXIT_CODE=0" in lines

    @staticmethod
    def _console_output(window):
        """Read accessible console text without clipboard or keyboard actions."""
        texts = []
        for control in [window] + window.descendants():
            texts.append(control.window_text())
            try:
                texts.append(control.iface_text.DocumentRange.GetText(-1))
            except Exception:
                # Most UIA controls do not implement the Text pattern.
                continue
        return "\n".join(texts)

    def _blank_desktop_point(self):
        """Find a point away from the cached desktop icons and taskbar."""
        screen_width, screen_height = self.ui.screen_size()
        icon_bounds = tuple(self.ui.desktop_icons.values())

        for y_ratio in (0.55, 0.45, 0.65, 0.35, 0.75):
            for x_ratio in (0.70, 0.80, 0.60, 0.90, 0.50):
                x = round(screen_width * x_ratio)
                y = round(screen_height * y_ratio)
                if all(
                    not (left - 70 <= x <= right + 70 and top - 45 <= y <= bottom + 45)
                    for left, top, right, bottom in icon_bounds
                ):
                    return x, y

        raise RuntimeError("Could not find a clear point on the desktop")

    def _find_new_desktop_item(self, previous_names):
        new_names = set(self.ui.desktop_icons) - previous_names
        if len(new_names) != 1:
            raise RuntimeError(
                "Expected exactly one new desktop item after creating a text document; "
                f"new items: {sorted(new_names)}"
            )
        return new_names.pop()

    def _open_editor(self, document_name, previous_handles):
        def observed():
            matches = []
            for window in self.ui.visible_windows():
                if window.handle in previous_handles:
                    continue
                controls = window.descendants()
                identities = [control for control in controls
                              if control.element_info.name == document_name
                              and control.element_info.control_type in ("Document", "Edit")
                              and control.is_visible()]
                # Live Notepad exposes the exact filename in a Text child;
                # the selected tab's own name includes document-state text.
                for control in controls:
                    if (control.element_info.control_type == "TabItem"
                            and control.is_visible() and control.is_selected()
                            and (control.element_info.name == document_name
                                 or any(child.element_info.name == document_name and child.is_visible()
                                        for child in control.descendants(control_type="Text")))):
                        identities.append(control)
                if not identities:
                    continue
                buffers = []
                for control in controls:
                    if control.element_info.control_type not in ("Document", "Edit") or not control.is_visible():
                        continue
                    try:
                        text = control.iface_text.DocumentRange.GetText(-1)
                    except Exception:
                        continue
                    buffers.append((control, text))
                if len(buffers) == 1 and buffers[0][1] == "":
                    matches.append((window, buffers[0][0]))
            return matches[0] if len(matches) == 1 else None
        result = self.ui.wait_until(observed, f"a new editor window with exact document identity {document_name!r} and one empty accessible buffer")
        if result is None:
            raise RuntimeError("The newly opened editor/document identity could not be verified")
        editor, buffer = result
        self.ui.focus_window(editor)
        if buffer.iface_text.DocumentRange.GetText(-1) != "":
            raise RuntimeError("The verified editor buffer is no longer empty")
        rect = buffer.rectangle()
        self.ui.move_and_click((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        return editor

    def _confirm_extension_change(self, previous_handles):
        # Exact English resource text inspected in shell32.dll.mui by root.
        expected = "If you change a file name extension, the file might become unusable. Are you sure you want to change it?"
        # Explorer can parent this dialog under the desktop rather than expose
        # it in top-level windows(); its actual foreground handle is authoritative.
        window = self.ui.foreground_window()
        if window.handle in previous_handles or not window.is_visible():
            return False
        if self.ui.window_executable(window).casefold() != "explorer.exe":
            return False
        controls = window.descendants()
        body = " ".join(" ".join(control.window_text().split()) for control in controls
                        if control.element_info.control_type == "Text").strip()
        if body != expected:
            return False
        buttons = [control for control in controls
                   if control.element_info.control_type == "Button" and control.is_visible()
                   and control.window_text().replace("&", "").strip() == "Yes"
                   and (self.ui.control_id(control) == 6
                        or control.element_info.automation_id == "CommandButton_6")]
        if len(buttons) != 1:
            return False
        rect = buttons[0].rectangle()
        self.ui.move_and_click((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        return True

    def _new_console(self, previous_handles):
        window = self.ui.foreground_window()
        if window.handle in previous_handles:
            return None
        # Classic Console Host and Windows Terminal host the launched shell.
        if self.ui.window_executable(window).casefold() in ("powershell.exe", "windowsterminal.exe", "conhost.exe"):
            return window
        return None

    def _run_with_powershell(self, script_name, expected_content):
        """Copy the script path from its context menu and run it in PowerShell."""
        self.ui.fetch_desktop()
        x, y = self.ui.get_coords_desktop(script_name)
        pyperclip.copy("")
        self.ui.move_and_click(x, y, "right")
        self.timing.pause()
        self.ui.click_context_menu_item("Copy as path")
        self.timing.pause()

        script_path = self._validate_script_path(pyperclip.paste(), script_name, self.ui.desktop_directory())
        self._validate_script_file(script_path, expected_content)

        self.timing.delay()
        previous_handles = {window.handle for window in self.ui.visible_windows()}
        self.ui.hotkey("win", "r")
        self.timing.delay()
        self.ui.type_text("powershell")
        self.ui.press("enter")

        powershell = self.ui.wait_until(lambda: self._new_console(previous_handles), "new PowerShell console window")
        self.ui.focus_window(powershell)

        self.timing.pause()
        python = sys.executable.replace("'", "''")
        self.ui.type_text(f"& '{python}' ")
        pyperclip.copy("'" + script_path.replace("'", "''") + "'")
        self.ui.hotkey("ctrl", "v")
        self.timing.pause()
        self.ui.type_text("; Write-Output ('SHA_EXIT_CODE=' + $LASTEXITCODE)")
        self.ui.press("enter")
        self.ui.wait_until(lambda: self._execution_succeeded(self._console_output(powershell)),
                           "visible Hello, world! output and SHA_EXIT_CODE=0; console must expose accessible text",
                           timeout=30)
        # Only actual output lines establish execution. Keep the console visible.
        return {"status": "execution_verified", "script_path": script_path,
                "powershell_handle": powershell.handle}

    def run(self):
        """Create and run the script after DefaultTask prepares the desktop."""
        self.ui.fetch_desktop()
        script_name = self._choose_script_name(self.ui.desktop_icons)

        previous_names = set(self.ui.desktop_icons)
        x, y = self._blank_desktop_point()

        # Open the desktop context menu, then choose New > Text Document.
        self.ui.press("esc")
        self.ui.move_and_click(x, y, "right")
        self.timing.delay()
        self.ui.click_context_menu_item("New")
        self.timing.delay()
        self.ui.click_context_menu_item("Text Document")
        self.ui.press("enter")
        self.timing.delay()

        self._wait_desktop(lambda: set(self.ui.desktop_icons) - previous_names,
                           "a newly created desktop text document")
        document_name = self._find_new_desktop_item(previous_names)
        if not document_name.casefold().endswith(".txt"):
            raise RuntimeError("Show file name extensions and use English New > Text Document before running HelloWorldTask; "
                               f"observed new item: {document_name!r}")

        x, y = self.ui.get_coords_desktop(document_name)
        created_path = ntpath.join(self.ui.desktop_directory(), document_name)
        if not os.path.isfile(created_path) or os.path.getsize(created_path) != 0:
            raise RuntimeError(f"The freshly created Desktop document is not an empty file: {created_path!r}")
        previous_handles = {window.handle for window in self.ui.visible_windows()}
        self.ui.move_and_click(x, y, "double")
        editor = self._open_editor(document_name, previous_handles)

        script_text = self.ui.type_from_corpus("helloworld", typo_rate=0)
        self.ui.hotkey("ctrl", "s")
        self.timing.delay()
        self.ui.focus_window(editor)
        self.ui.click_window_button("close")
        self.timing.pause()

        self.ui.fetch_desktop()
        if any(name.casefold() == script_name.casefold() for name in self.ui.desktop_icons):
            raise RuntimeError(f"A file named {script_name!r} appeared before rename; preserving both files")
        x, y = self.ui.get_coords_desktop(document_name)
        self.ui.move_and_click(x, y, "right")
        self.timing.delay()
        self.ui.click_context_menu_item("Rename")
        self.timing.delay()
        self.ui.hotkey("ctrl", "a")
        self.ui.type_text(script_name)
        before_rename = {window.handle for window in self.ui.visible_windows()}
        self.ui.press("enter")
        self.timing.delay()
        confirmed = False
        def renamed():
            nonlocal confirmed
            if script_name in self.ui.desktop_icons and document_name not in self.ui.desktop_icons:
                return True
            if not confirmed:
                confirmed = self._confirm_extension_change(before_rename)
            return False
        self._wait_desktop(renamed, f"rename to {script_name!r}; only a new Explorer dialog matching the verified extension-warning resource can be confirmed")
        return self._run_with_powershell(script_name, script_text)
