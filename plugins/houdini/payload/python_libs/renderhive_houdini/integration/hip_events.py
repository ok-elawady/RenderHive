"""HIP-file lifecycle callbacks for refreshing the open RenderHive window."""

_CALLBACK = None
_PENDING = False


def _run_deferred_refresh():
    global _PENDING
    _PENDING = False

    try:
        import hou
        from renderhive_houdini.core.constants import WINDOW_SESSION_KEY
        from renderhive_houdini.ui.qt_compat import object_is_valid
    except Exception:
        return

    window = getattr(hou.session, WINDOW_SESSION_KEY, None)
    if not object_is_valid(window):
        return

    try:
        window.refresh_context(scan_nodes=False)
    except (RuntimeError, AttributeError):
        pass


def _on_hip_event(event_type):
    """Coalesce file callbacks and refresh after Houdini finishes the event."""
    global _PENDING
    if _PENDING:
        return
    _PENDING = True

    try:
        from renderhive_houdini.ui.qt_compat import QtCore
        QtCore.QTimer.singleShot(0, _run_deferred_refresh)
    except Exception:
        _run_deferred_refresh()


def install():
    global _CALLBACK
    if _CALLBACK is not None:
        return

    import hou
    _CALLBACK = _on_hip_event
    hou.hipFile.addEventCallback(_CALLBACK)


def uninstall():
    global _CALLBACK, _PENDING
    if _CALLBACK is None:
        return

    try:
        import hou
        hou.hipFile.removeEventCallback(_CALLBACK)
    except Exception:
        pass
    _CALLBACK = None
    _PENDING = False
