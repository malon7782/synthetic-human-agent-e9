# Hello World task

## How the task runs

The current `main.py` run prepares the desktop with `DefaultTask`, then runs
`HelloWorldTask` once. The task expects `DefaultTask` to have brought the
desktop to the foreground.

`HelloWorldTask.run()` performs these steps:

1. Read the current desktop icons and stop with a clear error if
   `helloworld.py` already exists, so the task does not overwrite it.
2. Record the current icon names, then use the desktop context menu's
   **New > Text Document** commands to create a file. The task identifies the
   new file by comparing the desktop icons before and after creation, so other
   existing text documents do not make the selection ambiguous.
3. Open the new document, replace its contents with `print("Hello world!")`,
   save it, and close the editor.
4. Rename the new document to `helloworld.py`. If the rename confirmation
   dialog appears, confirm it, then check that the renamed file is on the
   desktop.
5. Open the file's context menu with Shift + right-click and choose
   **Copy as path**. Open PowerShell, type `python `, paste the copied path,
   pause, and press Enter. PowerShell remains open so the output or any error
   stays visible.

## Calling the UI helpers

`UI.click_window_button(action)` locates a title-bar button on the active
window, then moves to and clicks it. The supported action strings are
`"minimize"`, `"maximize"`, `"restore"`, and `"close"` (the corresponding
Chinese labels are supported too). The Hello World task uses it after saving
the document:

```python
self.ui.click_window_button("close")
```

`UI.click_context_menu_item(name)` finds a visible context-menu item by its
displayed label and clicks it. The caller first opens the relevant menu with
`move_and_click(..., "right")`; the helper selects an item from that menu. In
the Hello World task, the calls are:

```python
self.ui.click_context_menu_item("New")
self.ui.click_context_menu_item("Text Document")
self.ui.click_context_menu_item("Rename")
self.ui.click_context_menu_item("Copy as path")
```

The item name must match the visible menu label, ignoring letter case. For
example, the task opens the desktop context menu before selecting **New**,
then selects **Text Document** from its submenu.
