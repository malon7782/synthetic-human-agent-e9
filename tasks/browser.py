import re


from tasks.open_application import OpenApplicationTask


class BrowserTask:
    """Prepare a browser page, then click its search field and type."""

    requires_desktop = True

    def __init__(self, ui, session, profile, text="NTU Hackathon"):
        self.ui = ui
        self.session = session
        self.application = profile["application"]
        self.selectors = profile["browser"]
        self.text = text

    def _is_browser(self, current):
        return current is not None and re.fullmatch(
            self.application["title_re"], current["title"]
        ) is not None

    def is_ready(self, current):
        return (
            self._is_browser(current)
            and self.ui.find_element(current["handle"], **self.selectors["search_box"]) is not None
        )

    def prepare(self):
        OpenApplicationTask(self.ui, self.session, self.application).run()
        current = self.ui.get_current()
        if not self._is_browser(current):
            raise RuntimeError("Browser is not the foreground window")
        if self.is_ready(current):
            return

        # Reuse a visible matching tab when the target profile defines one.
        tab_selector = self.selectors.get("ready_tab")
        tab = self.ui.find_element(current["handle"], **tab_selector) if tab_selector else None
        if tab is not None:
            self.ui.move_and_click(
                *self.ui.get_coords(tab), button="left", expected_window=current["handle"]
            )
        else:
            self.ui.press_keys("ctrl", "t", expected_window=current["handle"])

    def run(self):
        current = self.ui.get_current()
        if not self._is_browser(current):
            raise RuntimeError("Browser changed before task execution")
        search_box = self.ui.find_element(current["handle"], **self.selectors["search_box"])
        x, y = self.ui.get_coords(search_box)
        self.ui.move_and_click(x, y, button="left", expected_window=current["handle"])
        self.session.remember(self.application["id"], current)
        self.ui.type_text(self.text, expected_window=current["handle"])
