from __future__ import print_function

from ..qt_compat import QtWidgets
from ..common_widgets import Card, LabeledField, PageHeader

def build_checks_page(self, register):
    page = QtWidgets.QWidget()
    body = QtWidgets.QVBoxLayout(page)
    body.setContentsMargins(2, 2, 5, 2)
    body.setSpacing(9)

    body.addWidget(
        PageHeader(
            "Scene Validation",
            "Errors block submission; warnings remain visible for review.",
        )
    )

    counters = QtWidgets.QHBoxLayout()
    counters.setSpacing(6)

    counter_specs = [
        ("counter_error", "ERRORS", "ERROR"),
        ("counter_warning", "WARNINGS", "WARNING"),
        ("counter_info", "INFO", "INFO"),
        ("counter_passed", "PASSED", "PASSED"),
        ("counter_total", "TOTAL", "All"),
    ]

    for name, title, filter_value in counter_specs:
        button = register(name, QtWidgets.QPushButton("{}\n0".format(title)))
        button.setObjectName("CounterCard")
        button.clicked.connect(
            lambda checked=False, value=filter_value: self.set_severity_filter(value)
        )
        counters.addWidget(button, 1)

    body.addLayout(counters)

    filter_card = Card("Filter Results")
    filter_row = QtWidgets.QHBoxLayout()

    severity = register("severity_filter", QtWidgets.QComboBox())
    severity.addItems(["All", "ERROR", "WARNING", "INFO", "PASSED"])

    category = register("category_filter", QtWidgets.QComboBox())
    category.addItem("All")

    severity.currentIndexChanged.connect(self.api.refresh_validation_filters)
    category.currentIndexChanged.connect(self.api.refresh_validation_filters)

    filter_row.addWidget(LabeledField("Severity", severity), 1)
    filter_row.addWidget(LabeledField("Category", category), 1)
    filter_card.layout.addLayout(filter_row)
    body.addWidget(filter_card)

    results_card = Card("Results")
    tree = register("validation_tree", QtWidgets.QTreeWidget())
    tree.setColumnCount(4)
    tree.setHeaderLabels(["Status", "Category", "Message", "Node"])
    tree.setRootIsDecorated(False)
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    tree.setUniformRowHeights(True)
    tree.setMinimumHeight(205)
    tree.header().setStretchLastSection(False)
    tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
    tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
    tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
    tree.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
    tree.itemSelectionChanged.connect(self.show_validation_details)
    tree.itemDoubleClicked.connect(lambda *_: self.api.select_validation_node())
    results_card.layout.addWidget(tree)
    body.addWidget(results_card, 1)

    details = register("validation_details_card", QtWidgets.QFrame())
    details.setObjectName("DetailsCard")
    details_layout = QtWidgets.QVBoxLayout(details)
    details_layout.setContentsMargins(12, 10, 12, 10)
    details_layout.setSpacing(4)

    details_top = QtWidgets.QHBoxLayout()
    details_title = QtWidgets.QLabel("Result Details")
    details_title.setObjectName("SectionTitle")
    details_top.addWidget(details_title)
    details_top.addStretch()

    details_badge = register("details_badge", QtWidgets.QLabel("NONE"))
    details_badge.setObjectName("MetaChip")
    details_top.addWidget(details_badge)
    details_layout.addLayout(details_top)

    details_message = register("details_message", QtWidgets.QLabel("Select a result to view its details."))
    details_message.setObjectName("SecondaryText")
    details_message.setWordWrap(True)
    details_layout.addWidget(details_message)

    details_meta = register("details_meta", QtWidgets.QLabel(""))
    details_meta.setObjectName("MutedText")
    details_meta.setWordWrap(True)
    details_layout.addWidget(details_meta)
    body.addWidget(details)
    details.setVisible(False)

    fix_row = QtWidgets.QHBoxLayout()
    fix_row.setSpacing(7)

    validate = QtWidgets.QPushButton("Validate Scene")
    validate.setObjectName("PrimaryButton")
    validate.clicked.connect(self.validate_scene)

    fix_selected = register(
        "fix_selected_validation",
        QtWidgets.QPushButton("Fix Selected"),
    )
    fix_selected.setObjectName("InfoButton")
    fix_selected.clicked.connect(
        self.fix_selected_validation
    )

    fix_all = register(
        "fix_all_safe_validation",
        QtWidgets.QPushButton("Fix All Safe Issues"),
    )
    fix_all.setObjectName("PrimaryButton")
    fix_all.clicked.connect(
        self.fix_all_safe_validations
    )

    fix_row.addWidget(validate)
    fix_row.addWidget(fix_selected)
    fix_row.addWidget(fix_all)
    body.addLayout(fix_row)

    utility_row = QtWidgets.QHBoxLayout()
    utility_row.setSpacing(7)

    select_node = QtWidgets.QPushButton("Select Node")
    select_node.clicked.connect(
        self.api.select_validation_node
    )

    export = QtWidgets.QPushButton("Export Report")
    export.clicked.connect(
        self.api.export_validation_report
    )

    clear = QtWidgets.QPushButton("Clear")
    clear.setObjectName("GhostButton")
    clear.clicked.connect(
        self.api.clear_validation_results
    )

    utility_row.addWidget(select_node)
    utility_row.addWidget(export)
    utility_row.addStretch()
    utility_row.addWidget(clear)
    body.addLayout(utility_row)

    self.update_autofix_actions()

    return page

