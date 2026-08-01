"""Backend connection, compatibility and activity page."""

from __future__ import absolute_import

import datetime

from renderhive_houdini.ui.qt_compat import QtWidgets, Signal
from renderhive_houdini.ui.widgets import (
    PageHeader,
    SectionCard,
    ReadOnlyRow,
    InlineStatus,
)
from renderhive_houdini.version import __version__
from renderhive_houdini.core.houdini_compat import (
    application_version_string,
    python_version_string,
    user_pref_dir,
)
from renderhive_houdini.ui.qt_compat import binding_name, qt_major_version


class ToolsPage(QtWidgets.QWidget):
    retryConnectionRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(PageHeader(
            "Tools",
            "Backend status, compatibility information and recent RenderHive activity.",
        ))

        connection = SectionCard(
            "Backend Connection",
            "Connection settings are managed outside the artist interface.",
        )
        connection_grid = QtWidgets.QGridLayout()
        connection_grid.setHorizontalSpacing(10)
        connection_grid.setVerticalSpacing(8)
        self.connection_state = ReadOnlyRow("Status", "Not Checked")
        self.config_source = ReadOnlyRow("Configuration", "Loading…")
        self.auth_state = ReadOnlyRow("Authentication", "Loading…")
        self.last_check = ReadOnlyRow("Last Check", "Never")
        connection_grid.addWidget(self.connection_state, 0, 0)
        connection_grid.addWidget(self.config_source, 0, 1)
        connection_grid.addWidget(self.auth_state, 1, 0)
        connection_grid.addWidget(self.last_check, 1, 1)
        connection_grid.setColumnStretch(0, 1)
        connection_grid.setColumnStretch(1, 1)
        connection.layout.addLayout(connection_grid)
        self.connection_message = InlineStatus(
            "RenderHive will test the managed backend automatically.",
            "neutral",
        )
        connection.layout.addWidget(self.connection_message)
        connection_actions = QtWidgets.QHBoxLayout()
        self.retry_button = QtWidgets.QPushButton("Retry Connection")
        self.retry_button.setObjectName("PrimaryButton")
        self.retry_button.clicked.connect(self.retryConnectionRequested.emit)
        connection_actions.addWidget(self.retry_button)
        connection_actions.addStretch()
        connection.layout.addLayout(connection_actions)

        compatibility = SectionCard("Compatibility Status")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        values = [
            ("Plugin Version", __version__),
            ("Houdini Version", application_version_string()),
            ("Python Version", python_version_string()),
            ("Qt Binding", "{} / Qt {}".format(binding_name(), qt_major_version())),
            ("User Preferences", user_pref_dir() or "Unavailable"),
            ("Integration", "Menu, Shelf and Python Panel"),
        ]
        for index, (name, value) in enumerate(values):
            grid.addWidget(ReadOnlyRow(name, value), index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        compatibility.layout.addLayout(grid)

        activity = SectionCard("Activity Log")
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        activity.layout.addWidget(self.log, 1)

        root.addWidget(connection)
        root.addWidget(compatibility)
        root.addWidget(activity, 1)
        self.append_activity("RenderHive Houdini v{} loaded.".format(__version__))
        self.append_activity("Scene and project values are synchronized automatically.")

    def set_connection_config(self, source, token_available):
        self.config_source.set_value(source or "Built-in Default")
        self.auth_state.set_value("Configured" if token_available else "Token Missing")

    def set_connecting(self):
        self.retry_button.setEnabled(False)
        self.retry_button.setText("Connecting…")
        self.connection_state.set_value("Connecting")
        self.connection_message.setText("Testing the RenderHive backend and loading farm data.")
        self.connection_message.set_level("info")

    def set_connected(self, checked_at):
        self.retry_button.setEnabled(True)
        self.retry_button.setText("Retry Connection")
        self.connection_state.set_value("Connected")
        self.last_check.set_value(checked_at or "Now")
        self.connection_message.setText("Backend connection is ready.")
        self.connection_message.set_level("good")

    def set_connection_error(self, message, checked_at):
        self.retry_button.setEnabled(True)
        self.retry_button.setText("Retry Connection")
        self.connection_state.set_value("Unavailable")
        self.last_check.set_value(checked_at or "Now")
        self.connection_message.setText(str(message or "Backend connection failed."))
        self.connection_message.set_level("error")

    def append_activity(self, message):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText("{}  {}".format(stamp, message))
