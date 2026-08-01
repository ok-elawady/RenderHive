"""Feature-based compatibility helpers for Houdini 19.5 and newer."""

from __future__ import absolute_import


def application_version():
    import hou
    try:
        values = tuple(int(value) for value in hou.applicationVersion())
    except Exception:
        values = ()
    return values


def application_version_string():
    import hou
    try:
        return str(hou.applicationVersionString())
    except Exception:
        values = application_version()
        return ".".join(str(value) for value in values) if values else "Unknown"


def python_version_string():
    import sys
    return "{}.{}.{}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2])


def main_window():
    """Return Houdini's main Qt window using the API available in this build."""
    import hou

    qt_namespace = getattr(hou, "qt", None)
    getter = getattr(qt_namespace, "mainWindow", None) if qt_namespace else None
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass

    ui_namespace = getattr(hou, "ui", None)
    getter = getattr(ui_namespace, "mainQtWindow", None) if ui_namespace else None
    if callable(getter):
        try:
            return getter()
        except Exception:
            pass

    return None


def has_ui():
    import hou
    checker = getattr(hou, "isUIAvailable", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            pass
    return main_window() is not None


def user_pref_dir():
    import hou
    try:
        return str(hou.getenv("HOUDINI_USER_PREF_DIR") or "")
    except Exception:
        return ""
