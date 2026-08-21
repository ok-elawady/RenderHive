"""Scene validation results and auto-repair view for RenderHive Maya Submitter."""

from __future__ import print_function

from ..qt_compat import QtCore, QtWidgets
from ..common_widgets import Card, LabeledField, PageHeader, ScrollFilter
from ..icons import get_icon
from ..qt_theme import COLORS


def get_counter_card_qss(color, rgb, count=0):
    """Generate clean uniform 4-sided styling with matching category selection border."""
    if count > 0:
        idle_bg = "rgba({}, 0.08)".format(rgb)
        idle_border = "rgba({}, 0.38)".format(rgb)
        idle_color = color
        font_weight = "700"
    else:
        idle_bg = COLORS["surface2"]
        idle_border = COLORS["border_card"]
        idle_color = COLORS["muted"]
        font_weight = "600"

    return (
        "QPushButton#CounterCard {"
        "background-color: " + idle_bg + ";"
        "border: 1px solid " + idle_border + ";"
        "border-radius: 6px;"
        "color: " + idle_color + ";"
        "padding: 6px 8px;"
        "margin: 0px;"
        "font-size: 11px;"
        "font-weight: " + font_weight + ";"
        "text-align: center;"
        "min-height: 44px;"
        "max-height: 44px;"
        "}"
        "QPushButton#CounterCard:hover {"
        "background-color: rgba(" + rgb + ", 0.14);"
        "border: 1px solid " + color + ";"
        "color: #FFFFFF;"
        "}"
        "QPushButton#CounterCard:checked {"
        "background-color: rgba(" + rgb + ", 0.22);"
        "border: 2px solid " + color + ";"
        "color: #FFFFFF;"
        "font-weight: 700;"
        "}"
    )


def build_checks_page(self, register):
    # Header action button on top right of the Page Title
    rescan_btn = QtWidgets.QPushButton("  Re-scan Scene")
    rescan_btn.setObjectName("SecondaryBtn")
    rescan_btn.setIcon(get_icon("shield-check", "#CBD5E1", 13))
    rescan_btn.setFixedHeight(30)
    rescan_btn.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    rescan_btn.setCursor(QtCore.Qt.PointingHandCursor)
    rescan_btn.clicked.connect(self.validate_scene)

    page, body = self.scroll_page(
        "Scene Validation",
        "Errors block submission; warnings remain visible for review.",
        action_widget=rescan_btn,
    )

    # ── 1. Top Severity Counter Tabs ──
    counters = QtWidgets.QHBoxLayout()
    counters.setContentsMargins(0, 0, 0, 0)
    counters.setSpacing(6)
    counters.setAlignment(QtCore.Qt.AlignTop)

    counter_group = QtWidgets.QButtonGroup(self)
    counter_group.setExclusive(True)
    self._validation_counter_buttons = {}

    counter_specs = [
        ("counter_error", "ERRORS", "ERROR", COLORS["error"], "248, 113, 113"),
        ("counter_warning", "WARNINGS", "WARNING", COLORS["warning"], "251, 191, 36"),
        ("counter_info", "INFO", "INFO", COLORS["info"], "77, 163, 255"),
        ("counter_passed", "PASSED", "PASSED", COLORS["success"], "74, 222, 128"),
        ("counter_total", "ALL CHECKS", "All", COLORS["primary"], "156, 115, 242"),
    ]

    for name, title, filter_value, color, rgb in counter_specs:
        button = register(name, QtWidgets.QPushButton("{}\n0".format(title)))
        button.setObjectName("CounterCard")
        button.setCheckable(True)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setStyleSheet(get_counter_card_qss(color, rgb, count=0))
        button.clicked.connect(
            lambda checked=False, value=filter_value: self.set_severity_filter(value)
        )
        counter_group.addButton(button)
        self._validation_counter_buttons[filter_value] = button
        if filter_value == "All":
            button.setChecked(True)
        counters.addWidget(button, 1)

    body.addLayout(counters)

    # Hidden severity combo to preserve 100% backend controller compatibility & test contracts
    severity = register("severity_filter", QtWidgets.QComboBox())
    severity.setVisible(False)
    severity.addItems(["All", "ERROR", "WARNING", "INFO", "PASSED"])
    severity.currentIndexChanged.connect(self.api.refresh_validation_filters)
    severity.currentIndexChanged.connect(
        lambda: [
            b.setChecked(True)
            for k, b in getattr(self, "_validation_counter_buttons", {}).items()
            if k == severity.currentText() and not b.isChecked()
        ]
    )

    # ── 2. Results Card with Integrated Category Header Filter ──
    category = register("category_filter", QtWidgets.QComboBox())
    category.addItem("All")
    category.setMinimumWidth(150)
    category.setFixedHeight(28)
    ScrollFilter.install(category)
    category.currentIndexChanged.connect(self.api.refresh_validation_filters)

    category_container = QtWidgets.QWidget()
    cat_layout = QtWidgets.QHBoxLayout(category_container)
    cat_layout.setContentsMargins(0, 0, 0, 0)
    cat_layout.setSpacing(6)
    cat_lbl = QtWidgets.QLabel("Category:")
    cat_lbl.setObjectName("MutedText")
    cat_layout.addWidget(cat_lbl)
    cat_layout.addWidget(category)

    results_card = Card(
        "Validation Results",
        "Inspected scene nodes, shaders, cameras and output settings.",
        action_widget=category_container,
    )

    tree = register("validation_tree", QtWidgets.QTreeWidget())
    tree.setColumnCount(4)
    tree.setHeaderLabels(["Status", "Category", "Message", "Node"])
    tree.setRootIsDecorated(False)
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    tree.setUniformRowHeights(True)
    tree.setMinimumHeight(240)
    tree.header().setStretchLastSection(False)
    tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
    tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
    tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
    tree.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
    tree.itemSelectionChanged.connect(self.show_validation_details)
    tree.itemDoubleClicked.connect(lambda *_: self.api.select_validation_node())
    results_card.layout.addWidget(tree, 1)

    # ── 3. Embedded Inspector Drawer ──
    details = register("validation_details_card", QtWidgets.QFrame())
    details.setObjectName("DetailsCard")
    details_layout = QtWidgets.QVBoxLayout(details)
    details_layout.setContentsMargins(14, 10, 14, 10)
    details_layout.setSpacing(4)

    details_top = QtWidgets.QHBoxLayout()
    details_title = QtWidgets.QLabel("Selected Issue Details")
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

    results_card.layout.addWidget(details)
    details.setVisible(False)

    body.addWidget(results_card, 1)

    # ── 4. Unified Action Bar ──
    action_bar = QtWidgets.QHBoxLayout()
    action_bar.setSpacing(8)

    select_node = QtWidgets.QPushButton("  Select Node")
    select_node.setObjectName("SecondaryBtn")
    select_node.setIcon(get_icon("search", "#CBD5E1", 13))
    select_node.clicked.connect(self.api.select_validation_node)

    export = QtWidgets.QPushButton("  Export Report")
    export.setObjectName("SecondaryBtn")
    export.setIcon(get_icon("copy", "#CBD5E1", 13))
    export.clicked.connect(self.api.export_validation_report)

    clear = QtWidgets.QPushButton("  Clear")
    clear.setObjectName("GhostBtn")
    clear.setIcon(get_icon("x", COLORS["muted"], 13))
    clear.clicked.connect(self.api.clear_validation_results)

    action_bar.addWidget(select_node)
    action_bar.addWidget(export)
    action_bar.addWidget(clear)
    action_bar.addStretch()

    fix_selected = register(
        "fix_selected_validation",
        QtWidgets.QPushButton("  Fix Selected"),
    )
    fix_selected.setObjectName("SecondaryBtn")
    fix_selected.setIcon(get_icon("wrench", "#CBD5E1", 13))
    fix_selected.clicked.connect(self.fix_selected_validation)

    fix_all = register(
        "fix_all_safe_validation",
        QtWidgets.QPushButton("  Fix All Safe Issues"),
    )
    fix_all.setObjectName("PrimaryButton")
    fix_all.setIcon(get_icon("zap", COLORS["primary_fg"], 13))
    fix_all.clicked.connect(self.fix_all_safe_validations)

    action_bar.addWidget(fix_selected)
    action_bar.addWidget(fix_all)
    body.addLayout(action_bar)

    self.update_autofix_actions()

    return page
