# Synthetic Human Agent

A Windows desktop automation program that runs two predefined workflows through visible mouse and keyboard actions:

- `browser`: open Microsoft Edge from its desktop shortcut, create a separate window, visit Samsung, Apple and Dell, scroll, and close that new window.
- `python`: create a desktop text document, enter `print("Hello, world!")`, save and rename it to a Python script, then run it in PowerShell using the same Python interpreter as the agent. Completion requires accessible console output containing `Hello, world!` and `SHA_EXIT_CODE=0`.

## Requirements

- An unlocked, interactive Windows desktop. Run in the intended user session with permission to control its applications, access the clipboard, and write desktop files and local logs. Applications must permit UI Automation and simulated input; blocked or elevated windows can prevent interaction.
- Python **3.13.5** and a writable project directory. Dependency installation was verified with this interpreter; other versions have not been validated.
- English Windows context-menu labels and an installed English keyboard layout. Enable desktop icons and **file name extensions**. The Python workflow expects **New > Text Document**, **Rename**, and **Copy as path**.
- A text editor that opens the new file in a **new window**, exposes its exact filename through an accessible document/edit control or selected tab, and exposes exactly one empty text buffer through UI Automation. Only the verified new blank document receives text. Reusing an existing editor window is unsupported. Save the file as UTF-8; its actual path and saved content are checked before execution.
- Microsoft Edge with a desktop shortcut named exactly **Microsoft Edge**. Finish browser first-run prompts beforehand. The browser workflow requires HTTPS access to `www.samsung.com`, `www.apple.com`, and `www.dell.com`; proxy, certificate, sign-in, consent, or connectivity problems can stop it.
- Windows PowerShell available through **Win+R > powershell**, with console text exposed to Windows UI Automation. The Python workflow itself does not require Internet access.

Live verification of the current workflows and target VM is pending. The Python workflow's editor behavior, guarded English Explorer extension-confirmation dialog, and accessible PowerShell output still need live validation. A different dialog, reused editor/console window, or inaccessible control causes a bounded failure.

Local evidence on 2026-10-16: dependencies installed into a fresh environment using Python 3.13.5. One earlier browser-only live smoke recorded one completed task in **45.96 seconds**, before stricter browser-readiness changes. It does not validate the current code. No HelloWorld, full 900-second session, or target-VM run has been verified.

## Install

Open PowerShell in this project directory, with `python` pointing to the installed interpreter. Create an isolated environment; activation is unnecessary:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe .\main.py --help
```

For a VM without Internet access, prepare dependencies on an Internet-connected Windows machine with the same Python version and architecture:

```powershell
python -m pip download --dest .\wheelhouse -r .\requirements.txt
```

Transfer the project and the complete `wheelhouse` directory to the VM, create its `.venv` there, and install locally:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r .\requirements.txt
```

Do not copy an existing virtual environment between machines. Complete dependency installation before starting desktop automation.

## Run

Save your work first and leave the desktop available. The agent takes control after the countdown; avoid competing mouse or keyboard input while it runs.

First, try one Python workflow with a two-minute activity budget:

```powershell
.\.venv\Scripts\python.exe .\main.py --tasks python --once --duration 120 --seed 7
```

Then try the browser workflow when its network prerequisites are ready:

```powershell
.\.venv\Scripts\python.exe .\main.py --tasks browser --once --duration 180 --seed 7
```

A successful single-workflow smoke run reports `Status: completed; completed tasks: 1`. Inspect the visible result as well as the log. `duration_elapsed` with zero completed tasks means the workflow did not finish within the budget.

Start the default **900-second activity session**, choosing repeatedly between both workflows:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

All available options are shown here:

```powershell
.\.venv\Scripts\python.exe .\main.py --duration 900 --tasks browser python --seed 7 --countdown 5 --log-dir "$env:LOCALAPPDATA\SyntheticHumanAgent\logs"
```

`--duration` must be positive finite seconds; `--countdown` must be a non-negative integer and defaults to 5 seconds. Countdown and initial dependency setup are outside the activity budget. `--once` stops after one task returns successfully, subject to the same duration limit. `--seed` repeats random choices when the control flow is unchanged; desktop timing and state can still vary.

The deadline is cooperative: a blocking third-party call can extend wall-clock time beyond the activity budget. The first workflow error stops the session; there are no automatic retries. Browser activity consists of direct URL navigation and scrolling; hyperlink clicks are not implemented. Readiness checks use accessible matching document information and limited English warning text; they do not guarantee that every page error or localized warning is detected.

## Stop and inspect results

Move the pointer to a screen corner to trigger PyAutoGUI's fail-safe on its next checked action. Alternatively, return to the launching PowerShell window and press **Ctrl+C**. Keep the fail-safe enabled. A blocking call can delay either stop mechanism. After stopping, inspect any open editor, console, browser window, or partial file before rerunning. Interrupting PyAutoGUI during a shortcut can leave a modifier key held; release any affected Ctrl, Alt, Shift, or Windows key before resuming normal input.

The program prints its diagnostic log path at startup. By default, each run creates a unique `run-*.jsonl` file under `%LOCALAPPDATA%\SyntheticHumanAgent\logs`. `--log-dir` must be outside the source tree. Records include UTC timestamps, selected tasks, task starts/completions/interruption/errors, and final session status and elapsed time.

| Status | Meaning | Exit code |
| --- | --- | --- |
| `completed` | A task returned successfully and `--once` ended the session. | 0 |
| `duration_elapsed` | The activity budget ended; an active task may be incomplete. | 0 |
| `aborted` | Ctrl+C or the PyAutoGUI fail-safe stopped execution. | 130 |
| `error` | Startup or a workflow raised an error. | 1 |

Invalid CLI arguments exit with code 2. A task counts as completed only after its `run()` returns. Check `interrupted_task` and the completed count, rather than treating exit code 0 as proof that every workflow finished. Logs are local diagnostics, not independent proof of desktop task success.

## Files and reruns

The Python workflow preserves existing desktop scripts by selecting `helloworld.py`, then `helloworld_2.py`, `helloworld_3.py`, and so on, avoiding observed names case-insensitively. It leaves the generated script and execution console for inspection. Interrupted runs can also leave a text document or editor open. Remove only artifacts you have identified as belonging to your run; keep original desktop files.

The browser workflow closes the new window it created after normal completion or an ordinary error when cleanup succeeds. Cancellation or deadline expiry intentionally leaves that window open to avoid further input. The window opened or reused by the desktop shortcut can also remain. Review remaining windows and partially created files, restore the prerequisites, then rerun the same command. Each run receives a new log file.

## Local checks without desktop input

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On 2026-10-16, all 50 tests passed in the fresh project environment; dependency and source-compilation checks also passed. The tests use isolated input/window substitutes. Passing them does not establish live focus, editor behavior, network access, or target-VM compatibility.
