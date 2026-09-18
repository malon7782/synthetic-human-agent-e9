# UI and task separation

User-approved design: keep observation, mouse and keyboard in UI; move
desktop return and visible application opening into tasks; share session
state across tasks; configure environment-specific selectors separately.

Implementation ownership:
- Primary: UI primitives, browser integration, main, profiles, inspection tool,
  README and browser tests.
- Session worker: window/page hint cache and its tests.
- Desktop worker: standalone desktop task, runner and their tests.
- Launcher worker: desktop/taskbar/search workflow and its tests.
- Reviewer: read-only cross-module correctness review.

Deployment constraint clarified by user: the competition computer is not
the development PC. Do not invent missing desktop/search selectors. The
example profile labels its observed environment; inspect_ui.py provides
read-only evidence for target-specific configuration.

Validation: fake-UI state-transition tests, import/CLI startup, compilation,
dependency and diff checks. No claim of deployment-PC end-to-end validation.
