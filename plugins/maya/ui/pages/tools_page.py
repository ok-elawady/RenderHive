from __future__ import print_function

from ..qt_compat import QtWidgets
from ..common_widgets import Card

def build_more_page(self, register):
    page, body = self.scroll_page(
        "Tools",
        "Connection status, activity and plugin maintenance.",
    )

    connection_card = Card(
        "Connection",
        "RenderHive connects automatically using the managed studio configuration.",
    )

    connection_row = QtWidgets.QHBoxLayout()
    connection_row.setSpacing(10)

    backend_status = register(
        "api_connection_status",
        QtWidgets.QLabel("Checking RenderHive connection…"),
    )
    backend_status.setObjectName("ConnectionState")
    backend_status.setWordWrap(True)
    connection_row.addWidget(backend_status, 1)

    test_button = register(
        "test_api_button",
        QtWidgets.QPushButton("Retry Connection"),
    )
    test_button.setObjectName("InfoButton")
    test_button.clicked.connect(self.test_api_connection)
    connection_row.addWidget(test_button)

    connection_card.layout.addLayout(connection_row)

    source_label = register(
        "api_config_source",
        QtWidgets.QLabel("Managed configuration"),
    )
    source_label.setObjectName("MutedText")
    connection_card.layout.addWidget(source_label)

    if bool(getattr(self.api, "api_admin_mode_enabled", lambda: False)()):
        admin_row = QtWidgets.QHBoxLayout()
        admin_row.setSpacing(7)

        open_button = QtWidgets.QPushButton(
            "Open Managed Configuration"
        )
        open_button.setObjectName("GhostButton")
        open_button.clicked.connect(self.open_api_config)
        admin_row.addWidget(open_button)
        admin_row.addStretch()
        connection_card.layout.addLayout(admin_row)

    body.addWidget(connection_card)

    activity = Card(
        "Activity Log",
        "Recent RenderHive actions and operational messages.",
    )

    activity_log = register(
        "activity_log",
        QtWidgets.QPlainTextEdit(),
    )
    activity_log.setObjectName("ActivityLog")
    activity_log.setReadOnly(True)
    activity_log.setMaximumBlockCount(250)
    activity_log.setMinimumHeight(260)
    activity.layout.addWidget(activity_log)
    body.addWidget(activity, 1)

    maintenance_row = QtWidgets.QHBoxLayout()
    maintenance_row.addStretch()

    menu_button = QtWidgets.QToolButton()
    menu_button.setObjectName("MaintenanceButton")
    menu_button.setText("•••")
    menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

    menu = QtWidgets.QMenu(menu_button)

    state_folder_action = menu.addAction(
        "Open Restore Data Folder"
    )
    state_folder_action.triggered.connect(
        self.open_state_storage_folder
    )

    runtime_logs_action = menu.addAction(
        "Open Runtime Logs"
    )
    runtime_logs_action.triggered.connect(
        self.open_runtime_logs_folder
    )

    diagnostics_action = menu.addAction(
        "Create Support Bundle"
    )
    diagnostics_action.triggered.connect(
        self.create_support_bundle
    )

    health_action = menu.addAction(
        "Run Production Check"
    )
    health_action.triggered.connect(
        self.run_production_check
    )

    menu.addSeparator()

    uninstall_action = menu.addAction("Uninstall RenderHive…")
    uninstall_action.triggered.connect(
        self.api.uninstall_renderhive_from_maya
    )
    menu_button.setMenu(menu)
    maintenance_row.addWidget(menu_button)

    body.addLayout(maintenance_row)
    body.addStretch()
    return page

