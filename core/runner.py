"""Bounded task execution without importing any desktop dependency."""
from dataclasses import asdict, dataclass
import math
import random
import time

from core.timing import DeadlineReached


def _recordable_result(value):
    """Accept current task contracts: None or a string-keyed scalar dict."""
    if value is None:
        return None
    if type(value) is not dict:
        raise TypeError("task result must be None or a dict of JSON scalar values")
    for key, item in value.items():
        scalar = item is None or type(item) in (str, bool, int)
        finite_float = type(item) is float and math.isfinite(item)
        if type(key) is not str or not (scalar or finite_float):
            raise TypeError("task result requires string keys and finite JSON scalar values")
    return value.copy()


@dataclass(frozen=True)
class RunResult:
    status: str
    completed: int
    elapsed: float
    interrupted_task: str | None = None
    error: str | None = None

    @property
    def exit_code(self):
        if self.status == "aborted":
            return 130
        return 1 if self.status == "error" else 0


def run_session(tasks, *, duration=900, once=False, prepare=None, timing=None,
                rng=None, clock=time.monotonic, emit=None, abort_exceptions=()):
    """Run until duration/once/error. A task counts only when run() returns.

    The deadline is cooperative: blocking third-party calls cannot be preempted.
    A deadline inside a task leaves interrupted_task set, even on clean expiry.
    """
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and greater than zero")
    if not tasks:
        raise ValueError("at least one task is required")
    rng = rng if rng is not None else random.Random()
    emit = emit if emit is not None else lambda event: None
    started = clock()
    deadline = started + duration
    previous_deadline = timing.deadline if timing is not None else None
    if timing is not None:
        timing.deadline = min(deadline, previous_deadline) if previous_deadline is not None else deadline
    completed = 0
    active = None
    status = "completed"
    error = None

    def event(name, **fields):
        emit({"event": name, "elapsed": max(0.0, clock() - started), **fields})

    def check():
        if timing is not None:
            timing.check()
        if clock() >= deadline:
            raise DeadlineReached("activity duration elapsed")

    event("session_start", duration=duration, once=once, tasks=list(tasks))
    try:
        while True:
            check()
            active = rng.choice(list(tasks))
            event("task_start", task=active)
            if prepare is not None:
                prepare()
            check()
            task_result = _recordable_result(tasks[active].run())
            completed += 1
            event("task_complete", task=active, completed=completed, result=task_result)
            active = None
            check()
            if once:
                break
            if timing is not None:
                timing.pause()
    except DeadlineReached as exc:
        status = "duration_elapsed"
        if active is not None:
            event("task_interrupted", task=active, reason=str(exc))
    except (KeyboardInterrupt, *abort_exceptions) as exc:
        status = "aborted"
        error = f"{type(exc).__name__}: {exc}"
        event("task_aborted" if active is not None else "session_aborted", task=active, error=error)
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
        event("task_error" if active is not None else "session_error", task=active, error=error)
    finally:
        if timing is not None:
            timing.deadline = previous_deadline
    result = RunResult(status, completed, max(0.0, clock() - started), active, error)
    event("session_end", **asdict(result))
    return result
