# RenderHive Houdini Qt Compatibility v0.1.3

## Fix

Houdini 20.5 uses PySide2. The previous bootstrap imported PySide6 directly,
which caused `ModuleNotFoundError: No module named PySide6`.

All UI modules now import Qt through `renderhive_houdini.ui.qt_compat`:

- PySide6 is used when available.
- PySide2 is used automatically on Houdini 20.5.
- The active binding is visible on the Tools page.

The installer also disables duplicate RenderHive package JSON files and verifies
that each Houdini preference folder points to the v0.1.3 runtime payload.

Close Houdini completely before installing and reopening the plugin.
