class SessionState:
    """In-memory window identity cache, validated against a fresh observation."""

    _WINDOW_FIELDS = (
        "handle",
        "process_id",
        "title",
        "class_name",
        "is_desktop",
    )

    def __init__(self):
        self._windows = {}

    def remember(self, app_id, window):
        """Remember a window's identity for one application in this process only."""
        self._windows[app_id] = self._copy_window(window)

    def get_window(self, app_id, live_windows):
        """Return a fresh matching observation, or evict stale remembered state."""
        remembered = self._windows.get(app_id)
        if remembered is None:
            return None

        refreshed = self._validated_live_window(remembered, live_windows)
        if refreshed is None:
            del self._windows[app_id]
            return None

        self._windows[app_id] = refreshed
        return refreshed.copy()

    @classmethod
    def _validated_live_window(cls, remembered, live_windows):
        live_window = next(
            (
                observed
                for observed in live_windows
                if observed["handle"] == remembered["handle"]
            ),
            None,
        )
        if live_window is None or any(
            live_window[field] != remembered[field]
            for field in ("process_id", "class_name")
        ):
            return None
        return cls._copy_window(live_window)

    @classmethod
    def _copy_window(cls, window):
        return {field: window[field] for field in cls._WINDOW_FIELDS}
