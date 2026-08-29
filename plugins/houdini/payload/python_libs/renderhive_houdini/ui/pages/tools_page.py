"""Tools, activity log and runtime telemetry view for RenderHive Houdini Submitter."""

from __future__ import absolute_import

import datetime

from renderhive_houdini.ui.qt_compat import QtCore, QtWidgets, Signal
from renderhive_houdini.ui.widgets import PageHeader, SectionCard, StatusChip
from renderhive_houdini.ui.icons import get_icon
from renderhive_houdini.ui.theme import COLORS
from renderhive_houdini.version import __version__


class ToolsPage(QtWidgets.QWidget):
    """Activity logs and runtime telemetry page."""

    openRuntimeLogsRequested = Signal()
    createSupportBundleRequested = Signal()
    runProductionCheckRequested = Signal()
    resetSceneStateRequested = Signal()
    uninstallRequested = Signal()
    retryConnectionRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)
        root.addWidget(
            PageHeader(
                "Tools & Activity Logs",
                "Real-time submission telemetry, validation logs, and network dispatch events.",
            )
        )

        # ── Connection Status Card with Maintenance Menu ──
        maintenance_btn = QtWidgets.QToolButton()
        maintenance_btn.setObjectName("MaintenanceButton")
        maintenance_btn.setText("•••")
        maintenance_btn.setToolTip("Maintenance & diagnostics actions")
        maintenance_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        maintenance_btn.setCursor(QtCore.Qt.PointingHandCursor)

        menu = QtWidgets.QMenu(maintenance_btn)
        act_logs = menu.addAction("Open Runtime Logs")
        act_logs.triggered.connect(self.openRuntimeLogsRequested.emit)
        act_bundle = menu.addAction("Create Support Bundle")
        act_bundle.triggered.connect(self.createSupportBundleRequested.emit)
        act_check = menu.addAction("Run Production Check")
        act_check.triggered.connect(self.runProductionCheckRequested.emit)
        menu.addSeparator()
        act_reset = menu.addAction("Reset Current Scene Settings")
        act_reset.triggered.connect(self.resetSceneStateRequested.emit)
        menu.addSeparator()
        act_uninstall = menu.addAction("Uninstall RenderHive…")
        act_uninstall.triggered.connect(self.uninstallRequested.emit)
        maintenance_btn.setMenu(menu)

        conn_card = SectionCard(
            "Connection",
            "Active RenderHive API connection and farm dispatcher status.",
            action_widget=maintenance_btn,
        )

        conn_row = QtWidgets.QHBoxLayout()
        conn_row.setContentsMargins(0, 0, 0, 0)
        conn_row.setSpacing(8)

        self.connection_state = QtWidgets.QLabel("Checking connection…")
        self.connection_state.setObjectName("MutedLabel")
        self.connection_state.setStyleSheet("font-size: 12px; color: #CBD5E1;")

        retry_btn = QtWidgets.QPushButton("Retry Connection")
        retry_btn.setObjectName("SecondaryBtn")
        retry_btn.setIcon(get_icon("refresh", COLORS["secondary"], 12))
        retry_btn.setFixedHeight(28)
        retry_btn.setCursor(QtCore.Qt.PointingHandCursor)
        retry_btn.clicked.connect(self.retryConnectionRequested.emit)

        conn_row.addWidget(self.connection_state, 1)
        conn_row.addWidget(retry_btn)
        conn_card.add_layout(conn_row)
        root.addWidget(conn_card)

        # ── Real-time Activity Log Card with Toolbar ──
        log_toolbar = QtWidgets.QWidget()
        log_tb_layout = QtWidgets.QHBoxLayout(log_toolbar)
        log_tb_layout.setContentsMargins(0, 0, 0, 0)
        log_tb_layout.setSpacing(6)

        copy_log_btn = QtWidgets.QPushButton("  Copy Log")
        copy_log_btn.setObjectName("SecondaryBtn")
        copy_log_btn.setIcon(get_icon("copy", "#CBD5E1", 12))
        copy_log_btn.setFixedHeight(28)
        copy_log_btn.setCursor(QtCore.Qt.PointingHandCursor)
        copy_log_btn.clicked.connect(self._copy_log)

        clear_log_btn = QtWidgets.QPushButton("  Clear")
        clear_log_btn.setObjectName("GhostBtn")
        clear_log_btn.setIcon(get_icon("x", COLORS["muted"], 12))
        clear_log_btn.setFixedHeight(28)
        clear_log_btn.setCursor(QtCore.Qt.PointingHandCursor)
        clear_log_btn.clicked.connect(self._clear_log)

        log_tb_layout.addWidget(copy_log_btn)
        log_tb_layout.addWidget(clear_log_btn)

        activity = SectionCard(
            "Activity Log",
            "Live streaming log events from Houdini submitter, scene validator, and farm dispatcher.",
            action_widget=log_toolbar,
        )
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setObjectName("ActivityLog")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMinimumHeight(320)
        activity.layout.addWidget(self.log, 1)
        root.addWidget(activity, 1)

        # ── Quick Utility Bar ──
        utility_row = QtWidgets.QHBoxLayout()
        utility_row.setSpacing(8)

        open_logs_btn = QtWidgets.QPushButton("  Open Full Runtime Log File")
        open_logs_btn.setObjectName("SecondaryBtn")
        open_logs_btn.setIcon(get_icon("terminal", "#CBD5E1", 13))
        open_logs_btn.setFixedHeight(30)
        open_logs_btn.setCursor(QtCore.Qt.PointingHandCursor)
        open_logs_btn.clicked.connect(self.openRuntimeLogsRequested.emit)
        utility_row.addWidget(open_logs_btn)
        utility_row.addStretch()

        root.addLayout(utility_row)

        self.append_activity("RenderHive Houdini v{} loaded.".format(__version__))

    def _copy_log(self):
        text = self.log.toPlainText()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                self.append_activity("Activity log copied to clipboard.")

    def _clear_log(self):
        self.log.clear()
        self.append_activity("Activity log cleared.")

    def set_connection_config(self, source, token_available):
        text = "Config source: {}".format(source or "Default")
        if not token_available:
            text += " (No API token)"
        self.connection_state.setText(text)

    def set_connecting(self):
        self.connection_state.setText("Connecting to RenderHive backend…")

    def set_connected(self, checked_at):
        stamp = checked_at.strftime("%H:%M:%S") if hasattr(checked_at, "strftime") else str(checked_at or "")
        self.connection_state.setText("Connected to backend at {}".format(stamp))

    def set_connection_error(self, message, checked_at):
        detail = str(message or "")
        text = "Backend unavailable."
        if checked_at:
            stamp = checked_at.strftime("%H:%M:%S") if hasattr(checked_at, "strftime") else str(checked_at)
            text += " (Last checked {})".format(stamp)
        self.connection_state.setText(text)
        self.connection_state.setToolTip(detail)

    def append_activity(self, message):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText("{}  {}".format(stamp, message))
