import time
import logging


logger = logging.getLogger(__name__)


class ReturnToDesktopTask:
    """Minimize foreground application windows using only UI observation/actions."""

    def __init__(
        self,
        ui,
        minimize_selector=None,
        minimize_timeout=3,
        poll_interval=0.1,
        max_windows=30,
    ):
        self.ui = ui
        # English accessible name observed during local inspection.  Deployments
        # may pass a locale- or application-specific selector instead.
        self.minimize_selector = (
            {"title": "Minimize", "control_type": "Button"}
            if minimize_selector is None
            else minimize_selector
        )
        self.minimize_timeout = minimize_timeout
        self.poll_interval = poll_interval
        self.max_windows = max_windows

    def run(self):
        previous_handle = None
        minimized_windows = 0

        while True:
            current = self.ui.get_current()
            logger.info("Desktop check: %r", current)
            if current is None:
                raise RuntimeError("Cannot identify the foreground window")

            foreground_handle = current["handle"]
            if current.get("is_taskbar", False) or current.get("is_auxiliary", False):
                remaining = self.ui.list_visible_application_windows()
                if not remaining:
                    if self.ui.get_desktop() is not None:
                        logger.info("Desktop confirmed with a shell/auxiliary foreground window")
                        return
                    raise RuntimeError("No visible applications, but Windows desktop is unavailable")
                # The top exposed application can be minimized by clicking its
                # actual button even while the taskbar owns keyboard focus.
                current = remaining[0]
                logger.info("Shell/auxiliary window focused; remaining top window: %r", current)
            elif self.ui.is_desktop(current):
                logger.info("Desktop confirmed")
                return

            handle = current["handle"]
            if handle == previous_handle:
                raise RuntimeError("Minimization did not change the foreground window")
            if minimized_windows >= self.max_windows:
                raise RuntimeError(
                    f"Desktop was not reached after minimizing {self.max_windows} windows"
                )

            button = self.ui.find_element(handle, **self.minimize_selector)
            if button is None:
                raise RuntimeError(
                    f"Minimize button not found: {current['title']!r}; "
                    f"window={current!r}; selector={self.minimize_selector!r}"
                )
            logger.info("Clicking Minimize for handle=%s title=%r", handle, current["title"])
            x, y = self.ui.get_coords(button)
            self.ui.move_and_click(x, y, button="left", expected_window=foreground_handle)
            self._wait_for_minimization(handle, current["title"])
            previous_handle = handle
            minimized_windows += 1

    def _wait_for_minimization(self, handle, title):
        deadline = time.monotonic() + self.minimize_timeout
        while time.monotonic() < deadline:
            current = self.ui.get_current()
            if (
                self.ui.is_minimized(handle)
                and current is not None
                and current["handle"] != handle
            ):
                return
            time.sleep(self.poll_interval)
        raise RuntimeError(f"Window did not minimize: {title}")
