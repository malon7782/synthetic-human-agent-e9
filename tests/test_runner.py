"""Runner tests use an injected clock and inert tasks; no desktop access."""
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import types
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Task:
    def __init__(self, action):
        self.action = action
        self.calls = 0

    def run(self):
        self.calls += 1
        return self.action()


class RunnerTests(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec("core.runner"), "bounded runner is missing")
        from core.runner import run_session
        return run_session

    def test_budget_stops_before_next_task(self):
        run = self.runner()
        clock = Clock()
        task = Task(lambda: clock.sleep(1))
        result = run({"browser": task}, duration=2, clock=clock)
        self.assertEqual(task.calls, 2)
        self.assertEqual(result.completed, 2)
        self.assertEqual(result.status, "duration_elapsed")
        self.assertEqual(result.exit_code, 0)

    def test_first_failure_stops_without_success_or_retry(self):
        run = self.runner()
        events = []
        task = Task(lambda: (_ for _ in ()).throw(RuntimeError("foreground unknown")))
        result = run({"python": task}, emit=lambda event: events.append(event))
        self.assertEqual(task.calls, 1)
        self.assertEqual(result.completed, 0)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.interrupted_task, "python")
        self.assertEqual([e["event"] for e in events], ["session_start", "task_start", "task_error", "session_end"])

    def test_task_error_traceback_identifies_real_call_and_chained_cause(self):
        run = self.runner()
        events = []
        def observed_window_process():
            try:
                raise ValueError("underlying process lookup failed")
            except ValueError as exc:
                raise OSError("Could not read observed window process") from exc
        result = run({"python": Task(observed_window_process)}, once=True, emit=events.append)
        failure = next(event for event in events if event["event"] == "task_error")
        trace = failure.get("traceback", "")
        self.assertIn("test_runner.py", trace)
        self.assertIn("observed_window_process", trace)
        self.assertIn("ValueError: underlying process lookup failed", trace)
        self.assertIn("OSError: Could not read observed window process", trace)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.completed, 0)

    def test_keyboard_abort_traceback_identifies_interrupted_task(self):
        run = self.runner()
        events = []
        def interrupted_task():
            raise KeyboardInterrupt("manual stop")
        result = run({"python": Task(interrupted_task)}, once=True, emit=events.append)
        failure = next(event for event in events if event["event"] == "task_aborted")
        self.assertIn("interrupted_task", failure.get("traceback", ""))
        self.assertIn("KeyboardInterrupt: manual stop", failure.get("traceback", ""))
        self.assertEqual(result.exit_code, 130)

    def test_keyboard_and_failsafe_abort_are_explicit_and_not_completed(self):
        run = self.runner()
        class FailSafe(Exception):
            pass
        for error in (KeyboardInterrupt(), FailSafe("corner")):
            with self.subTest(error=type(error).__name__):
                task = Task(lambda: (_ for _ in ()).throw(error))
                result = run({"python": task}, abort_exceptions=(FailSafe,))
                self.assertEqual(result.status, "aborted")
                self.assertEqual(result.exit_code, 130)
                self.assertEqual(result.completed, 0)
                self.assertEqual(task.calls, 1)

    def test_deadline_inside_pause_records_incomplete_operation(self):
        run = self.runner()
        from core.timing import Timing
        clock = Clock()
        timing = Timing(clock=clock, sleep=clock.sleep)
        task = Task(lambda: timing.pause(10))
        result = run({"browser": task}, duration=0.2, timing=timing, clock=clock)
        self.assertEqual(result.status, "duration_elapsed")
        self.assertEqual(result.completed, 0)
        self.assertEqual(result.interrupted_task, "browser")
        self.assertAlmostEqual(result.elapsed, 0.2)
        self.assertLessEqual(max(clock.sleeps), 0.05)

    def test_once_completes_one_task_and_seed_repeats_selection(self):
        run = self.runner()
        selected = []
        for _ in range(2):
            events = []
            tasks = {name: Task(lambda: None) for name in ("browser", "python")}
            result = run(tasks, once=True, rng=random.Random(10), emit=events.append)
            self.assertEqual(result.completed, 1)
            self.assertEqual(result.status, "completed")
            selected.append([event["task"] for event in events if event["event"] == "task_start"])
        self.assertEqual(selected[0], selected[1])

    def test_prepare_failure_does_not_run_or_count_selected_task(self):
        run = self.runner()
        task = Task(lambda: None)
        def prepare():
            raise RuntimeError("prepare failed")
        result = run({"browser": task}, prepare=prepare, once=True)
        self.assertEqual(task.calls, 0)
        self.assertEqual(result.completed, 0)
        self.assertEqual(result.status, "error")

    def test_once_reports_elapsed_budget_when_blocking_task_returns_late(self):
        run = self.runner()
        clock = Clock()
        events = []
        task = Task(lambda: clock.sleep(2))
        result = run({"python": task}, duration=1, once=True, clock=clock, emit=events.append)
        self.assertEqual(result.status, "duration_elapsed")
        self.assertEqual(result.completed, 1)
        self.assertIsNone(result.interrupted_task)
        self.assertEqual(result.elapsed, 2)
        self.assertEqual([e["event"] for e in events], ["session_start", "task_start", "task_complete", "session_end"])

    def test_task_complete_retains_verified_structured_result(self):
        run = self.runner()
        outcome = {"status": "execution_verified", "script_path": r"C:\Desktop\helloworld.py", "powershell_handle": 123}
        events = []
        result = run({"python": Task(lambda: outcome)}, once=True, emit=events.append)
        self.assertEqual(result.completed, 1)
        completion = next(event for event in events if event["event"] == "task_complete")
        self.assertEqual(completion.get("result"), outcome)
        self.assertEqual(json.loads(json.dumps(completion))["result"], outcome)

    def test_task_none_result_is_json_null(self):
        run = self.runner()
        events = []
        run({"browser": Task(lambda: None)}, once=True, emit=events.append)
        completion = next(event for event in events if event["event"] == "task_complete")
        self.assertIn("result", completion)
        self.assertIsNone(completion["result"])

    def test_unsupported_task_results_fail_without_implicit_serialization(self):
        run = self.runner()
        for outcome in (object(), {"status": object()}, {"number": float("nan")}, {1: "value"}):
            with self.subTest(outcome=type(outcome).__name__):
                events = []
                result = run({"python": Task(lambda: outcome)}, once=True, emit=events.append)
                self.assertEqual(result.status, "error")
                self.assertIn("TypeError", result.error)
                self.assertFalse(any(event["event"] == "task_complete" for event in events))
                json.dumps(events, allow_nan=False)

    def test_invalid_duration_is_rejected_before_task(self):
        run = self.runner()
        for duration in (0, -1, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                run({"browser": Task(lambda: self.fail("task must not run"))}, duration=duration)


class CliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-S", str(ROOT / "main.py"), *args], capture_output=True, text=True, timeout=5)

    def test_help_works_without_site_packages_or_desktop(self):
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--duration", result.stdout)
        self.assertIn("--once", result.stdout)

    def test_invalid_arguments_fail_before_desktop_import(self):
        for args in (("--duration", "nan"), ("--duration", "0"), ("--countdown", "-1"), ("--countdown", "0.5"), ("--tasks", "unknown")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_startup_failure_is_logged_and_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.cli("--once", "--countdown", "0", "--log-dir", directory)
            self.assertEqual(result.returncode, 1)
            paths = list(Path(directory).glob("*.jsonl"))
            self.assertEqual(len(paths), 1)
            events = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[-1]["event"], "session_end")
            self.assertEqual(events[-1]["status"], "error")
            self.assertEqual(events[-1]["completed"], 0)

            failure = next(event for event in events if event["event"] == "startup_error")
            self.assertIn("main.py", failure.get("traceback", ""))
            self.assertIn("create_desktop_tasks", failure.get("traceback", ""))
            self.assertIn("ModuleNotFoundError", failure.get("traceback", ""))

    def test_startup_traceback_preserves_real_failure_location(self):
        import main
        def startup_process_failure(*args):
            raise OSError("Could not read observed window process")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, "create_desktop_tasks", startup_process_failure):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    code = main.main(["--once", "--countdown", "0", "--log-dir", directory])
            events = [json.loads(line) for line in next(Path(directory).glob("*.jsonl")).read_text(encoding="utf-8").splitlines()]
        failure = next(event for event in events if event["event"] == "startup_error")
        self.assertIn("test_runner.py", failure.get("traceback", ""))
        self.assertIn("startup_process_failure", failure.get("traceback", ""))
        self.assertIn("OSError: Could not read observed window process", failure.get("traceback", ""))
        self.assertEqual(code, 1)

    def test_failsafe_during_startup_is_an_abort(self):
        import main
        class FailSafe(Exception):
            pass
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(sys.modules, {"pyautogui": types.SimpleNamespace(FailSafeException=FailSafe)}):
                with patch.object(main, "create_desktop_tasks", side_effect=FailSafe("corner")):
                    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                        code = main.main(["--once", "--countdown", "0", "--log-dir", directory])
            self.assertEqual(code, 130)
            events = [json.loads(line) for line in next(Path(directory).glob("*.jsonl")).read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[-1]["status"], "aborted")
            self.assertEqual(events[-1]["completed"], 0)


if __name__ == "__main__":
    unittest.main()
