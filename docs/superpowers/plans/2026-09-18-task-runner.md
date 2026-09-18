# Shared task runner implementation plan

Goal: inspect current UI before running any task, prepare once if necessary,
and stop if the required UI never becomes ready.

Design approved in chat: UI.get_current supplies foreground window state;
TaskRunner coordinates is_ready(current), prepare(), and run(). Each task
owns its application-specific requirements. Later user amendment: before
preparing a mismatched task, click each foreground window's Minimize button
and re-detect until the desktop is reached. Do not minimize after completion.

1. Add unittest coverage for ready, preparation, timeout, and preparation failure.
2. Implement core/task_runner.py with a bounded readiness wait.
3. Add shared foreground inspection, window activation and element lookup to UI.
4. Give BrowserTask is_ready/prepare methods and use TaskRunner in main.py.
5. Run tests, compilation and diff checks; document extension and live-test limits.

Keep current mouse behaviour and unfinished text typing unchanged. Browser
selectors must use the Edge title and search-box ID already inspected live.
