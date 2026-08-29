"""Tools, activity log and runtime telemetry view for RenderHive Houdini Submitter."""

from __future__ import absolute_import

import datetime

from renderhive_houdini.ui.qt_compat import QtCore, QtWidgets, Signal
from renderhive_houdini.ui.widgets import PageHeader, SectionCard
from renderhive_houdini.ui.icons import get_icon
from renderhive_houdini.ui.theme import COLORS
from renderhive_houdini.version import __version__


class ToolsPage(QtWidgets.QWidget):
    """Maya-parity activity logs and runtime telemetry page."""

    openRuntimeLogsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)
        root.addWidget(
            PageHeader(
                "Tools & Activity Logs",
                "Real-time submission telemetry, validation logs, and network dispatch events.",
            )
        )

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
        self.log.setMinimumHeight(380)
        activity.layout.addWidget(self.log, 1)
        root.addWidget(activity, 1)

        # ── Quick Utility Bar ──
        utility_row = QtWidgets.QHBoxLayout()
        utility_row.setSpacing(8)

        open_logs_btn = QtWidgets.QPushButton("  Open Full Runtime Log File")
        open_logs_btn.setObjectName("SecondaryBtn")
        open_logs_btn.setIcon(get_icon("terminal", "#CBD5E1", 13))
        open_logs_btn.setFixedHeight(32)
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
        pass

    def set_connecting(self):
        pass

    def set_connected(self, checked_at):
        pass

    def set_connection_error(self, message, checked_at):
        pass

    def append_activity(self, message):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText("{}  {}".format(stamp, message))
