# synthetic-human-agent-e9

NTU X ST Engineering Hackathon 2026. Windows UI automation through visible
mouse movement, clicks and keyboard input.

## Setup and run

Activate the project's Python environment, then run from this directory:

```powershell
python -m pip install -r requirements.txt
python main.py --profile profiles/windows_edge.json
```

The supplied profile is an **English Windows/Edge development example**.
Its taskbar/search-page selectors were observed on the development PC.
It is not a verified profile for the competition VM. Desktop shortcut and
Windows Search route selectors are unset until inspected on the target PC.
An unavailable or ambiguous configured control stops the task.

## Responsibilities

| File | Responsibility |
|---|---|
| `core/ui.py` | Read current windows/controls/coordinates; physical mouse and keyboard primitives |
| `core/timing.py` | Character/action delays |
| `core/session_state.py` | In-memory window identities, checked against fresh observations |
| `core/task_runner.py` | Check prerequisites, prepare, verify readiness, execute |
| `tasks/return_to_desktop.py` | Click each foreground window's Minimize button until the desktop is detected |
| `tasks/open_application.py` | Open/reuse an application through configured desktop, taskbar or search controls |
| `tasks/browser.py` | Reuse/open the required browser tab, click the search field and type |
| `profiles/windows_edge.json` | Environment-specific application and control selectors |
| `tools/inspect_ui.py` | Read-only target-PC window/control inspection |

The old `core/process.py` direct launcher has been removed. Runtime actions
never use `os.startfile()`, direct window restoration, `set_focus()`, or UIA
Invoke to bypass mouse/keyboard input. UI Automation and Win32 are used
for observation.

## Execution

If the requested task is already ready, the runner executes it immediately.
Otherwise, for a task requiring the desktop:

1. Run `ReturnToDesktopTask` directly as a prerequisite.
2. Observe the foreground window, locate its configured Minimize button,
   move in a straight line and left-click it.
3. Confirm minimization, then inspect the newly exposed window. Repeat
   until the Windows shell desktop is identified.
   If focus lands on the shell taskbar instead, check remaining visible,
   unminimized task windows. Minimize those via their actual buttons; do
   not look for a Minimize button on the taskbar itself. Hidden/cloaked
   windows and shell/tool helpers do not block desktop detection.
   A zero-area foreground helper is handled the same way: it is not a
   window to minimize. The task observes remaining applications and only
   proceeds when none remain and the Windows desktop exists.
4. Run the task's preparation and wait for its required interface.
5. Execute only after readiness is verified.

There is no return-to-desktop step after completion. Missing buttons,
unknown foreground state, focus changes, unsuccessful clicks, or more than
30 windows stop preparation. `TaskRunner` handles business tasks with
`is_ready(current)`, `prepare()` and `run()`. The desktop and application
helpers expose `run()` for direct use during preparation; do not pass them
to `TaskRunner`. Each preparation step executes once.

Application-opening order:

- A remembered, still-valid window: taskbar first, then desktop if no
  configured taskbar control is found.
- No valid remembered window: desktop shortcut first, then taskbar.
- If neither control exists: use the configured Windows Search route.

Desktop shortcuts are double-clicked; taskbar icons are single-clicked.
Once a launcher is clicked, the task waits for the expected foreground
window. It does not try another launcher after an unverified click, which
could open duplicate instances. Grouped taskbar previews are not currently
selected automatically: if clicking the icon cannot restore the expected
window, the task stops and reports the mismatch.

## Configure the target PC

On the actual deployment computer, run:

```powershell
python tools/inspect_ui.py --delay 5
```

During the delay, manually show the interface to inspect (desktop, search
panel, browser, or application). The command prints window metadata and
UI Automation controls without clicking, typing, or activating windows.
Repeat after manually entering an application name into Windows Search
to inspect its results. To inspect an already reported window explicitly:

```powershell
python tools/inspect_ui.py --handle 12345 --delay 0
```

`12345` is only an example; use the handle from your own inspection output.
Handles are transient and should not be put in the reusable profile.

Copy the example profile and fill selectors from that machine's output:

- Observation `name` maps to selector `title`.
- Observation `auto_id` maps to selector `auto_id`.
- Observation `control_type` maps to selector `control_type`.
- Window `class_name` or `title` can scope a top-level window selector.
- Prefer stable inspected IDs; do not save screen coordinates.

`application.desktop_selector` identifies the desktop shortcut, and
`application.taskbar_selector` identifies the taskbar button. `null` means
that route has no inspected selector and is skipped. The optional
`application.search` object has these fields:

| Field | Value from target inspection |
|---|---|
| `entry_window` | Selector for the window containing the search entry |
| `entry` | Selector for the visible search entry button/input |
| `panel` | Top-level window selector for the opened search panel |
| `input` | Selector for its editable search input |
| `query` | Application name to type |
| `result` | Selector for the exact application result to click |

The search task clicks the entry, waits for the panel/input, types the query,
waits for the configured result, clicks it, and checks the resulting app.
No guessed selectors or hidden application-launch fallback are supplied.
Use an English keyboard input mode for the current ASCII typing implementation.

The Windows shell desktop detection uses the shell process and inspected
`Progman`/`WorkerW` desktop-host structure. Custom shells and inaccessible
UIA controls are not verified. Different languages/title bars may require a
different `minimize_selector`. Validate the profile on the target machine.

## Session memory and browser tabs

One `SessionState` instance is shared by tasks in the same Python run. It
remembers window handles, process IDs, classes and last observed titles;
lookups compare those identities with current windows and invalidate stale
records. It never caches click coordinates or persists browsing history.
Page records are not cached. The browser task inspects the configured
matching tab before reusing it; otherwise it opens a new tab using Ctrl+T.
Multiple matching tabs require a more specific selector.

To keep memory across several tasks, reuse `ui`, `session` and `runner`
inside the same process rather than restarting `main.py` for every task.
A future document task implements `is_ready(current)`, `prepare()` and
`run()`, and can use the same opening task with its own inspected profile.
No document-writing task is included yet.

## Mouse and keyboard

```python
ui.move_and_click(x, y, button="left")
ui.move_and_click(x, y, button="right")
ui.move_and_click(x, y, button="left", clicks=2)
ui.move_and_click(x, y, button=None, scroll=-3)
ui.type_text("NTU Hackathon")
```

Coordinates come from `ui.get_coords(element)` after
`ui.find_element(window_handle, **selector)`. `UI` no longer knows the
application-specific name `search_box`.

Movement takes 0.5 seconds. Positive wheel steps scroll up; negative steps
scroll down. Typing preserves the per-character delay and does not press
Enter. This implementation supports ASCII input, not Unicode text. Keep
the target input focused during typing. Browser/search tasks bind keyboard
input to the expected foreground window; changing windows stops input.

## Validation

```powershell
python -m unittest discover -s tests -v
python -m compileall -q core tasks tools main.py
```

Automated tests use fake observations/actions to test decisions and state
transitions. Passing them does not verify clicks on the deployment desktop.
