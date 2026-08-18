"""Reusable Qt widgets shared by all Houdini submitter pages."""

from __future__ import absolute_import

from renderhive_houdini.ui.qt_compat import (
    QtCore,
    QtGui,
    QtWidgets,
    TEXT_SELECTABLE_BY_MOUSE,
    ALIGN_CENTER,
    Signal,
)
from renderhive_houdini.ui.theme import COLORS


class InfoButton(QtWidgets.QToolButton):
    def __init__(self, tooltip, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoTipButton")
        self.setText("i")
        self.setToolTip(str(tooltip or ""))
        self.setAutoRaise(True)
        self.setFixedSize(18, 18)


class PageHeader(QtWidgets.QWidget):
    def __init__(self, title, tooltip="", parent=None):
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(2, 0, 2, 2)
        row.setSpacing(7)
        label = QtWidgets.QLabel(str(title))
        label.setObjectName("PageTitle")
        row.addWidget(label)
        if tooltip:
            row.addWidget(InfoButton(tooltip))
        row.addStretch()


class SectionCard(QtWidgets.QFrame):
    def __init__(self, title, tooltip="", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(12, 11, 12, 12)
        self.layout.setSpacing(9)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        heading = QtWidgets.QLabel(str(title))
        heading.setObjectName("SectionTitle")
        header.addWidget(heading)
        if tooltip:
            header.addWidget(InfoButton(tooltip))
        header.addStretch()
        self.layout.addLayout(header)


class FieldLabel(QtWidgets.QWidget):
    def __init__(self, text, tooltip="", parent=None):
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(5)
        label = QtWidgets.QLabel(str(text))
        label.setObjectName("FieldLabel")
        row.addWidget(label)
        if tooltip:
            row.addWidget(InfoButton(tooltip))
        row.addStretch()


class LabeledField(QtWidgets.QWidget):
    def __init__(self, label, widget, tooltip="", parent=None):
        super().__init__(parent)
        self.widget = widget
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        root.addWidget(FieldLabel(label, tooltip))
        root.addWidget(widget)


class ReadOnlyRow(QtWidgets.QWidget):
    def __init__(self, label, value="—", tooltip="", parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        root.addWidget(FieldLabel(label, tooltip))
        self.value_label = QtWidgets.QLabel(str(value))
        self.value_label.setObjectName("ReadOnlyValue")
        self.value_label.setTextInteractionFlags(TEXT_SELECTABLE_BY_MOUSE)
        self.value_label.setWordWrap(True)
        root.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value if value not in (None, "") else "—"))


def _palette_window_text_role():
    role = getattr(QtGui.QPalette, "WindowText", None)
    if role is not None:
        return role
    return QtGui.QPalette.ColorRole.WindowText


def apply_status_appearance(widget, level="neutral"):
    """Use palette changes only; never repolish Houdini's QProxyStyle."""
    level = str(level or "neutral").lower()
    colors = {
        "good": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
        "info": COLORS["info"],
        "neutral": COLORS["secondary"],
    }
    palette = widget.palette()
    palette.setColor(
        _palette_window_text_role(),
        QtGui.QColor(colors.get(level, COLORS["secondary"])),
    )
    widget.setPalette(palette)
    font = widget.font()
    font.setBold(level in ("good", "warning", "error"))
    widget.setFont(font)
    widget.update()


class InlineStatus(QtWidgets.QLabel):
    def __init__(self, text="", level="neutral", parent=None):
        super().__init__(str(text), parent)
        self.setObjectName("InlineStatus")
        self.setWordWrap(True)
        self.set_level(level)

    def set_level(self, level):
        apply_status_appearance(self, level)


class StatusChip(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(str(text), parent)
        self.setObjectName("MetaChip")
        self.setAlignment(ALIGN_CENTER)


class SegmentedChoice(QtWidgets.QFrame):
    """Compact radio-style segmented selector matching the RenderHive submitter UX."""
    currentTextChanged = Signal(str) if Signal is not None else None

    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setObjectName("SegmentedControl")
        self._buttons = []
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        values = [str(value) for value in labels or []]
        for index, label in enumerate(values):
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("SegmentButton")
            button.setProperty("segment", "first" if index == 0 else "last" if index == len(values) - 1 else "middle")
            self._group.addButton(button, index)
            row.addWidget(button, 1)
            self._buttons.append(button)
            button.clicked.connect(self._emit_changed)
        if self._buttons:
            self._buttons[0].setChecked(True)

    def _emit_changed(self, *args):
        if self.currentTextChanged is not None:
            self.currentTextChanged.emit(self.currentText())

    def currentText(self):
        button = self._group.checkedButton()
        return str(button.text()) if button is not None else ""

    def setCurrentText(self, text):
        target = str(text or "")
        for button in self._buttons:
            if str(button.text()) == target:
                button.setChecked(True)
                self._emit_changed()
                return True
        return False
