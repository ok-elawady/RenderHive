# RenderHive Maya v1.9.11 — UI Lifecycle Stability

## Root causes corrected

- Qt UI modules were reloaded every time the window opened. Existing PySide widgets, timers and signals could still reference the old Python classes.
- The window could be deleted while API QThreads were still running, especially during automatic backend connection or pool refresh.
- `WA_DeleteOnClose` was combined with explicit `deleteLater()`, creating a double-deletion risk.
- Zero-delay callbacks could run after the window had begun closing.
- Maya menu commands reloaded the submitter module on every click.

## Fixes

- Production modules are imported once per Maya session.
- Reopening RenderHive focuses the existing window instead of destroying and rebuilding it.
- Running API threads are detached safely and allowed to finish without calling a deleted UI.
- Timers are owned by the window and stopped during close.
- Background callbacks check the closing state.
- Menu and startup commands no longer use `importlib.reload`.
- The Maya top menu remains installed through the existing startup hook.
