"""Reusable Shadcn-styled VFX widgets for the RenderHive Maya Submitter."""

from __future__ import absolute_import, print_function

import os
from .qt_compat import QtCore, QtGui, QtWidgets
from .qt_theme import COLORS, build_stylesheet
from .icons import get_icon


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
            # Completely suppress mouse wheel scrolling on dropdowns to prevent accidental changes
            if isinstance(obj, QtWidgets.QComboBox):
                event.ignore()
                return True
            # For other inputs (e.g. spinboxes, line edits), only allow if explicitly focused
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
            header.setContentsMargins(12, 6, 12, 6)
            header.setSpacing(6)
            header.setAlignment(QtCore.Qt.AlignVCenter)

            text_box = QtWidgets.QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(1)

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
        self.content_layout.setContentsMargins(12, 8, 12, 10)
        self.content_layout.setSpacing(6)
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

    def __init__(self, caption, value="—", detail="", icon_name="", color=None, parent=None):
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
        self.value_label.setText(str(value if value not in (None, "") else "—"))
        if detail is not None:
            self.detail_label.setText(str(detail))
            self.detail_label.setVisible(bool(detail))


class PathBox(QtWidgets.QWidget):
    """File path field with embedded quick-copy and open-in-folder buttons."""

    def __init__(self, placeholder="Select file or directory…", file_mode=False, parent=None):
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
        self.copy_btn.setFixedSize(28, 28)
        self.copy_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.copy_btn.setAccessibleName("Copy path to clipboard")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

        self.browse_btn = QtWidgets.QPushButton("Browse…")
        self.browse_btn.setObjectName("SecondaryBtn")
        self.browse_btn.setFixedHeight(30)
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
    valueChanged = QtCore.Signal(int)
    editingFinished = QtCore.Signal()

    def __init__(self, parent=None, minimum=0, maximum=1000000, default=0, step=1, suffix="", special_value_text=""):
        super(StepperNumberInput, self).__init__(parent)
        self.setObjectName("StepperFrame")
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        self._step = int(step) if step > 0 else 1
        self._value = int(default)
        self._suffix = str(suffix or "")
        self._special_value_text = str(special_value_text or "")
        self._block_updates = False

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.dec_button = QtWidgets.QPushButton("−")
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
        return int(self._value)

    def setValue(self, value):
        try:
            val = int(value)
        except (ValueError, TypeError):
            val = self._minimum
        val = max(self._minimum, min(self._maximum, val))
        if val != self._value:
            self._value = val
            self._update_display()
            self.valueChanged.emit(self._value)
        else:
            self._update_display()

    def minimum(self):
        return self._minimum

    def setMinimum(self, minimum):
        self._minimum = int(minimum)
        if self._value < self._minimum:
            self.setValue(self._minimum)
        self._update_display()

    def maximum(self):
        return self._maximum

    def setMaximum(self, maximum):
        self._maximum = int(maximum)
        if self._value > self._maximum:
            self.setValue(self._maximum)
        self._update_display()

    def setRange(self, minimum, maximum):
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        if self._value < self._minimum:
            self.setValue(self._minimum)
        elif self._value > self._maximum:
            self.setValue(self._maximum)
        self._update_display()

    def singleStep(self):
        return self._step

    def setSingleStep(self, step):
        self._step = max(1, int(step))

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

    def _update_display(self):
        if self._block_updates:
            return
        if self._special_value_text and self._value == self._minimum:
            text = self._special_value_text
        else:
            text = "{}{}".format(self._value, self._suffix)
        self.line_edit.setText(text)
        self.dec_button.setEnabled(self.isEnabled() and self._value > self._minimum)
        self.inc_button.setEnabled(self.isEnabled() and self._value < self._maximum)

    def _on_editing_finished(self):
        raw = self.line_edit.text().strip()
        if self._suffix and raw.endswith(self._suffix):
            raw = raw[:-len(self._suffix)].strip()
        if self._special_value_text and raw.lower() == self._special_value_text.lower():
            self.setValue(self._minimum)
            self.editingFinished.emit()
            return
        try:
            val = int(raw)
            self.setValue(val)
        except ValueError:
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
            "border-radius: 4px;"
            "padding: 2px 8px;"
            "font-size: 10.5px;"
            "font-weight: 600;"
            "min-height: 20px;"
            "max-height: 20px;"
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
            "success": COLORS["success"],
            "online": COLORS["success"],
            "passed": COLORS["success"],
            "ready": COLORS["success"],
            "connected": COLORS["success"],
            "warning": COLORS["warning"],
            "busy": COLORS["warning"],
            "rendering": COLORS["warning"],
            "error": COLORS["error"],
            "offline": COLORS["error"],
            "failed": COLORS["error"],
            "info": COLORS["info"],
            "paused": COLORS["paused"],
            "muted": COLORS["muted"],
        }
        color = color_map.get(str(status).lower(), COLORS["info"])
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
        self.setFixedHeight(38)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(QtCore.Qt.AlignVCenter)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

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

        # ── Header Frame ──
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
        

        
        # ── Body Frame ──
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


class ValidationRulesDialog(QtWidgets.QDialog):
    """
    Modal dialog allowing users to customize validation rules, severity enforcement,
    presets (Studio Strict, LookDev, Standard), and configure required AOVs (e.g. Cryptomatte).
    """

    KNOWN_RULES = [
        ("SCENE_NOT_SAVED", "Scene File", "Scene is saved to disk with valid path", "ERROR"),
        ("SCENE_UNSAVED_CHANGES", "Scene File", "Scene has no unsaved modifications", "WARNING"),
        ("RENDERER_NOT_ARNOLD", "Renderer", "Renderer matches configured Arnold target", "ERROR"),
        ("REQUIRED_AOV_MISSING", "AOVs & Layers", "Configured required AOVs (Cryptomatte, etc.) exist", "ERROR"),
        ("AOV_DRIVER_MISSING", "AOVs & Layers", "Active AOVs have valid output drivers connected", "WARNING"),
        ("RENDER_REGION_ENABLED", "Render Globals", "Render region / crop window is disabled", "WARNING"),
        ("FRAME_STEP_INVALID", "Frame Range", "Frame step is a positive integer", "ERROR"),
        ("RESOLUTION_ZERO", "Resolution", "Width and height are greater than zero", "ERROR"),
        ("RESOLUTION_NON_STANDARD", "Resolution", "Resolution matches standard production aspect", "INFO"),
        ("CAMERA_NOT_RENDERABLE", "Camera", "Selected camera is marked renderable", "ERROR"),
        ("CAMERA_CLIPPING_SUSPICIOUS", "Camera", "Camera near/far clip planes are within sane ranges", "WARNING"),
        ("TEXTURE_MISSING", "Dependencies", "File texture paths exist on shared storage / disk", "ERROR"),
        ("REFERENCE_MISSING", "Dependencies", "Referenced Maya files exist and are loaded", "ERROR"),
        ("CACHE_FILE_MISSING", "Dependencies", "Alembic / GPU / VDB cache files exist", "ERROR"),
        ("NON_MANIFOLD_VERTICES", "Geometry", "Geometry has no non-manifold vertices", "WARNING"),
        ("NON_MANIFOLD_EDGES", "Geometry", "Geometry has no non-manifold edges", "WARNING"),
        ("TRANSFORM_HISTORY_HEAVY", "Geometry", "Deformation history and node count within thresholds", "INFO"),
        ("LIGHT_ZERO_INTENSITY", "Lighting", "Active lights have non-zero exposure / intensity", "INFO"),
    ]

    def __init__(self, current_overrides=None, current_aovs=None, parent=None):
        super(ValidationRulesDialog, self).__init__(parent)
        self.setObjectName("RenderHiveDialog")
        self.setWindowTitle("RenderHive — Validation Rules & AOV Enforcement")
        self.setMinimumSize(740, 600)
        self.resize(780, 660)
        self.setModal(True)

        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#080A0E"))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(build_stylesheet())

        self.rule_overrides = dict(current_overrides or {})
        self.required_aovs = list(current_aovs) if current_aovs is not None else [
            "crypto_asset",
            "crypto_object",
            "crypto_material",
        ]
        self.rule_combos = {}

        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (#0B0E17 matching DWM Titlebar & Settings Dialog) ──
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("DialogHeader")
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(3)

        title = QtWidgets.QLabel("Validation Rules & Severity Control")
        title.setObjectName("PageTitle")
        subtitle = QtWidgets.QLabel(
            "Customize how scene checks are enforced. Errors prevent job submission, "
            "warnings advise artists, and disabled checks are skipped entirely."
        )
        subtitle.setObjectName("MutedLabel")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px; margin-top: 2px;")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_frame)

        # ── Body Content ──
        body_widget = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 16, 24, 16)
        body_layout.setSpacing(12)

        # Presets Bar
        preset_card = SectionCard("RULE PRESETS", "Quickly apply standard studio enforcement profiles")
        preset_row = QtWidgets.QHBoxLayout()
        preset_row.setSpacing(8)

        btn_std = QtWidgets.QPushButton("Standard (Default)")
        btn_std.setObjectName("SecondaryBtn")
        btn_std.setCursor(QtCore.Qt.PointingHandCursor)
        btn_std.clicked.connect(lambda: self._apply_profile("standard"))

        btn_strict = QtWidgets.QPushButton("Studio Strict")
        btn_strict.setObjectName("SecondaryBtn")
        btn_strict.setCursor(QtCore.Qt.PointingHandCursor)
        btn_strict.clicked.connect(lambda: self._apply_profile("studio_strict"))

        btn_lookdev = QtWidgets.QPushButton("LookDev / Relaxed")
        btn_lookdev.setObjectName("SecondaryBtn")
        btn_lookdev.setCursor(QtCore.Qt.PointingHandCursor)
        btn_lookdev.clicked.connect(lambda: self._apply_profile("lookdev"))

        preset_row.addWidget(btn_std)
        preset_row.addWidget(btn_strict)
        preset_row.addWidget(btn_lookdev)
        preset_row.addStretch()
        preset_card.add_layout(preset_row)
        body_layout.addWidget(preset_card)

        # Required AOVs Card
        aov_card = SectionCard("REQUIRED AOVS / CRYPTOMATTE", "Specify required AOVs that must be active in Arnold")
        aov_row = QtWidgets.QHBoxLayout()
        aov_row.setSpacing(8)
        self.aov_input = QtWidgets.QLineEdit(", ".join(self.required_aovs))
        self.aov_input.setObjectName("InputField")
        self.aov_input.setPlaceholderText("e.g. crypto_asset, crypto_object, crypto_material, Z, RGBA")
        aov_row.addWidget(self.aov_input, 1)

        btn_crypto_reset = QtWidgets.QPushButton("Cryptomatte Defaults")
        btn_crypto_reset.setObjectName("GhostBtn")
        btn_crypto_reset.setCursor(QtCore.Qt.PointingHandCursor)
        btn_crypto_reset.clicked.connect(self._reset_aov_defaults)
        aov_row.addWidget(btn_crypto_reset)
        aov_card.add_layout(aov_row)
        body_layout.addWidget(aov_card)

        # Rule Tree Table
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("RulesTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Validation Check / Rule", "Category", "Severity"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.tree.setColumnWidth(2, 195)

        self._populate_rules()
        body_layout.addWidget(self.tree, 1)

        root.addWidget(body_widget, 1)

        # ── Full-Width Divider above action buttons ──
        actions_divider = QtWidgets.QFrame()
        actions_divider.setObjectName("SheetDivider")
        actions_divider.setFixedHeight(1)
        root.addWidget(actions_divider)

        # ── Full-Width Dialog Footer (#0B0E17 matching DWM Titlebar & Settings Dialog) ──
        footer_frame = QtWidgets.QFrame()
        footer_frame.setObjectName("DialogFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(8)

        reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        reset_btn.setObjectName("GhostBtn")
        reset_btn.setCursor(QtCore.Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_factory_defaults)
        footer_layout.addWidget(reset_btn)

        footer_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        save_btn = QtWidgets.QPushButton("  Save Changes")
        save_btn.setObjectName("SubmitButton")
        save_btn.setIcon(get_icon("check", COLORS["primary_fg"], 13))
        save_btn.setCursor(QtCore.Qt.PointingHandCursor)
        save_btn.setFixedHeight(30)
        save_btn.setMinimumWidth(130)
        save_btn.clicked.connect(self._save_and_accept)
        footer_layout.addWidget(save_btn)

        root.addWidget(footer_frame)

    def _populate_rules(self):
        self.tree.clear()
        self.rule_combos.clear()

        for code, category, desc, default_sev in self.KNOWN_RULES:
            item = QtWidgets.QTreeWidgetItem([desc, category, ""])
            item.setData(0, QtCore.Qt.UserRole, code)
            item.setSizeHint(0, QtCore.QSize(0, 28))
            item.setSizeHint(1, QtCore.QSize(0, 28))
            item.setSizeHint(2, QtCore.QSize(0, 28))
            item.setTextAlignment(0, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            item.setTextAlignment(1, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            self.tree.addTopLevelItem(item)

            combo = QtWidgets.QComboBox()
            combo.setObjectName("SeverityCombo")
            combo.setCursor(QtCore.Qt.PointingHandCursor)
            ScrollFilter.install(combo)
            combo.addItems(["Required (Error)", "Optional (Warning)", "Advisory (Info)", "Disabled (Ignore)"])

            current_val = self.rule_overrides.get(code, default_sev).upper()
            if current_val == "ERROR":
                combo.setCurrentIndex(0)
            elif current_val == "WARNING":
                combo.setCurrentIndex(1)
            elif current_val == "INFO":
                combo.setCurrentIndex(2)
            elif current_val in ("DISABLED", "IGNORE", "OFF"):
                combo.setCurrentIndex(3)
            else:
                combo.setCurrentIndex(0)

            self.rule_combos[code] = combo

            cell_container = QtWidgets.QWidget()
            cell_layout = QtWidgets.QHBoxLayout(cell_container)
            cell_layout.setContentsMargins(2, 0, 2, 0)
            cell_layout.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            cell_layout.addWidget(combo)
            self.tree.setItemWidget(item, 2, cell_container)

    def _apply_profile(self, profile_name):
        from validation.validator import RULE_PROFILES
        prof = RULE_PROFILES.get(profile_name, {})
        overrides = prof.get("overrides", {})

        for code, combo in self.rule_combos.items():
            target_sev = overrides.get(code)
            if not target_sev:
                for c, cat, desc, def_sev in self.KNOWN_RULES:
                    if c == code:
                        target_sev = def_sev
                        break

            target_sev = (target_sev or "ERROR").upper()
            if target_sev == "ERROR":
                combo.setCurrentIndex(0)
            elif target_sev == "WARNING":
                combo.setCurrentIndex(1)
            elif target_sev == "INFO":
                combo.setCurrentIndex(2)
            elif target_sev in ("DISABLED", "IGNORE", "OFF"):
                combo.setCurrentIndex(3)

    def _reset_aov_defaults(self):
        self.aov_input.setText("crypto_asset, crypto_object, crypto_material")

    def _reset_factory_defaults(self):
        self.rule_overrides.clear()
        self._populate_rules()
        self._reset_aov_defaults()

    def _save_and_accept(self):
        self.rule_overrides = {}
        for code, combo in self.rule_combos.items():
            idx = combo.currentIndex()
            if idx == 0:
                self.rule_overrides[code] = "ERROR"
            elif idx == 1:
                self.rule_overrides[code] = "WARNING"
            elif idx == 2:
                self.rule_overrides[code] = "INFO"
            elif idx == 3:
                self.rule_overrides[code] = "DISABLED"

        raw_aovs = self.aov_input.text().split(",")
        self.required_aovs = [a.strip() for a in raw_aovs if a.strip()]
        self.accept()

    def showEvent(self, event):
        super(ValidationRulesDialog, self).showEvent(event)
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


class LocalRenderDialog(QtWidgets.QDialog):
    """
    Modal dialog allowing artists to render individual frames locally in Maya
    with interactive feedback before farm submission.
    """

    def __init__(self, submitter=None, parent=None):
        super(LocalRenderDialog, self).__init__(parent)
        self.submitter = submitter
        self.setObjectName("RenderHiveDialog")
        self.setWindowTitle("RenderHive — Local Single Frame Render")
        self.setMinimumSize(580, 480)
        self.resize(620, 520)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)

        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#080A0E"))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(build_stylesheet())

        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (#0B0E17 matching DWM Titlebar & Settings Dialog) ──
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("DialogHeader")
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(3)

        title = QtWidgets.QLabel("Local Single-Frame Test Render")
        title.setObjectName("PageTitle")
        subtitle = QtWidgets.QLabel(
            "Render a test frame on this workstation using Arnold to verify shaders, "
            "lighting, and AOVs before submitting the full sequence to the render farm."
        )
        subtitle.setObjectName("MutedLabel")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px; margin-top: 2px;")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_frame)

        # ── Body Content ──
        body_widget = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 16, 24, 16)
        body_layout.setSpacing(12)

        # Settings Card
        settings_card = SectionCard("TEST RENDER PARAMETERS", "Configure frame and camera target")
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QtWidgets.QLabel("Target Frame:"), 0, 0)
        self.frame_spin = QtWidgets.QSpinBox()
        self.frame_spin.setObjectName("NumberInput")
        self.frame_spin.setRange(-999999, 999999)
        current_frame = 1
        if self.submitter:
            if hasattr(self.submitter, "field_value"):
                try:
                    current_frame = int(self.submitter.field_value("rh_frame_start"))
                except Exception:
                    pass
            elif hasattr(self.submitter, "api") and hasattr(self.submitter.api, "get_frame_range"):
                try:
                    current_frame = int(self.submitter.api.get_frame_range()[0])
                except Exception:
                    pass
        self.frame_spin.setValue(current_frame)
        grid.addWidget(self.frame_spin, 0, 1)

        grid.addWidget(QtWidgets.QLabel("Render Camera:"), 1, 0)
        self.cam_combo = QtWidgets.QComboBox()
        self.cam_combo.setObjectName("SelectField")
        cameras = ["persp"]
        try:
            if self.submitter and hasattr(self.submitter, "api") and hasattr(self.submitter.api, "get_cameras"):
                cams = self.submitter.api.get_cameras()
                if cams:
                    cameras = list(cams)
            elif "maya.cmds" in sys.modules:
                import maya.cmds as cmds
                cams = cmds.ls(cameras=True) or []
                if cams:
                    cameras = [cmds.listRelatives(c, parent=True)[0] if cmds.listRelatives(c, parent=True) else c for c in cams]
        except Exception:
            pass
        self.cam_combo.addItems(cameras)
        if self.submitter and hasattr(self.submitter, "field_value"):
            sel_cam = self.submitter.field_value("rh_render_camera")
            if sel_cam and self.cam_combo.findText(sel_cam) >= 0:
                self.cam_combo.setCurrentText(sel_cam)
        self.cam_combo.setCursor(QtCore.Qt.PointingHandCursor)
        ScrollFilter.install(self.cam_combo)
        grid.addWidget(self.cam_combo, 1, 1)

        grid.addWidget(QtWidgets.QLabel("Render Layer:"), 2, 0)
        self.layer_combo = QtWidgets.QComboBox()
        self.layer_combo.setObjectName("SelectField")
        self.layer_combo.setCursor(QtCore.Qt.PointingHandCursor)
        layers = ["defaultRenderLayer"]
        try:
            if self.submitter and hasattr(self.submitter, "api") and hasattr(self.submitter.api, "get_render_layers"):
                raw_layers = self.submitter.api.get_render_layers() or []
                layers = [item.get("name", "defaultRenderLayer") if isinstance(item, dict) else str(item) for item in raw_layers]
            elif "maya.cmds" in sys.modules:
                import maya.cmds as cmds
                if cmds.objExists("renderLayerManager"):
                    layers = cmds.listConnections("renderLayerManager.renderLayerUsages") or ["defaultRenderLayer"]
        except Exception:
            pass
        self.layer_combo.addItems(layers)
        ScrollFilter.install(self.layer_combo)
        grid.addWidget(self.layer_combo, 2, 1)

        settings_card.add_layout(grid)
        body_layout.addWidget(settings_card)

        # Status & Log Console
        self.log_edit = QtWidgets.QTextEdit()
        self.log_edit.setObjectName("ConsoleBox")
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("Test render output logs will appear here...")
        self.log_edit.setStyleSheet(
            "background-color: #09090B; border: 1px solid #27272A; border-radius: 6px; "
            "padding: 8px; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 11px; color: #A1A1AA;"
        )
        body_layout.addWidget(self.log_edit, 1)

        root.addWidget(body_widget, 1)

        # ── Full-Width Divider above action buttons ──
        actions_divider = QtWidgets.QFrame()
        actions_divider.setObjectName("SheetDivider")
        actions_divider.setFixedHeight(1)
        root.addWidget(actions_divider)

        # ── Full-Width Dialog Footer (#0B0E17 matching DWM Titlebar & Settings Dialog) ──
        footer_frame = QtWidgets.QFrame()
        footer_frame.setObjectName("DialogFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setObjectName("SecondaryBtn")
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setFixedHeight(30)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        open_rv_btn = QtWidgets.QPushButton("  Open Render View")
        open_rv_btn.setObjectName("SecondaryBtn")
        open_rv_btn.setIcon(get_icon("image", COLORS["secondary"], 13))
        open_rv_btn.setCursor(QtCore.Qt.PointingHandCursor)
        open_rv_btn.setFixedHeight(30)
        open_rv_btn.clicked.connect(self._open_render_view)
        footer_layout.addWidget(open_rv_btn)

        self.render_btn = QtWidgets.QPushButton("  Render Frame Now")
        self.render_btn.setObjectName("SubmitButton")
        self.render_btn.setIcon(get_icon("cube", COLORS["primary_fg"], 13))
        self.render_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.render_btn.setFixedHeight(30)
        self.render_btn.setMinimumWidth(160)
        self.render_btn.clicked.connect(self._start_local_render)
        footer_layout.addWidget(self.render_btn)

        root.addWidget(footer_frame)

    def _open_render_view(self):
        try:
            import maya.mel as mel
            import maya.cmds as cmds
            mel.eval('RenderViewWindow;')
            if cmds.window("renderViewWindow", exists=True):
                cmds.showWindow("renderViewWindow")
            self.log_edit.append("[RenderHive] Maya Render View window opened.")
        except Exception as error:
            self.log_edit.append("[RenderHive] Could not open Render View: {}".format(error))

    def _start_local_render(self):
        target_frame = self.frame_spin.value()
        target_cam = self.cam_combo.currentText()
        target_layer = self.layer_combo.currentText()

        self.log_edit.append("[RenderHive] Starting local test render of frame {} (Camera: {}, Layer: {})...".format(
            target_frame, target_cam, target_layer
        ))
        self.render_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            render_func = None
            try:
                from renderhive_maya_submitter import render_frame_locally
                render_func = render_frame_locally
            except ImportError:
                if self.submitter and hasattr(self.submitter, "api") and hasattr(self.submitter.api, "render_frame_locally"):
                    render_func = self.submitter.api.render_frame_locally

            if render_func:
                result = render_func(
                    frame=target_frame,
                    camera=target_cam,
                    layer=target_layer,
                    show_render_view=True,
                )
            else:
                import maya.cmds as cmds
                import maya.mel as mel
                try:
                    mel.eval('RenderViewWindow;')
                    mel.eval('renderWindowRenderCamera "render" "renderView" "{}";'.format(target_cam))
                except Exception:
                    cmds.currentTime(int(target_frame))
                    cmds.render(target_cam)
                result = {
                    "success": True,
                    "frame": target_frame,
                    "camera": target_cam,
                    "layer": target_layer,
                    "message": "Rendered frame {} into Maya Render View.".format(target_frame),
                }

            if result.get("success"):
                self.log_edit.append("[RenderHive] SUCCESS: Frame {} rendered in Maya Render View.".format(target_frame))
                if result.get("resolution"):
                    self.log_edit.append("[RenderHive] Render Resolution: {}".format(result.get("resolution")))
                self.log_edit.append("[RenderHive] Check Maya's Render View window for the rendered output buffer.")
            else:
                self.log_edit.append("[RenderHive] ERROR: {}".format(result.get("message") or result.get("error")))
        except Exception as error:
            self.log_edit.append("[RenderHive] EXCEPTION: {}".format(error))
        finally:
            self.render_btn.setEnabled(True)

    def showEvent(self, event):
        super(LocalRenderDialog, self).showEvent(event)
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

