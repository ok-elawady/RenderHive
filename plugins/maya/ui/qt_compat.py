from __future__ import absolute_import

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance, isValid
    PYSIDE6 = True
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance, isValid
    PYSIDE6 = False

# Re-export exactly what is needed
__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "wrapInstance",
    "isValid",
    "PYSIDE6",
]
