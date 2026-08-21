# RenderHive Worker 1.2.2 - System Tray Import Fix

## Symptom

The packaged worker exited at startup with:

```text
NameError: name 'QSystemTrayIcon' is not defined
```

## Cause

The professional UI instantiated `QSystemTrayIcon`, but the symbol was omitted from the `PySide6.QtWidgets` import list. Python compilation does not catch missing runtime names, so the earlier package could build successfully and still fail when the main window was created.

## Fix

- Import `QSystemTrayIcon` from `PySide6.QtWidgets`.
- Add a static AST regression test that verifies the symbol remains imported.
- Bump the worker version to 1.2.2.

No worker scheduling, Maya/Houdini adapter, backend, or task execution logic changed in this hotfix.
