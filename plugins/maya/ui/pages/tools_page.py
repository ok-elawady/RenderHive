"""Tools, activity log and runtime telemetry view for RenderHive Maya Submitter."""

from __future__ import print_function

from ..qt_compat import QtCore, QtWidgets
from ..common_widgets import Card
from ..icons import get_icon
from ..qt_theme import COLORS


def build_more_page(self, register):
    page, body = self.scroll_page(
        "Tools & Activity Logs",
        "Real-time submission telemetry, validation logs, and network dispatch events.",
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

    clear_log_btn = QtWidgets.QPushButton("  Clear")
    clear_log_btn.setObjectName("GhostBtn")
    clear_log_btn.setIcon(get_icon("x", COLORS["muted"], 12))
    clear_log_btn.setFixedHeight(28)
    clear_log_btn.setCursor(QtCore.Qt.PointingHandCursor)

    log_tb_layout.addWidget(copy_log_btn)
    log_tb_layout.addWidget(clear_log_btn)

    activity = Card(
        "Activity Log",
        "Live streaming log events from Maya submitter, scene validator, and farm dispatcher.",
        action_widget=log_toolbar,
    )

    activity_log = register(
        "activity_log",
        QtWidgets.QPlainTextEdit(),
    )
    activity_log.setObjectName("ActivityLog")
    activity_log.setReadOnly(True)
    activity_log.setMaximumBlockCount(500)
    activity_log.setMinimumHeight(380)
    activity.layout.addWidget(activity_log, 1)

    def _copy_activity_log():
        text = activity_log.toPlainText()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                self.append_activity("Activity log copied to clipboard.")

    def _clear_activity_log():
        activity_log.clear()
        self.append_activity("Activity log cleared.")

    copy_log_btn.clicked.connect(_copy_activity_log)
    clear_log_btn.clicked.connect(_clear_activity_log)

    body.addWidget(activity, 1)

    # ── Quick Utility Bar ──
    utility_row = QtWidgets.QHBoxLayout()
    utility_row.setSpacing(8)

    open_logs_btn = QtWidgets.QPushButton("  Open Full Runtime Log File")
    open_logs_btn.setObjectName("SecondaryBtn")
    open_logs_btn.setIcon(get_icon("terminal", "#CBD5E1", 13))
    open_logs_btn.setFixedHeight(30)
    open_logs_btn.setCursor(QtCore.Qt.PointingHandCursor)
    if hasattr(self, "open_runtime_logs_folder"):
        open_logs_btn.clicked.connect(self.open_runtime_logs_folder)

    local_test_btn = QtWidgets.QPushButton("  Local Test Render")
    local_test_btn.setObjectName("SecondaryBtn")
    local_test_btn.setIcon(get_icon("cube", "#CBD5E1", 13))
    local_test_btn.setFixedHeight(30)
    local_test_btn.setCursor(QtCore.Qt.PointingHandCursor)
    if hasattr(self, "open_local_render_dialog"):
        local_test_btn.clicked.connect(self.open_local_render_dialog)

    utility_row.addWidget(open_logs_btn)
    utility_row.addWidget(local_test_btn)
    utility_row.addStretch()

    body.addLayout(utility_row)

    return page
