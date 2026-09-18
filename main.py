import argparse
import json
import logging
from pathlib import Path

from core.timing import Timing
from core.session_state import SessionState
from core.ui import UI
from core.task_runner import TaskRunner
from tasks.browser import BrowserTask
from tasks.return_to_desktop import ReturnToDesktopTask

def main():
    parser = argparse.ArgumentParser(description="Run the visible browser task")
    parser.add_argument(
        "--profile", type=Path,
        default=Path(__file__).parent / "profiles" / "windows_edge.json",
        help="Selectors inspected on the Windows machine running this task",
    )
    args = parser.parse_args()
    log_path = Path(__file__).parent / "last_run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
        ],
    )
    logging.info("Profile: %s; diagnostic log: %s", args.profile, log_path)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    timing = Timing()
    ui = UI(timing)
    session = SessionState()
    desktop_task = ReturnToDesktopTask(ui, minimize_selector=profile["minimize_selector"])
    task = BrowserTask(ui, session, profile)
    try:
        TaskRunner(ui, desktop_task=desktop_task).run(task)
    except Exception:
        logging.exception("Task stopped before completion")
        raise SystemExit(1)
    print("done.")

if __name__ == "__main__":
    main()
