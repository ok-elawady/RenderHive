"""Application composition root for the Houdini submitter bootstrap."""

from __future__ import absolute_import

from renderhive_houdini.core.constants import WINDOW_SESSION_KEY


def _existing_window():
    import hou
    return getattr(hou.session, WINDOW_SESSION_KEY, None)


def _store_window(window):
    import hou
    setattr(hou.session, WINDOW_SESSION_KEY, window)


def show_window():
    """Create or focus one persistent floating RenderHive window."""
    import sys
    import importlib
    from renderhive_houdini.bootstrap import install_runtime_hooks
    from renderhive_houdini.core.houdini_compat import has_ui, main_window
    from renderhive_houdini.ui.qt_compat import object_is_valid

    if not has_ui():
        raise RuntimeError("RenderHive UI requires an interactive Houdini session.")

    install_runtime_hooks()
    window = _existing_window()

    if not object_is_valid(window):
        window = None
        _store_window(None)

    if window is None:
        for mod_name in list(sys.modules):
            if (
                mod_name == "renderhive_houdini"
                or mod_name.startswith("renderhive_houdini.")
            ):
                del sys.modules[mod_name]
        importlib.invalidate_caches()
        from renderhive_houdini.ui.main_window import MainWindow
        window = MainWindow(parent=main_window(), embedded=False)
        _store_window(window)
    else:
        from renderhive_houdini.ui.main_window import MainWindow

    try:
        window.refresh_context()
        window.show()
        window.raise_()
        window.activateWindow()
    except RuntimeError:
        window = MainWindow(parent=main_window(), embedded=False)
        _store_window(window)
        window.show()

    return window
