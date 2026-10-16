"""Command-line entry point. Help/validation never import desktop libraries."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import uuid

from core.runner import RunResult, run_session
from core.timing import Timing


TASK_NAMES = ("browser", "python")


def positive_seconds(value):
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number of seconds") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return seconds


def countdown_seconds(value):
    try:
        seconds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a whole number of seconds") from exc
    if seconds < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return seconds


def parser():
    cli = argparse.ArgumentParser(description="Run real desktop tasks for a bounded activity session.")
    cli.add_argument("--duration", type=positive_seconds, default=900, help="activity seconds, excluding countdown (default: 900)")
    cli.add_argument("--tasks", nargs="+", choices=TASK_NAMES, default=list(TASK_NAMES), help="task registry names to select from")
    cli.add_argument("--seed", type=int, help="repeat random choices with this integer seed")
    cli.add_argument("--once", action="store_true", help="stop after one completed task (duration still applies)")
    cli.add_argument("--countdown", type=countdown_seconds, default=5, help="startup countdown seconds (default: 5)")
    cli.add_argument("--log-dir", type=Path, default=None, help="diagnostic directory outside the source tree")
    return cli


def create_desktop_tasks(timing, rng, names):
    # These imports are deliberately after argument validation and countdown.
    import pyautogui
    from core.process import Process
    from core.ui import UI
    from tasks.browser import BrowserTask
    from tasks.default import DefaultTask
    from tasks.helloworld import HelloWorldTask
    from tasks.play import PlayTask

    ui = UI(timing, rng)
    play_task = PlayTask(ui, timing)
    timing.pause_action = play_task.move_locally
    default_task = DefaultTask(ui, timing)
    factories = {
        "browser": lambda: BrowserTask(Process(), ui, timing),
        "python": lambda: HelloWorldTask(ui, timing),
    }
    return {name: factories[name]() for name in names}, default_task.run, (pyautogui.FailSafeException,)


def log_directory(requested):
    if requested is None:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "state")))
        requested = base / "SyntheticHumanAgent" / "logs"
    directory = requested.expanduser().resolve()
    source = Path(__file__).resolve().parent
    if directory == source or source in directory.parents:
        raise ValueError("diagnostic logs must be outside the source tree")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        directory = log_directory(args.log_dir)
    except (OSError, ValueError) as exc:
        cli.error(str(exc))
    path = directory / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}.jsonl"
    try:
        stream = path.open("x", encoding="utf-8")
    except OSError as exc:
        print(f"Cannot create diagnostic log: {exc}", file=sys.stderr)
        return 1
    with stream:
        def emit(event):
            record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
        emit({"event": "startup", "duration": args.duration, "tasks": args.tasks,
              "seed": args.seed, "once": args.once, "countdown": args.countdown})
        print(f"Diagnostic log: {path}", flush=True)
        started = time.monotonic()
        rng = random.Random(args.seed)
        timing = Timing(rng=rng)
        # Existing tasks also use the module-level generator.
        random.seed(args.seed)
        try:
            for remaining in range(args.countdown, 0, -1):
                print(f"Starting desktop actions in {remaining}...", flush=True)
                timing.sleep(1)
            tasks, prepare, abort_exceptions = create_desktop_tasks(timing, rng, args.tasks)
            result = run_session(tasks, duration=args.duration, once=args.once,
                                 prepare=prepare, timing=timing, rng=rng, emit=emit,
                                 abort_exceptions=abort_exceptions)
        except KeyboardInterrupt as exc:
            result = RunResult("aborted", 0, time.monotonic() - started, error=f"KeyboardInterrupt: {exc}")
            emit({"event": "startup_aborted", "error": result.error})
            emit({"event": "session_end", **result.__dict__})
        except Exception as exc:
            desktop_module = sys.modules.get("pyautogui")
            abort_types = (desktop_module.FailSafeException,) if desktop_module is not None else ()
            status = "aborted" if isinstance(exc, abort_types) else "error"
            result = RunResult(status, 0, time.monotonic() - started, error=f"{type(exc).__name__}: {exc}")
            emit({"event": "startup_aborted" if status == "aborted" else "startup_error", "error": result.error})
            emit({"event": "session_end", **result.__dict__})
        print(f"Status: {result.status}; completed tasks: {result.completed}; elapsed: {result.elapsed:.2f}s", flush=True)
        if result.interrupted_task:
            print(f"Incomplete task: {result.interrupted_task}", flush=True)
        if result.error:
            print(result.error, file=sys.stderr, flush=True)
        return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
