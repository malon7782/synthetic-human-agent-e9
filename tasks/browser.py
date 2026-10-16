import random
import pyautogui
from urllib.parse import urlsplit
from core.timing import DeadlineReached


class BrowserTask:
    def __init__(self, process, ui, timing, urls=None):
        self.process = process
        self.ui = ui
        self.timing = timing
        self.urls = tuple(urls if urls is not None else (
            "https://www.samsung.com", "https://www.apple.com", "https://www.dell.com",
        ))
        if not self.urls or any(urlsplit(url).scheme != "https" or not urlsplit(url).netloc for url in self.urls):
            raise ValueError("BrowserTask requires explicit HTTPS URLs")

    def _focused_edge(self, excluded=()):
        window = self.ui.foreground_window()
        if window.handle not in excluded and self.ui.window_executable(window).casefold() == "msedge.exe":
            return window
        return None

    def run(self):
        self.ui.fetch_desktop()

        x, y = self.ui.get_coords_desktop("Microsoft Edge")
        self.ui.curve_move(x, y)
        self.timing.delay()

        self.ui.move_and_click(x, y, "double")
        launched = self.ui.wait_until(self._focused_edge, "desktop shortcut to focus Microsoft Edge")
        self.ui.focus_window(launched)
        before = {window.handle for window in self.ui.visible_windows()}
        self.ui.hotkey("ctrl", "n")
        owned = self.ui.wait_until(lambda: self._focused_edge(before), "a new owned Microsoft Edge window")
        cleanup = True
        failure = None
        try:
            self.ui.focus_window(owned)
            self.ui.hotkey("win", "up")
            for url in self.urls:
                self.ui.focus_window(owned)
                self.ui.hotkey("ctrl", "l")
                self.ui.type_text(url)
                self.ui.press("enter")
                self.ui.wait_browser_document(owned, url)
                rect = owned.rectangle()
                if rect.right - rect.left < 300 or rect.bottom - rect.top < 300:
                    raise RuntimeError("The owned Edge window is too small for safe content scrolling")
                rng = getattr(self.ui, "rng", random)
                for _ in range(4):
                    self.ui.focus_window(owned)
                    x = rng.randint(rect.left + 100, rect.right - 100)
                    y = rng.randint(rect.top + 180, rect.bottom - 80)
                    self.ui.move_and_click(x, y, "scroll", None, None, -rng.randint(1, 5))
                    self.timing.delay()
        except (KeyboardInterrupt, pyautogui.FailSafeException, DeadlineReached):
            cleanup = False
            raise
        except Exception as error:
            failure = error
            raise
        finally:
            # Never close the shortcut's reused window or any pre-existing tabs.
            if cleanup:
                try:
                    if any(window.handle == owned.handle for window in self.ui.visible_windows()):
                        self.ui.focus_window(owned)
                        self.ui.hotkey("alt", "f4")
                    self.ui.wait_until(
                        lambda: not any(window.handle == owned.handle for window in self.ui.visible_windows()),
                        "owned Microsoft Edge window to close", timeout=10,
                    )
                except (KeyboardInterrupt, pyautogui.FailSafeException, DeadlineReached):
                    raise
                except Exception as error:
                    if failure is None:
                        raise
                    failure.add_note(f"Browser cleanup also failed: {error}")
