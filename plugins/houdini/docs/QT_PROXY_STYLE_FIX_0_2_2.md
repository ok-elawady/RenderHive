# RenderHive Houdini v0.2.2 - Qt Proxy Style Lifetime Fix

## Cause

Houdini 20.5 uses PySide2 and wraps stylesheet-aware widgets with an internal
`QProxyStyle`. The previous status widget manually called `unpolish()` and
`polish()` on `widget.style()`. Houdini can replace that internal wrapper, so
the Python reference may point to an already-deleted C++ object.

## Fix

- Removed every manual `style().unpolish()` / `style().polish()` call.
- Status color and weight now update through `QPalette` and `QFont`.
- The implementation supports both PySide2 and PySide6.
- Render-node scanning remains manual and does not run during window startup.

## Regression protection

The package test suite now fails if unsafe manual QStyle repolishing is
reintroduced.
