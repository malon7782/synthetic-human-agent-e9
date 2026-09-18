"""Read-only control inspection to configure the deployment PC."""

import argparse
import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.timing import Timing
from core.ui import UI


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handle", type=int, help="Inspect this window handle instead of the foreground")
    parser.add_argument("--delay", type=float, default=5, help="Seconds to manually select the target interface")
    args = parser.parse_args()
    if args.delay < 0:
        parser.error("--delay must be non-negative")
    print("Read-only inspection: manually select the target window during the delay.", flush=True)
    time.sleep(args.delay)
    ui = UI(Timing())
    current = ui.get_window(args.handle) if args.handle is not None else ui.get_current()
    result = {"current": current, "windows": ui.list_windows()}
    if current is not None:
        result["controls"] = ui.find_elements(current["handle"])
    result["desktop"] = ui.get_desktop()
    if result["desktop"] is not None:
        result["desktop_controls"] = ui.find_elements(result["desktop"]["handle"])
    taskbar = ui.find_window(class_name="Shell_TrayWnd")
    result["taskbar"] = taskbar
    if taskbar is not None:
        result["taskbar_controls"] = ui.find_elements(taskbar["handle"])
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
