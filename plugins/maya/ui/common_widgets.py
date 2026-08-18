from __future__ import absolute_import

from .qt_compat import QtCore, QtWidgets
from .qt_theme import COLORS


class WorkerStatusChip(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super(WorkerStatusChip, self).__init__(str(text), parent)
        self.setObjectName("WorkerStatusChip")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.set_state(text or "Not Synced", COLORS["muted"])

    def set_state(self, text, color):
        color = str(color or COLORS["muted"])
        self.setText(str(text or "—"))
        self.setStyleSheet(
            "QLabel#WorkerStatusChip {"
            "background-color:%s;"
            "border:1px solid %s;"
            "color:%s;"
            "border-radius:9px;"
            "padding:3px 8px;"
            "font-size:10px;"
            "font-weight:600;"
            "}" % (COLORS["surface2"], color, color)
        )

class SegmentedChoice(QtWidgets.QFrame):
    currentTextChanged = QtCore.Signal(str)

    def __init__(self, options, parent=None):
        super(SegmentedChoice, self).__init__(parent)
        self.setObjectName("SegmentedControl")
        self._options = [str(value) for value in options]
        self._buttons = []
        self._current = self._options[0] if self._options else ""

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)

        for index, option in enumerate(self._options):
            button = QtWidgets.QPushButton(option)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.clicked.connect(
                lambda checked=False, value=option: self.setCurrentText(value)
            )
            self._group.addButton(button, index)
            self._buttons.append(button)
            layout.addWidget(button, 1)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def currentText(self):
        return self._current

    def setCurrentText(self, value):
        value = str(value or "")
        if value not in self._options:
            return False

        changed = value != self._current
        self._current = value

        for option, button in zip(self._options, self._buttons):
            button.blockSignals(True)
            button.setChecked(option == value)
            button.blockSignals(False)

        if changed:
            self.currentTextChanged.emit(value)

        return True

    def findText(self, value):
        try:
            return self._options.index(str(value))
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        try:
            value = self._options[int(index)]
        except Exception:
            return
        self.setCurrentText(value)

    def isEditable(self):
        return False


class InfoTipButton(QtWidgets.QToolButton):
    def __init__(self, tooltip, parent=None):
        super(InfoTipButton, self).__init__(parent)
        self.setObjectName("InfoTipButton")
        self.setText("i")
        self.setToolTip(str(tooltip or ""))
        self.setCursor(QtCore.Qt.WhatsThisCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setFixedSize(18, 18)

class LabeledField(QtWidgets.QWidget):
    def __init__(self, label, widget, tooltip="", parent=None):
        super(LabeledField, self).__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(5)

        title = QtWidgets.QLabel(label)
        title.setObjectName("FieldLabel")
        header.addWidget(title)

        if tooltip:
            header.addWidget(InfoTipButton(tooltip))

        header.addStretch()
        layout.addLayout(header)
        layout.addWidget(widget)

class Card(QtWidgets.QFrame):
    def __init__(self, title, subtitle="", parent=None):
        super(Card, self).__init__(parent)
        self.setObjectName("Card")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 14)
        self.layout.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 1)
        header.setSpacing(7)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("SectionTitle")
        header.addWidget(title_label)

        if subtitle:
            header.addWidget(InfoTipButton(subtitle))

        header.addStretch()
        self.layout.addLayout(header)

class PageHeader(QtWidgets.QWidget):
    def __init__(self, title, subtitle="", parent=None):
        super(PageHeader, self).__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(3, 2, 3, 5)
        layout.setSpacing(7)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)

        if subtitle:
            layout.addWidget(InfoTipButton(subtitle))

        layout.addStretch()
