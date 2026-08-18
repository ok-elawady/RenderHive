"""Qt compatibility for Houdini 19.5+ across Qt 5 and Qt 6 builds.

Every RenderHive UI module must import Qt from this file. The module prefers
SideFX's hutil.Qt wrapper, then falls back to the binding bundled with the
running Houdini build. No external Qt package is installed or bundled.
"""

from __future__ import absolute_import

QT_BINDING = ""
wrapInstance = None
isValid = None

try:
    from hutil.Qt import QtCore, QtGui, QtWidgets
    module_name = str(getattr(QtCore, "__name__", ""))
    QT_BINDING = "PySide6" if "PySide6" in module_name else "PySide2"
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        QT_BINDING = "PySide6"
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets
        QT_BINDING = "PySide2"

try:
    if QT_BINDING == "PySide6":
        from shiboken6 import wrapInstance, isValid
    else:
        from shiboken2 import wrapInstance, isValid
except ImportError:
    wrapInstance = None
    isValid = None


def _enum(owner, nested_name, member_name):
    nested = getattr(owner, nested_name, None)
    if nested is not None and hasattr(nested, member_name):
        return getattr(nested, member_name)
    return getattr(owner, member_name)


WINDOW = _enum(QtCore.Qt, "WindowType", "Window")
ALIGN_RIGHT = _enum(QtCore.Qt, "AlignmentFlag", "AlignRight")
ALIGN_CENTER = _enum(QtCore.Qt, "AlignmentFlag", "AlignCenter")
ALIGN_HCENTER = _enum(QtCore.Qt, "AlignmentFlag", "AlignHCenter")
ALIGN_VCENTER = _enum(QtCore.Qt, "AlignmentFlag", "AlignVCenter")
TEXT_SELECTABLE_BY_MOUSE = _enum(
    QtCore.Qt, "TextInteractionFlag", "TextSelectableByMouse"
)
HEADER_STRETCH = _enum(QtWidgets.QHeaderView, "ResizeMode", "Stretch")
HEADER_RESIZE_TO_CONTENTS = _enum(
    QtWidgets.QHeaderView, "ResizeMode", "ResizeToContents"
)
EXTENDED_SELECTION = _enum(
    QtWidgets.QAbstractItemView, "SelectionMode", "ExtendedSelection"
)
USER_ROLE = _enum(QtCore.Qt, "ItemDataRole", "UserRole")
CHECKED = _enum(QtCore.Qt, "CheckState", "Checked")
UNCHECKED = _enum(QtCore.Qt, "CheckState", "Unchecked")
ITEM_IS_ENABLED = _enum(QtCore.Qt, "ItemFlag", "ItemIsEnabled")
ITEM_IS_SELECTABLE = _enum(QtCore.Qt, "ItemFlag", "ItemIsSelectable")
ITEM_IS_USER_CHECKABLE = _enum(QtCore.Qt, "ItemFlag", "ItemIsUserCheckable")
SINGLE_SELECTION = _enum(
    QtWidgets.QAbstractItemView, "SelectionMode", "SingleSelection"
)
NO_SELECTION = _enum(
    QtWidgets.QAbstractItemView, "SelectionMode", "NoSelection"
)
NO_ITEM_FLAGS = _enum(QtCore.Qt, "ItemFlag", "NoItemFlags")
DIALOG_CLOSE = _enum(QtWidgets.QDialogButtonBox, "StandardButton", "Close")
DIALOG_OK = _enum(QtWidgets.QDialogButtonBox, "StandardButton", "Ok")
DIALOG_CANCEL = _enum(QtWidgets.QDialogButtonBox, "StandardButton", "Cancel")
MESSAGE_YES = _enum(QtWidgets.QMessageBox, "StandardButton", "Yes")

Signal = getattr(QtCore, "Signal", None)
Slot = getattr(QtCore, "Slot", None)
Property = getattr(QtCore, "Property", None)


def binding_name():
    return QT_BINDING


def qt_major_version():
    try:
        return int(str(QtCore.qVersion()).split(".", 1)[0])
    except Exception:
        return 6 if QT_BINDING == "PySide6" else 5


def dialog_exec(dialog):
    method = getattr(dialog, "exec", None)
    if callable(method):
        return method()
    return dialog.exec_()


def application_exec(application):
    method = getattr(application, "exec", None)
    if callable(method):
        return method()
    return application.exec_()


def set_window_flag(widget, flag, enabled=True):
    method = getattr(widget, "setWindowFlag", None)
    if callable(method):
        method(flag, bool(enabled))
        return
    flags = widget.windowFlags()
    widget.setWindowFlags(flags | flag if enabled else flags & ~flag)


def object_is_valid(obj):
    if obj is None:
        return False
    if callable(isValid):
        try:
            return bool(isValid(obj))
        except Exception:
            return False
    try:
        obj.objectName()
        return True
    except RuntimeError:
        return False
