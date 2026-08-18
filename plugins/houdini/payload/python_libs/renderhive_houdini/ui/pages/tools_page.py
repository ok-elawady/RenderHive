"""Compact backend connection, activity log and maintenance menu."""

from __future__ import absolute_import

import datetime

from renderhive_houdini.ui.qt_compat import QtWidgets, Signal
from renderhive_houdini.ui.widgets import PageHeader, SectionCard, apply_status_appearance
from renderhive_houdini.version import __version__


def _instant_popup_mode():
    mode = getattr(QtWidgets.QToolButton, "InstantPopup", None)
    if mode is not None:
        return mode
    return QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup


class ToolsPage(QtWidgets.QWidget):
    """Maya-parity tools page: backend state, activity, and a compact overflow menu."""

    retryConnectionRequested = Signal()
    openRuntimeLogsRequested = Signal()
    createSupportBundleRequested = Signal()
    runProductionCheckRequested = Signal()
    resetSceneStateRequested = Signal()
    uninstallRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(
            PageHeader(
                "Tools",
                "Backend connection, activity and RenderHive maintenance.",
            )
        )

        connection = SectionCard(
            "Connection",
            "RenderHive connects automatically using the managed studio configuration.",
        )
        connection_row = QtWidgets.QHBoxLayout()
        connection_row.setSpacing(10)

        self.connection_state = QtWidgets.QLabel("Checking RenderHive connection…")
        self.connection_state.setObjectName("ConnectionState")
        self.connection_state.setWordWrap(True)
        connection_row.addWidget(self.connection_state, 1)

        self.retry_button = QtWidgets.QPushButton("Retry Connection")
        self.retry_button.setObjectName("InfoButton")
        self.retry_button.clicked.connect(self.retryConnectionRequested.emit)
        connection_row.addWidget(self.retry_button)
        connection.layout.addLayout(connection_row)

        self.config_source = QtWidgets.QLabel("Managed configuration")
        self.config_source.setObjectName("MutedText")
        connection.layout.addWidget(self.config_source)
        root.addWidget(connection)

        activity = SectionCard(
            "Activity Log",
            "Recent RenderHive actions and operational messages.",
        )
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setObjectName("ActivityLog")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMinimumHeight(280)
        activity.layout.addWidget(self.log, 1)
        root.addWidget(activity, 1)

        maintenance_row = QtWidgets.QHBoxLayout()
        maintenance_row.setContentsMargins(0, 0, 0, 0)
        maintenance_row.addStretch()

        self.maintenance_button = QtWidgets.QToolButton()
        self.maintenance_button.setObjectName("MaintenanceButton")
        self.maintenance_button.setText("•••")
        self.maintenance_button.setToolTip("RenderHive tools and maintenance")
        self.maintenance_button.setPopupMode(_instant_popup_mode())

        menu = QtWidgets.QMenu(self.maintenance_button)

        runtime_logs_action = menu.addAction("Open Runtime Logs")
        runtime_logs_action.triggered.connect(self.openRuntimeLogsRequested.emit)

        diagnostics_action = menu.addAction("Create Support Bundle")
        diagnostics_action.triggered.connect(self.createSupportBundleRequested.emit)

        health_action = menu.addAction("Run Production Check")
        health_action.triggered.connect(self.runProductionCheckRequested.emit)

        reset_action = menu.addAction("Reset Current Scene Settings")
        reset_action.triggered.connect(self.resetSceneStateRequested.emit)

        menu.addSeparator()

        uninstall_action = menu.addAction("Uninstall RenderHive…")
        uninstall_action.triggered.connect(self.uninstallRequested.emit)

        self.maintenance_button.setMenu(menu)
        maintenance_row.addWidget(self.maintenance_button)
        root.addLayout(maintenance_row)
        root.addStretch()

        self.append_activity("RenderHive Houdini v{} loaded.".format(__version__))

    def set_connection_config(self, source, token_available):
        source_text = str(source or "").strip()
        if not source_text or source_text.lower() == "unavailable":
            display = "Configuration unavailable"
        elif "managed" in source_text.lower():
            display = "Managed configuration"
        else:
            display = "Managed configuration"
        if not token_available:
            display += " · Authentication unavailable"
        self.config_source.setText(display)

    def set_connecting(self):
        self.retry_button.setEnabled(False)
        self.retry_button.setText("Connecting…")
        self.connection_state.setText("Connecting to RenderHive…")
        self.connection_state.setToolTip("")
        apply_status_appearance(self.connection_state, "info")

    def set_connected(self, checked_at):
        self.retry_button.setEnabled(True)
        self.retry_button.setText("Retry Connection")
        text = "Connected to RenderHive backend."
        if checked_at:
            text += " Last checked {}.".format(checked_at)
        self.connection_state.setText(text)
        self.connection_state.setToolTip("")
        apply_status_appearance(self.connection_state, "good")

    def set_connection_error(self, message, checked_at):
        self.retry_button.setEnabled(True)
        self.retry_button.setText("Retry Connection")
        detail = str(message or "Backend connection failed.").strip()
        text = "Backend unavailable."
        if checked_at:
            text += " Last checked {}.".format(checked_at)
        self.connection_state.setText(text)
        self.connection_state.setToolTip(detail)
        apply_status_appearance(self.connection_state, "error")

    def append_activity(self, message):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText("{}  {}".format(stamp, message))
