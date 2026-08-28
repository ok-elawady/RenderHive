"""Settings and configuration dialog for RenderHive Worker matching frontend sidesheet layout."""

from __future__ import annotations

import os
import platform
import socket
import sys
import time
from typing import Dict, List, Optional

import requests
from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from core.dcc_discovery import DCCInstallation, discover_all
from daemon.api_client import RenderHiveApiClient
from ui.icons import get_icon
from version import WORKER_VERSION

HOSTNAME = socket.gethostname()


class ComboItemDelegate(QStyledItemDelegate):
    """Prevents Qt setPointSize <= 0 warnings when pixel-based font sizes are used in stylesheets."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if option.font.pointSize() <= 0:
            if option.font.pixelSize() > 0:
                option.font.setPointSize(max(1, int(option.font.pixelSize() * 72 / 96)))
            else:
                option.font.setPointSize(10)


class CleanComboBox(QComboBox):
    """QComboBox subclass that guarantees a valid point-size font before popup display,
    preventing Qt's internal QFont::setPointSize(-1) warning when pixel font sizes are used."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        font = QFont("Inter", 10)
        self.setFont(font)
        self.setItemDelegate(ComboItemDelegate(self))
        if self.view():
            self.view().setFont(font)

    def showPopup(self) -> None:
        font = self.font()
        if font.pointSize() <= 0:
            font.setPointSize(10)
            self.setFont(font)
        if self.view():
            v_font = self.view().font()
            if v_font.pointSize() <= 0:
                v_font.setPointSize(10)
                self.view().setFont(v_font)
            container = self.view().window()
            if container:
                container.setFont(font)
        super().showPopup()


class NoWheelFilter(QObject):
    """Prevents mouse wheel scrolling over inputs from inadvertently altering values."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class ConnectionTester(QThread):
    """Background worker thread for asynchronous, thread-safe backend ping testing."""

    finished_signal = Signal(str, str)  # status: "success" | "error", message: str

    def __init__(self, api_url: str, api_token: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token

    def run(self) -> None:
        t0 = time.monotonic()
        try:
            client = RenderHiveApiClient(self.api_url, self.api_token)
            payload = {
                "hostname": HOSTNAME,
                "worker_version": WORKER_VERSION,
                "capabilities": {},
                "operating_system": platform.system(),
            }
            resp = client.ping(payload, timeout=5.0)
            latency_ms = max(1, int((time.monotonic() - t0) * 1000))
            if 200 <= resp.status_code < 300:
                self.finished_signal.emit("success", f"Connected ({latency_ms}ms)")
            elif resp.status_code in (401, 403):
                self.finished_signal.emit("error", f"Unauthorized ({resp.status_code})")
            else:
                self.finished_signal.emit("error", f"Server Error ({resp.status_code})")
        except requests.exceptions.Timeout:
            self.finished_signal.emit("error", "Connection Timed Out")
        except requests.exceptions.ConnectionError:
            self.finished_signal.emit("error", "Connection Refused")
        except Exception as exc:
            self.finished_signal.emit("error", f"Failed: {exc}")


class StepperNumberInput(QFrame):
    """Modern input field with embedded horizontal minus/plus buttons."""

    valueChanged = Signal(int)

    def __init__(
        self,
        min_val: int = 2,
        max_val: int = 30,
        value: int = 5,
        suffix: str = " seconds",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("StepperFrame")
        self._min_val = min_val
        self._max_val = max_val
        self._value = max(min_val, min(max_val, value))
        self._suffix = suffix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("StepperInput")
        self.input_field.setText(f"{self._value}{self._suffix}")
        self.input_field.editingFinished.connect(self._on_text_edited)
        layout.addWidget(self.input_field, 1)

        # Minus Button
        self.minus_btn = QPushButton()
        self.minus_btn.setObjectName("StepperBtn")
        self.minus_btn.setIcon(get_icon("minus", "#94A3B8", 12))
        self.minus_btn.setCursor(Qt.PointingHandCursor)
        self.minus_btn.setFixedSize(20, 20)
        self.minus_btn.clicked.connect(self.decrement)
        layout.addWidget(self.minus_btn)

        # Plus Button
        self.plus_btn = QPushButton()
        self.plus_btn.setObjectName("StepperBtn")
        self.plus_btn.setIcon(get_icon("plus", "#94A3B8", 12))
        self.plus_btn.setCursor(Qt.PointingHandCursor)
        self.plus_btn.setFixedSize(20, 20)
        self.plus_btn.clicked.connect(self.increment)
        layout.addWidget(self.plus_btn)

        self._update_btn_states()

    def value(self) -> int:
        return self._value

    def setValue(self, val: int) -> None:
        self._value = max(self._min_val, min(self._max_val, int(val)))
        self.input_field.setText(f"{self._value}{self._suffix}")
        self._update_btn_states()
        self.valueChanged.emit(self._value)

    def setRange(self, min_val: int, max_val: int) -> None:
        self._min_val = min_val
        self._max_val = max_val
        self.setValue(self._value)

    def setSuffix(self, suffix: str) -> None:
        self._suffix = suffix
        self.setValue(self._value)

    def increment(self) -> None:
        if self._value < self._max_val:
            self.setValue(self._value + 1)

    def decrement(self) -> None:
        if self._value > self._min_val:
            self.setValue(self._value - 1)

    def _on_text_edited(self) -> None:
        text = self.input_field.text()
        import re

        digits = re.findall(r"\d+", text)
        if digits:
            new_val = int(digits[0])
            self.setValue(new_val)
        else:
            self.setValue(self._value)

    def _update_btn_states(self) -> None:
        can_dec = self._value > self._min_val
        can_inc = self._value < self._max_val
        self.minus_btn.setEnabled(can_dec)
        self.plus_btn.setEnabled(can_inc)
        self.minus_btn.setIcon(get_icon("minus", "#94A3B8" if can_dec else "#374151", 12))
        self.plus_btn.setIcon(get_icon("plus", "#94A3B8" if can_inc else "#374151", 12))


class SettingsDialog(QDialog):
    """Configuration modal matching the Shadcn/UI sidesheet layout from the frontend."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Worker Settings")
        self.setMinimumSize(680, 600)
        self.resize(700, 660)
        self.settings = QSettings("RenderHive", "WorkerDaemon")
        self._wheel_filter = NoWheelFilter(self)
        self._tester_thread: Optional[ConnectionTester] = None

        # Window background matching #080A0E
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#080A0E"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (#0B0E17 matching DWM Titlebar & Frontend SheetHeader) ──
        header_frame = QFrame()
        header_frame.setObjectName("DialogHeader")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(3)
        title = QLabel("Worker Node Configuration")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Configure network authentication, worker metadata, and dispatch behavior.")
        subtitle.setObjectName("MutedLabel")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_frame)

        # Full-width Header Separator Divider
        header_divider = QFrame()
        header_divider.setObjectName("DialogDivider")
        header_divider.setFixedHeight(1)
        root.addWidget(header_divider)

        # ── Scrollable Body Area (Sidesheet Content) ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("SettingsScrollArea")
        body = QWidget()
        body.setObjectName("SettingsBody")
        scroll.setWidget(body)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(18)
        root.addWidget(scroll, 1)

        # ── Section 1: Backend Connection ──
        sec_conn = QWidget()
        sec_conn_layout = QVBoxLayout(sec_conn)
        sec_conn_layout.setContentsMargins(0, 0, 0, 0)
        sec_conn_layout.setSpacing(8)
        sec_conn_layout.addWidget(
            self._create_section_header(
                "globe",
                "BACKEND CONNECTION",
                "Server endpoint and authentication token for worker orchestration.",
            )
        )

        conn_form = QFormLayout()
        conn_form.setHorizontalSpacing(16)
        conn_form.setVerticalSpacing(8)
        conn_form.setContentsMargins(0, 4, 0, 0)
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("http://server.renderhive.local/api")
        self.api_url_input.setText(self.settings.value("api_url", "http://server.renderhive.local/api"))
        self.api_url_input.textChanged.connect(self._on_connection_input_changed)
        conn_form.addRow("API URL", self.api_url_input)
        self.api_token_input = QLineEdit()
        self.api_token_input.setPlaceholderText("Enter worker authentication token")
        self.api_token_input.setText(self.settings.value("api_token", ""))
        self.api_token_input.setEchoMode(QLineEdit.Password)
        self.api_token_input.textChanged.connect(self._on_connection_input_changed)
        conn_form.addRow("API Token", self.api_token_input)
        sec_conn_layout.addLayout(conn_form)

        # Test Connection Row with Status Badge
        test_row = QHBoxLayout()
        test_row.setSpacing(12)
        test_row.setContentsMargins(0, 4, 0, 0)
        self.test_conn_btn = QPushButton("  Test Connection")
        self.test_conn_btn.setObjectName("SecondaryBtn")
        self.test_conn_btn.setIcon(get_icon("radio", "#CBD5E1", 13))
        self.test_conn_btn.setFixedHeight(32)
        self.test_conn_btn.setMinimumWidth(140)
        self.test_conn_btn.setCursor(Qt.PointingHandCursor)
        self.test_conn_btn.clicked.connect(self.test_connection)
        test_row.addWidget(self.test_conn_btn)

        self.test_status_label = QLabel()
        self.test_status_label.setObjectName("TestStatusBadge")
        self.test_status_label.setVisible(False)
        test_row.addWidget(self.test_status_label)
        test_row.addStretch()
        sec_conn_layout.addLayout(test_row)

        body_layout.addWidget(sec_conn)

        # Divider
        body_layout.addWidget(self._create_section_divider())

        # ── Section 2: Worker Node Metadata ──
        sec_meta = QWidget()
        sec_meta_layout = QVBoxLayout(sec_meta)
        sec_meta_layout.setContentsMargins(0, 0, 0, 0)
        sec_meta_layout.setSpacing(8)
        sec_meta_layout.addWidget(
            self._create_section_header(
                "sliders",
                "WORKER NODE METADATA",
                "Node metadata published to the central coordinator for farm management and routing.",
            )
        )

        meta_form = QFormLayout()
        meta_form.setHorizontalSpacing(16)
        meta_form.setVerticalSpacing(8)
        meta_form.setContentsMargins(0, 4, 0, 0)
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("e.g. Workstation Room 204")
        self.description_input.setText(self.settings.value("description", ""))
        meta_form.addRow("Description", self.description_input)
        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("e.g. RTX 4090 render box")
        self.comment_input.setText(self.settings.value("comment", ""))
        meta_form.addRow("Comment", self.comment_input)
        self.region_input = QLineEdit()
        self.region_input.setText(self.settings.value("region", "Default"))
        meta_form.addRow("Region", self.region_input)
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Example: gpu, studio-a, overnight")
        self.tags_input.setText(self.settings.value("custom_tags", ""))
        meta_form.addRow("Custom Tags", self.tags_input)
        self.pools_input = QLineEdit()
        self.pools_input.setPlaceholderText("Leave empty to preserve server assignments, or enter: GPU, VFX")
        self.pools_input.setText(self.settings.value("custom_pools", ""))
        meta_form.addRow("Assigned Pools", self.pools_input)
        sec_meta_layout.addLayout(meta_form)
        body_layout.addWidget(sec_meta)

        # Divider
        body_layout.addWidget(self._create_section_divider())

        # ── Section 3: Scheduling & Daemon Behavior ──
        sec_sched = QWidget()
        sec_sched_layout = QVBoxLayout(sec_sched)
        sec_sched_layout.setContentsMargins(0, 0, 0, 0)
        sec_sched_layout.setSpacing(8)
        sec_sched_layout.addWidget(
            self._create_section_header(
                "clock",
                "SCHEDULING & DAEMON BEHAVIOR",
                "Control poll frequency and automatic task dequeue policies.",
            )
        )

        sched_form = QFormLayout()
        sched_form.setHorizontalSpacing(16)
        sched_form.setVerticalSpacing(8)
        self.poll_interval_input = StepperNumberInput(
            min_val=2,
            max_val=30,
            value=int(self.settings.value("poll_interval", 5) or 5),
            suffix=" seconds",
        )
        sched_form.addRow("Dispatch Interval", self.poll_interval_input)
        self.after_task_combo = CleanComboBox()
        self.after_task_combo.addItem("Continue to the next task", "continue")
        self.after_task_combo.addItem("Pause dispatch after the current task", "pause")
        saved_after = str(self.settings.value("after_task", "continue") or "continue")
        self.after_task_combo.setCurrentIndex(1 if saved_after == "pause" else 0)
        self.after_task_combo.installEventFilter(self._wheel_filter)
        self.after_task_combo.view().setAutoScroll(False)
        sched_form.addRow("After Task", self.after_task_combo)
        self.auto_start_check = QCheckBox("Start the worker automatically when the application opens")
        self.auto_start_check.setChecked(str(self.settings.value("auto_start", "false")).lower() == "true")
        sched_form.addRow("", self.auto_start_check)
        self.start_minimized_check = QCheckBox("Open minimized to the system tray")
        self.start_minimized_check.setChecked(str(self.settings.value("start_minimized", "false")).lower() == "true")
        sched_form.addRow("", self.start_minimized_check)
        sec_sched_layout.addLayout(sched_form)
        body_layout.addWidget(sec_sched)



        # ── Full-Width Divider above action buttons ──
        actions_divider = QFrame()
        actions_divider.setObjectName("DialogDivider")
        actions_divider.setFixedHeight(1)
        root.addWidget(actions_divider)

        # ── Full-Width Dialog Footer (#0B0E17 matching DWM Titlebar) ──
        footer_frame = QFrame()
        footer_frame.setObjectName("DialogFooter")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(34)
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("  Save Settings")
        save_btn.setIcon(get_icon("check", "#0E1016", 13))
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self.save_settings)
        footer_layout.addWidget(cancel_btn)
        footer_layout.addWidget(save_btn)
        root.addWidget(footer_frame)

    def _create_section_header(self, icon_name: str, title_text: str, desc_text: str = "") -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(7)
        title_row.setContentsMargins(1, 0, 0, 0)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon(icon_name, "#9C73F2", 14).pixmap(14, 14))
        icon_lbl.setFixedSize(14, 14)
        title_row.addWidget(icon_lbl)

        title_lbl = QLabel(title_text)
        title_lbl.setObjectName("SheetSectionTitle")
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        layout.addLayout(title_row)

        if desc_text:
            desc_lbl = QLabel(desc_text)
            desc_lbl.setObjectName("MutedLabel")
            desc_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; margin-top: 2px;")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        return container

    def _create_section_divider(self) -> QFrame:
        divider = QFrame()
        divider.setObjectName("SheetDivider")
        divider.setFixedHeight(1)
        return divider

    def _on_connection_input_changed(self) -> None:
        if hasattr(self, "test_status_label"):
            self.test_status_label.setVisible(False)

    def test_connection(self) -> None:
        api_url = self.api_url_input.text().strip()
        api_token = self.api_token_input.text().strip()
        if not api_url:
            self._set_test_status("error", "API URL is required")
            return

        self.test_conn_btn.setEnabled(False)
        self.test_conn_btn.setText("  Testing…")
        self._set_test_status("testing", "Connecting to backend…")

        if self._tester_thread and self._tester_thread.isRunning():
            self._tester_thread.terminate()

        self._tester_thread = ConnectionTester(api_url, api_token, self)
        self._tester_thread.finished_signal.connect(self._on_test_finished)
        self._tester_thread.start()

    def _on_test_finished(self, status: str, message: str) -> None:
        self.test_conn_btn.setEnabled(True)
        self.test_conn_btn.setText("  Test Connection")
        self._set_test_status(status, message)

    def _set_test_status(self, status: str, message: str) -> None:
        self.test_status_label.setVisible(True)
        if status == "success":
            self.test_status_label.setText(f"✓  {message}")
            self.test_status_label.setStyleSheet(
                "color: #4ADE80; background-color: rgba(74, 222, 128, 0.12); "
                "border: 1px solid rgba(74, 222, 128, 0.35); border-radius: 6px; "
                "padding: 4px 10px; font-weight: 600; font-size: 12px;"
            )
        elif status == "testing":
            self.test_status_label.setText(f"●  {message}")
            self.test_status_label.setStyleSheet(
                "color: #C084FC; background-color: rgba(192, 132, 252, 0.12); "
                "border: 1px solid rgba(192, 132, 252, 0.35); border-radius: 6px; "
                "padding: 4px 10px; font-weight: 500; font-size: 12px;"
            )
        else:
            self.test_status_label.setText(f"✕  {message}")
            self.test_status_label.setStyleSheet(
                "color: #F87171; background-color: rgba(248, 113, 113, 0.12); "
                "border: 1px solid rgba(248, 113, 113, 0.35); border-radius: 6px; "
                "padding: 4px 10px; font-weight: 600; font-size: 12px;"
            )



    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_dialog_theme()

    def _apply_dialog_theme(self) -> None:
        """Apply native DWM dark titlebar (#0B0E17) matching the table dialog."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes as wintypes

            hwnd = wintypes.HWND(int(self.winId()))
            DWMWA_USE_IMMERSIVE_DARK_MODE_1 = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_2 = 19
            dark_val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_1, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_2, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
            )
            DWMWA_CAPTION_COLOR = 35
            caption_color = ctypes.c_int(0x00170E0B)  # #0B0E17
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption_color), ctypes.sizeof(caption_color)
            )
            DWMWA_TEXT_COLOR = 36
            text_color = ctypes.c_int(0x00E1D5CB)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text_color), ctypes.sizeof(text_color)
            )
        except Exception:
            pass



    def save_settings(self) -> None:
        self.settings.setValue("api_url", self.api_url_input.text().strip())
        self.settings.setValue("api_token", self.api_token_input.text().strip())
        self.settings.setValue("description", self.description_input.text().strip())
        self.settings.setValue("comment", self.comment_input.text().strip())
        self.settings.setValue("region", self.region_input.text().strip() or "Default")
        self.settings.setValue("custom_tags", self.tags_input.text().strip())
        self.settings.setValue("custom_pools", self.pools_input.text().strip())
        self.settings.setValue("poll_interval", self.poll_interval_input.value())
        self.settings.setValue("after_task", self.after_task_combo.currentData())
        self.settings.setValue("auto_start", self.auto_start_check.isChecked())
        self.settings.setValue("start_minimized", self.start_minimized_check.isChecked())

        self.accept()


