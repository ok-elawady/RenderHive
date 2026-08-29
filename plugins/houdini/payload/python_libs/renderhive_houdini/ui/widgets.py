"""Reusable Shadcn-styled VFX widgets for the RenderHive Maya Submitter."""

from __future__ import absolute_import, print_function

import os
from renderhive_houdini.ui.qt_compat import QtCore, QtGui, QtWidgets, TEXT_SELECTABLE_BY_MOUSE, ALIGN_CENTER, Signal
from renderhive_houdini.ui.theme import COLORS
from renderhive_houdini.ui.icons import get_icon


class ScrollFilter(QtCore.QObject):
    """Event filter that suppresses mouse wheel events unless the widget has explicit focus.
    
    Prevents scroll hijacking in VFX DCC dialogs with nested scroll views.
    """
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def install(cls, widget):
        if widget is not None:
            widget.installEventFilter(cls.get())
            widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        return widget

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Wheel:
            # Only allow wheel adjustments if the widget is explicitly focused
            if hasattr(obj, "hasFocus") and not obj.hasFocus():
                event.ignore()
                return True
        return super(ScrollFilter, self).eventFilter(obj, event)


class SegmentNavButton(QtWidgets.QPushButton):
    """Pill navigation button matching worker desktop client with active icon sync."""

    def __init__(self, icon_name="", text="", parent=None):
        super(SegmentNavButton, self).__init__("  " + text.strip(), parent)
        self.icon_name = icon_name
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setAccessibleName(text.strip())
        if self.icon_name:
            self._update_icon(self.isChecked())
            self.toggled.connect(self._update_icon)

    def _update_icon(self, checked):
        if not self.icon_name:
            return
        color = "#FFFFFF" if checked else "#94A3B8"
        self.setIcon(get_icon(self.icon_name, color, 14))


class SectionCard(QtWidgets.QFrame):
    """Shadcn Card with header divider, visible title & subtitle description, and clean studio typography."""

    def __init__(self, title="", subtitle="", action_widget=None, parent=None):
        super(SectionCard, self).__init__(parent)
        self.setObjectName("Card")
        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        if title or subtitle:
            header_frame = QtWidgets.QFrame()
            header_frame.setObjectName("CardHeader")
            header = QtWidgets.QHBoxLayout(header_frame)
            header.setContentsMargins(16, 12, 16, 12)
            header.setSpacing(8)
            header.setAlignment(QtCore.Qt.AlignVCenter)

            text_box = QtWidgets.QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(4)

            if title:
                title_label = QtWidgets.QLabel(title)
                title_label.setObjectName("SectionTitle")
                text_box.addWidget(title_label)

            if subtitle:
                subtitle_label = QtWidgets.QLabel(subtitle)
                subtitle_label.setObjectName("CardDescription")
                subtitle_label.setWordWrap(True)
                text_box.addWidget(subtitle_label)

            header.addLayout(text_box, 1)

            if action_widget is not None:
                header.addWidget(action_widget, 0, QtCore.Qt.AlignVCenter)

            self.root.addWidget(header_frame)

        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setObjectName("CardContent")
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 14, 16, 16)
        self.content_layout.setSpacing(10)
        self.root.addWidget(self.content_widget, 1)

    @property
    def layout(self):
        """Backward compatibility for existing pages accessing card.layout."""
        return self.content_layout

    def add_widget(self, widget, stretch=0):
        self.content_layout.addWidget(widget, stretch)

    def add_layout(self, layout, stretch=0):
        self.content_layout.addLayout(layout, stretch)


# Aliases for backwards compatibility
Card = SectionCard
StudioCard = SectionCard


class StatCard(QtWidgets.QFrame):
    """Metric Stat Card following shadcn StatChip aesthetic with bold monospace value."""

    def __init__(self, caption, value="â€”", detail="", icon_name="", color=None, parent=None):
        super(StatCard, self).__init__(parent)
        self.setObjectName("StatCard")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.caption_label = QtWidgets.QLabel(str(caption).upper())
        self.caption_label.setStyleSheet("font-size: 10px; font-weight: 700; color: %s; letter-spacing: 0.5px;" % (color or COLORS["muted"]))
        header.addWidget(self.caption_label)
        header.addStretch()

        if icon_name:
            self.icon_label = QtWidgets.QLabel()
            self.icon_label.setPixmap(get_icon(icon_name, color or COLORS["muted"], 13).pixmap(13, 13))
            header.addWidget(self.icon_label)

        self.value_label = QtWidgets.QLabel(str(value))
        self.value_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF; font-family: 'JetBrains Mono', Consolas, monospace;")
        self.value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.detail_label = QtWidgets.QLabel(str(detail))
        self.detail_label.setObjectName("MutedText")
        self.detail_label.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(self.value_label)
        if detail:
            layout.addWidget(self.detail_label)

        self.setStyleSheet(
            "QFrame#StatCard {"
            "background-color: %s;"
            "border: 1px solid %s;"
            "border-radius: 8px;"
            "}" % (COLORS["surface2"], COLORS["border_card"])
        )

    def set_value(self, value, detail=None):
        self.value_label.setText(str(value if value not in (None, "") else "â€”"))
        if detail is not None:
            self.detail_label.setText(str(detail))
            self.detail_label.setVisible(bool(detail))


class PathBox(QtWidgets.QWidget):
    """File path field with embedded quick-copy and open-in-folder buttons."""

    def __init__(self, placeholder="Select file or directoryâ€¦", file_mode=False, parent=None):
        super(PathBox, self).__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.line_edit = QtWidgets.QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setClearButtonEnabled(True)
        ScrollFilter.install(self.line_edit)

        self.copy_btn = QtWidgets.QPushButton()
        self.copy_btn.setObjectName("GhostBtn")
        self.copy_btn.setIcon(get_icon("copy", COLORS["muted"], 13))
        self.copy_btn.setFixedSize(32, 32)
        self.copy_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.copy_btn.setAccessibleName("Copy path to clipboard")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

        self.browse_btn = QtWidgets.QPushButton("Browseâ€¦")
        self.browse_btn.setObjectName("SecondaryBtn")
        self.browse_btn.setFixedHeight(32)
        self.browse_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.browse_btn.setAccessibleName("Browse for file or directory")

        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self.copy_btn)
        layout.addWidget(self.browse_btn)

    def text(self):
        return self.line_edit.text()

    def setText(self, text):
        self.line_edit.setText(str(text or ""))

    def _copy_to_clipboard(self):
        text = self.line_edit.text().strip()
        if text:
            QtWidgets.QApplication.clipboard().setText(text)


class StepperNumberInput(QtWidgets.QFrame):
    """Modern dark studio numeric input with embedded horizontal decrement/increment buttons.
    
    Provides high-contrast precision numeric adjustment without scroll hijacking.
    """
    valueChanged = QtCore.Signal(object)
    editingFinished = QtCore.Signal()

    def __init__(self, parent=None, minimum=0, maximum=1000000, default=0, step=1, decimals=0, suffix="", special_value_text=""):
        super(StepperNumberInput, self).__init__(parent)
        self.setObjectName("StepperFrame")
        self._decimals = int(decimals)
        self._minimum = float(minimum) if self._decimals > 0 else int(minimum)
        self._maximum = float(maximum) if self._decimals > 0 else int(maximum)
        self._step = (float(step) if self._decimals > 0 else int(step)) if step > 0 else 1
        self._value = float(default) if self._decimals > 0 else int(default)
        self._suffix = str(suffix or "")
        self._special_value_text = str(special_value_text or "")
        self._block_updates = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.dec_button = QtWidgets.QPushButton("-")
        self.dec_button.setObjectName("StepperBtn")
        self.dec_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.dec_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.dec_button.setAutoRepeat(True)
        self.dec_button.setAutoRepeatDelay(400)
        self.dec_button.setAutoRepeatInterval(80)
        self.dec_button.clicked.connect(self.stepDown)

        self.line_edit = QtWidgets.QLineEdit()
        self.line_edit.setObjectName("StepperInput")
        self.line_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.line_edit.editingFinished.connect(self._on_editing_finished)
        ScrollFilter.install(self.line_edit)

        self.inc_button = QtWidgets.QPushButton("+")
        self.inc_button.setObjectName("StepperBtn")
        self.inc_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.inc_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.inc_button.setAutoRepeat(True)
        self.inc_button.setAutoRepeatDelay(400)
        self.inc_button.setAutoRepeatInterval(80)
        self.inc_button.clicked.connect(self.stepUp)

        layout.addWidget(self.dec_button)
        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self.inc_button)

        ScrollFilter.install(self)
        self._update_display()

    def value(self):
        return float(self._value) if self._decimals > 0 else int(self._value)

    def setValue(self, value):
        try:
            val = float(value) if self._decimals > 0 else int(value)
        except (ValueError, TypeError):
            val = self._minimum
        val = max(self._minimum, min(self._maximum, val))
        if val != self._value:
            self._value = val
            self._update_display()
            self.valueChanged.emit(self.value())
        else:
            self._update_display()

    def decimals(self):
        return self._decimals

    def setDecimals(self, decimals):
        self._decimals = int(decimals)
        self.setValue(self._value)

    def minimum(self):
        return self._minimum

    def setMinimum(self, minimum):
        self._minimum = float(minimum) if self._decimals > 0 else int(minimum)
        if self._value < self._minimum:
            self.setValue(self._minimum)
        self._update_display()

    def maximum(self):
        return self._maximum

    def setMaximum(self, maximum):
        self._maximum = float(maximum) if self._decimals > 0 else int(maximum)
        if self._value > self._maximum:
            self.setValue(self._maximum)
        self._update_display()

    def setRange(self, minimum, maximum):
        self._minimum = float(minimum) if self._decimals > 0 else int(minimum)
        self._maximum = float(maximum) if self._decimals > 0 else int(maximum)
        if self._value < self._minimum:
            self.setValue(self._minimum)
        elif self._value > self._maximum:
            self.setValue(self._maximum)
        self._update_display()

    def singleStep(self):
        return self._step

    def setSingleStep(self, step):
        self._step = max(0.001 if self._decimals > 0 else 1, float(step) if self._decimals > 0 else int(step))

    def suffix(self):
        return self._suffix

    def setSuffix(self, suffix):
        self._suffix = str(suffix or "")
        self._update_display()

    def specialValueText(self):
        return self._special_value_text

    def setSpecialValueText(self, text):
        self._special_value_text = str(text or "")
        self._update_display()

    def setPlaceholderText(self, text):
        self.line_edit.setPlaceholderText(str(text or ""))

    def stepUp(self):
        self.setValue(self._value + self._step)

    def stepDown(self):
        self.setValue(self._value - self._step)

    def text(self):
        return self.line_edit.text()

    def isReadOnly(self):
        return self.line_edit.isReadOnly()

    def setReadOnly(self, read_only):
        self.line_edit.setReadOnly(bool(read_only))
        self._update_display()

    def _update_display(self):
        if self._block_updates:
            return
        if self._special_value_text and self._value == self._minimum:
            text = self._special_value_text
        else:
            if self._decimals > 0:
                val_str = "{:.{}f}".format(self._value, self._decimals)
                if val_str.endswith(".000"):
                    val_str = val_str[:-4]
            else:
                val_str = str(int(self._value))
            text = "{}{}".format(val_str, self._suffix)
        self.line_edit.setText(text)
        is_interactive = self.isEnabled() and not self.line_edit.isReadOnly()
        self.dec_button.setEnabled(is_interactive and self._value > self._minimum)
        self.inc_button.setEnabled(is_interactive and self._value < self._maximum)

    def _on_editing_finished(self):
        raw = self.line_edit.text().strip()
        if self._suffix and raw.endswith(self._suffix):
            raw = raw[:-len(self._suffix)].strip()
        if self._special_value_text and raw.lower() == self._special_value_text.lower():
            self.setValue(self._minimum)
            self.editingFinished.emit()
            return
        try:
            val = float(raw) if self._decimals > 0 else int(raw)
            self.setValue(val)
        except Exception:
            self._update_display()
        self.editingFinished.emit()


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
            "background-color: #121622;"
            "border: 1px solid #283145;"
            "color: %s;"
            "border-radius: 12px;"
            "padding: 2px 10px;"
            "font-size: 11px;"
            "font-weight: 600;"
            "min-height: 20px;"
            "max-height: 22px;"
            "}" % color
        )
class StatusChip(QtWidgets.QLabel):
    """Clean text status badge with dynamic colorized icon dot and label matching status."""

    STYLES = {
        "ONLINE": ("#3DDC84", "●"),
        "READY": ("#3DDC84", "●"),
        "SUCCESS": ("#3DDC84", "●"),
        "OK": ("#3DDC84", "●"),
        "PASSED": ("#3DDC84", "●"),
        "RENDERING": ("#C084FC", "●"),
        "PAUSED": ("#FFB84D", "●"),
        "OFFLINE": ("#94A3B8", "○"),
        "ERROR": ("#FF5D73", "●"),
        "WARNING": ("#FFB84D", "●"),
        "CONNECTED": ("#3DDC84", "●"),
        "DISCONNECTED": ("#FF5D73", "●"),
        "VALIDATING": ("#60A5FA", "●"),
        "SUBMITTING": ("#9C73F2", "●"),
    }

    def __init__(self, status="READY", parent=None):
        super(StatusChip, self).__init__(parent)
        self.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.set_status(status)

    def set_status(self, status="READY", custom_text=None):
        normalized = str(status or "READY").upper()
        if normalized in ("SUCCESS", "OK", "PASSED"):
            normalized_label = "Ready"
        elif normalized == "CONNECTED":
            normalized_label = "Ready"
        else:
            normalized_label = normalized.title().replace("_", " ")

        foreground, dot = self.STYLES.get(
            normalized, self.STYLES.get("OFFLINE", ("#A1A7BB", "●"))
        )
        display_text = custom_text if custom_text else "{} {}".format(dot, normalized_label)
        self.setText(display_text)
        self.setAccessibleName("Status: {}".format(display_text))
        self.setStyleSheet(
            "QLabel { color: %s; background-color: transparent; border: none; "
            "font-weight: 600; padding: 0 4px; font-size: 13px; "
            "letter-spacing: 0.2px; font-family: 'Inter', system-ui, sans-serif; }"
            % foreground
        )


class StatusBadge(QtWidgets.QFrame):
    """Pill badge with colored status dot and uppercase label."""

    def __init__(self, text="READY", status="info", parent=None):
        super(StatusBadge, self).__init__(parent)
        self.setObjectName("StatusChip")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 8, 2)
        layout.setSpacing(4)

        self.dot = QtWidgets.QLabel("●")
        self.dot.setObjectName("StatusChipDot")
        self.label = QtWidgets.QLabel(str(text).upper())
        self.label.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")

        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self.set_status(text, status)

    def set_status(self, text, status="info"):
        color_map = {
            "success": COLORS.get("success", "#4ADE80"),
            "online": COLORS.get("success", "#4ADE80"),
            "passed": COLORS.get("success", "#4ADE80"),
            "ready": COLORS.get("success", "#4ADE80"),
            "connected": COLORS.get("success", "#4ADE80"),
            "warning": COLORS.get("warning", "#FBBF24"),
            "busy": COLORS.get("warning", "#FBBF24"),
            "rendering": COLORS.get("warning", "#FBBF24"),
            "error": COLORS.get("error", "#F87171"),
            "offline": COLORS.get("error", "#F87171"),
            "failed": COLORS.get("error", "#F87171"),
            "info": COLORS.get("info", "#4DA3FF"),
            "paused": COLORS.get("paused", "#C084FC"),
            "muted": COLORS.get("muted", "#A1A7BB"),
        }
        color = color_map.get(str(status).lower(), COLORS.get("info", "#4DA3FF"))
        self.label.setText(str(text).upper())
        self.dot.setStyleSheet("color: %s; font-size: 10px;" % color)
        self.label.setStyleSheet("color: %s; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;" % color)




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
            button.setFixedHeight(32)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setAccessibleName(option)
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
        self._tooltip_text = str(tooltip or "")
        self.setObjectName("InfoTipButton")
        self.setText("?")
        self.setToolTip(self._tooltip_text)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setFixedSize(16, 16)
        self.clicked.connect(self._show_info_popup)
        self.setStyleSheet(
            "QToolButton#InfoTipButton {"
            "background-color: #1A1F2C;"
            "color: #94A3B8;"
            "border: 1px solid #283145;"
            "border-radius: 8px;"
            "font-size: 10px;"
            "font-weight: 700;"
            "padding: 0px;"
            "margin: 0px;"
            "}"
            "QToolButton#InfoTipButton:hover {"
            "color: #FFFFFF;"
            "border-color: #9C73F2;"
            "background-color: #262142;"
            "}"
            "QToolButton#InfoTipButton:pressed {"
            "background-color: #9C73F2;"
            "color: #080A0F;"
            "}"
        )

    def _show_info_popup(self):
        if not self._tooltip_text:
            return
        pos = self.mapToGlobal(QtCore.QPoint(0, self.height() + 4))
        QtWidgets.QToolTip.showText(pos, self._tooltip_text, self)


class LabeledField(QtWidgets.QWidget):
    def __init__(self, label, widget, tooltip="", parent=None):
        super(LabeledField, self).__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

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


class PageHeader(QtWidgets.QWidget):
    def __init__(self, title, subtitle="", action_widget=None, parent=None):
        super(PageHeader, self).__init__(parent)
        self.setFixedHeight(44)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignVCenter)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("PageTitle")
        text_layout.addWidget(title_label)

        if subtitle:
            sub_label = QtWidgets.QLabel(subtitle)
            sub_label.setObjectName("MutedText")
            text_layout.addWidget(sub_label)

        layout.addLayout(text_layout, 1)

        if action_widget is not None:
            layout.addWidget(action_widget, 0, QtCore.Qt.AlignVCenter)

class RenderHiveMessageDialog(QtWidgets.QDialog):
    """Custom premium dialog replacing generic QMessageBox."""

    def __init__(self, title, message, icon_name="info", buttons=None, parent=None):
        super(RenderHiveMessageDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        
        self._apply_window_theme()
        
        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#080A0E"))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # â”€â”€ Header Frame â”€â”€
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("DialogHeader")
        header_row = QtWidgets.QHBoxLayout(header_frame)
        header_row.setContentsMargins(24, 18, 24, 18)
        header_row.setSpacing(12)
        
        if icon_name == "info":
            icon_color = COLORS["info"]
            lucide_icon = "info"
        elif icon_name == "warning":
            icon_color = COLORS["warning"]
            lucide_icon = "alert-triangle"
        elif icon_name in ("error", "critical"):
            icon_color = COLORS["error"]
            lucide_icon = "x-circle"
        elif icon_name == "success":
            icon_color = COLORS["success"]
            lucide_icon = "check-circle"
        else:
            icon_color = COLORS["primary"]
            lucide_icon = icon_name

        icon_lbl = QtWidgets.QLabel()
        icon_lbl.setPixmap(get_icon(lucide_icon, icon_color, 24).pixmap(24, 24))
        header_row.addWidget(icon_lbl)
        
        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
        header_row.addWidget(title_lbl, 1)
        
        root.addWidget(header_frame)
        

        
        # â”€â”€ Body Frame â”€â”€
        body_frame = QtWidgets.QFrame()
        body_layout = QtWidgets.QVBoxLayout(body_frame)
        body_layout.setContentsMargins(24, 24, 24, 24)
        body_layout.setSpacing(20)

        # Message
        msg_lbl = QtWidgets.QLabel(message)
        msg_lbl.setStyleSheet("font-size: 13px; color: #CBD5E1;")
        msg_lbl.setWordWrap(True)
        body_layout.addWidget(msg_lbl)
        
        body_layout.addStretch()
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        self.clicked_button = None
        if not buttons:
            buttons = [("OK", "primary")]
            
        for btn_text, btn_role in buttons:
            btn = QtWidgets.QPushButton("  " + btn_text + "  ")
            if btn_role == "secondary":
                btn.setObjectName("SecondaryBtn")
            elif btn_role == "destructive":
                btn.setObjectName("DestructiveTonalBtn")
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            
            def make_handler(t):
                return lambda *args: self._on_btn_clicked(t)
            
            btn.clicked.connect(make_handler(btn_text))
            btn_layout.addWidget(btn)
            
        body_layout.addLayout(btn_layout)
        root.addWidget(body_frame, 1)

    def _on_btn_clicked(self, text):
        self.clicked_button = text
        self.accept()
        
    def showEvent(self, event):
        super(RenderHiveMessageDialog, self).showEvent(event)
        self._apply_window_theme()
        
    def _apply_window_theme(self):
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes as wintypes
            hwnd = wintypes.HWND(int(self.winId()))
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(0x00170E0B)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(0x00E1D5CB)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(ctypes.c_int(0x00453128)), 4)
        except Exception:
            pass

    @classmethod
    def show_message(cls, parent, title, message, icon_name="info", buttons=None):
        dlg = cls(title, message, icon_name, buttons, parent)
        dlg.exec_()
        return dlg.clicked_button

# --- Houdini Specific Overrides ---
class InfoButton(InfoTipButton):
    pass

class FieldLabel(QtWidgets.QWidget):
    def __init__(self, text, tooltip="", parent=None):
        super(FieldLabel, self).__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(5)
        label = QtWidgets.QLabel(str(text))
        label.setObjectName("FieldLabel")
        row.addWidget(label)
        if tooltip:
            row.addWidget(InfoButton(tooltip))
        row.addStretch()

class ReadOnlyRow(QtWidgets.QWidget):
    def __init__(self, label, value="—", tooltip="", parent=None):
        super(ReadOnlyRow, self).__init__(parent)
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
        super(InlineStatus, self).__init__(str(text), parent)
        self.setObjectName("InlineStatus")
        self.setWordWrap(True)
        self.set_level(level)

    def set_level(self, level):
        apply_status_appearance(self, level)

