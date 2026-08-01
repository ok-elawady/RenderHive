# RenderHive Houdini Multi-Version Bootstrap v0.1.4

## Compatibility strategy

- One pure-Python codebase for Houdini 19.5 and newer.
- SideFX `hutil.Qt` is preferred, with PySide6 and PySide2 fallbacks.
- Qt 5 and Qt 6 enum differences are normalized in `ui/qt_compat.py`.
- The package is stored in `payload/python_libs`, not a Python-minor-specific folder.
- The Houdini package prepends `python_libs` to `PYTHONPATH`.
- The installer registers every detected `Documents/houdiniX.Y` directory.
- Menu, shelf and Python Panel continue to load through `HOUDINI_PATH`.
- No compiled Python, Qt, or Shiboken binaries are distributed.

## Official support target

- Houdini 19.5+
- Windows
- Qt 5 / PySide2 builds
- Qt 6 / PySide6 builds
- Python 3.9+
