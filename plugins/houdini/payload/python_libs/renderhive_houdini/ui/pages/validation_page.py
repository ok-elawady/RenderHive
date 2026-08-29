"""Production validation, filtering and Auto Fix UI for Houdini."""

from __future__ import absolute_import

from renderhive_houdini.ui.qt_compat import (
    QtWidgets,
    QtGui,
    QtCore,
    Signal,
    USER_ROLE,
    HEADER_STRETCH,
    HEADER_RESIZE_TO_CONTENTS,
)
from renderhive_houdini.ui.icons import get_icon
from renderhive_houdini.ui.widgets import PageHeader, SectionCard, InlineStatus
from renderhive_houdini.ui.theme import COLORS
from renderhive_houdini.validation.validator import validate, summary
from renderhive_houdini.validation.auto_fix import can_fix_result, collect_batch_safe, fix_label


SEVERITY_COLORS = {
    "ERROR": COLORS["error"],
    "WARNING": COLORS["warning"],
    "INFO": COLORS["info"],
    "PASSED": COLORS["success"],
    "TOTAL": COLORS["light"],
}



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
        "outline: none;"
        "}"
        "QPushButton#CounterCard:hover {"
        "background-color: rgba(" + rgb + ", 0.14);"
        "border: 1px solid " + color + ";"
        "color: #FFFFFF;"
        "outline: none;"
        "}"
        "QPushButton#CounterCard:checked {"
        "background-color: rgba(" + rgb + ", 0.22);"
        "border: 2px solid " + color + ";"
        "color: #FFFFFF;"
        "font-weight: 700;"
        "outline: none;"
        "}"
        "QPushButton#CounterCard:focus {"
        "outline: none;"
        "}"
    )


def _severity_color(level):
    return SEVERITY_COLORS.get(str(level or "INFO").upper(), COLORS["muted"])


class ValidationPage(QtWidgets.QWidget):
    autoFixRequested = Signal(object)
    autoFixAllRequested = Signal(object)
    selectNodeRequested = Signal(str)
    exportRequested = Signal(object)
    validationCompleted = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._context = None
        self._node_info = None
        self._render_nodes = []
        self._dependencies = None
        self._farm_context = None
        self._results = []
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)
        rescan_btn = QtWidgets.QPushButton("  Re-scan Scene")
        rescan_btn.setObjectName("SecondaryBtn")
        rescan_btn.setFixedHeight(30)
        rescan_btn.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        rescan_btn.setCursor(QtCore.Qt.PointingHandCursor)
        rescan_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        rescan_btn.clicked.connect(self.run_validation)
        
        root.addWidget(PageHeader("Scene Validation", "Errors block submission. Safe issues can be fixed automatically.", action_widget=rescan_btn))

        # 1. Top Severity Counter Tabs
        counters = QtWidgets.QHBoxLayout()
        counters.setContentsMargins(0, 0, 0, 0)
        counters.setSpacing(6)
        counters.setAlignment(QtCore.Qt.AlignTop)
        
        counter_group = QtWidgets.QButtonGroup(self)
        counter_group.setExclusive(True)
        self.summary_buttons = {}
        
        counter_specs = [
            ("ERROR", "ERRORS", COLORS["error"], "248, 113, 113"),
            ("WARNING", "WARNINGS", COLORS["warning"], "251, 191, 36"),
            ("INFO", "INFO", COLORS["info"], "77, 163, 255"),
            ("PASSED", "PASSED", COLORS["success"], "74, 222, 128"),
            ("TOTAL", "ALL CHECKS", COLORS["primary"], "156, 115, 242"),
        ]
        
        for key, title, color, rgb in counter_specs:
            button = QtWidgets.QPushButton("{}\n0".format(title))
            button.setObjectName("CounterCard")
            button.setCheckable(True)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            button.setStyleSheet(get_counter_card_qss(color, rgb, count=0))
            button.clicked.connect(lambda checked=False, value=key: self._set_severity(value))
            counter_group.addButton(button)
            self.summary_buttons[key] = button
            if key == "TOTAL":
                button.setChecked(True)
            counters.addWidget(button, 1)
            
        root.addLayout(counters)

        self.severity_filter = QtWidgets.QComboBox()
        self.severity_filter.setVisible(False)
        self.severity_filter.addItems(("All", "ERROR", "WARNING", "INFO", "PASSED"))
        self.severity_filter.currentIndexChanged.connect(self.refresh_filters)
        self.severity_filter.currentIndexChanged.connect(
            lambda: [
                b.setChecked(True)
                for k, b in getattr(self, "summary_buttons", {}).items()
                if k == self.severity_filter.currentText() and not b.isChecked()
            ]
        )

        self.category_filter = QtWidgets.QComboBox()
        self.category_filter.addItem("All")
        self.category_filter.setMinimumWidth(150)
        self.category_filter.setFixedHeight(28)
        self.category_filter.currentIndexChanged.connect(self.refresh_filters)

        category_container = QtWidgets.QWidget()
        cat_layout = QtWidgets.QHBoxLayout(category_container)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.setSpacing(6)
        cat_lbl = QtWidgets.QLabel("Category:")
        cat_lbl.setObjectName("MutedText")
        cat_layout.addWidget(cat_lbl)
        cat_layout.addWidget(self.category_filter)

        results_card = SectionCard(
            "Validation Results", 
            "Inspected scene nodes, shaders, cameras and output settings.",
            action_widget=category_container
        )
        
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search message, node, category or code")
        self.search.textChanged.connect(self.refresh_filters)
        self.search.setVisible(False)
        results_card.layout.addWidget(self.search)
        
        self.status = InlineStatus("Validation has not been run.", "neutral")
        results_card.layout.addWidget(self.status)
        self.table = QtWidgets.QTreeWidget()
        self.table.setColumnCount(5)
        self.table.setHeaderLabels(("Status", "Category", "Message", "Node", "Auto Fix"))
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.header().setStretchLastSection(False)
        self.table.header().setSectionResizeMode(0, HEADER_RESIZE_TO_CONTENTS)
        self.table.header().setSectionResizeMode(1, HEADER_RESIZE_TO_CONTENTS)
        self.table.header().setSectionResizeMode(2, HEADER_STRETCH)
        self.table.header().setSectionResizeMode(3, HEADER_STRETCH)
        self.table.header().setSectionResizeMode(4, HEADER_RESIZE_TO_CONTENTS)
        self.table.itemSelectionChanged.connect(self._update_details)
        self.table.itemDoubleClicked.connect(self._select_current_node)
        results_card.layout.addWidget(self.table, 1)

        self.details = QtWidgets.QFrame()
        self.details.setObjectName("DetailsCard")
        details_layout = QtWidgets.QVBoxLayout(self.details)
        details_layout.setContentsMargins(14, 10, 14, 10)
        details_layout.setSpacing(4)
        
        details_top = QtWidgets.QHBoxLayout()
        self.details_title = QtWidgets.QLabel("Selected Issue Details")
        self.details_title.setObjectName("SectionTitle")
        details_top.addWidget(self.details_title)
        details_top.addStretch()
        
        self.details_badge = QtWidgets.QLabel("NONE")
        self.details_badge.setObjectName("MetaChip")
        details_top.addWidget(self.details_badge)
        details_layout.addLayout(details_top)
        
        self.details_message = QtWidgets.QLabel("Select a result to view its details.")
        self.details_message.setObjectName("SecondaryText")
        self.details_message.setWordWrap(True)
        details_layout.addWidget(self.details_message)
        
        self.details_meta = QtWidgets.QLabel("")
        self.details_meta.setObjectName("MutedText")
        self.details_meta.setWordWrap(True)
        details_layout.addWidget(self.details_meta)
        
        self.details.setVisible(False)
        results_card.layout.addWidget(self.details)
        
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        
        self.select_button = QtWidgets.QPushButton("  Select Node")
        self.select_button.setObjectName("SecondaryBtn")
        self.select_button.setIcon(get_icon("search", "#CBD5E1", 13))
        
        self.export_button = QtWidgets.QPushButton("  Export Report")
        self.export_button.setObjectName("SecondaryBtn")
        self.export_button.setIcon(get_icon("copy", "#CBD5E1", 13))
        
        self.clear_button = QtWidgets.QPushButton("  Clear")
        self.clear_button.setObjectName("GhostBtn")
        self.clear_button.setIcon(get_icon("x", COLORS["muted"], 13))
        
        self.select_button.clicked.connect(self._select_current_node)
        self.export_button.clicked.connect(lambda: self.exportRequested.emit(list(self._results)))
        self.clear_button.clicked.connect(self.clear_results)
        
        actions.addWidget(self.select_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.clear_button)
        actions.addStretch()
        
        self.fix_selected_button = QtWidgets.QPushButton("  Fix Selected")
        self.fix_selected_button.setObjectName("SecondaryBtn")
        self.fix_selected_button.setIcon(get_icon("wrench", "#CBD5E1", 13))
        self.fix_selected_button.clicked.connect(self._fix_selected)
        
        self.fix_all_button = QtWidgets.QPushButton("  Fix All Safe Issues")
        self.fix_all_button.setObjectName("PrimaryButton")
        self.fix_all_button.setIcon(get_icon("zap", COLORS["primary_fg"], 13))
        self.fix_all_button.clicked.connect(self._fix_all)
        
        self.validate_button = QtWidgets.QPushButton("  Validate Scene")
        self.validate_button.setObjectName("PrimaryButton")
        self.validate_button.clicked.connect(self.run_validation)
        self.validate_button.hide()
        
        actions.addWidget(self.fix_selected_button)
        actions.addWidget(self.fix_all_button)
        
        root.addWidget(results_card, 1)
        root.addLayout(actions)
        self._update_action_state()

    def set_context(self, context):
        self._context = context

    def set_render_node(self, node_info):
        self._node_info = node_info
        if node_info is not None and not self._render_nodes:
            self._render_nodes = [node_info]

    def set_render_nodes(self, nodes):
        self._render_nodes = list(nodes or [])
        self._node_info = self._render_nodes[0] if self._render_nodes else None

    def set_dependencies(self, dependencies):
        self._dependencies = list(dependencies or [])

    def set_farm_context(self, farm_context):
        self._farm_context = dict(farm_context or {})

    def results(self):
        return list(self._results)

    def selected_result(self):
        item = self.table.currentItem()
        if item is None:
            return None
        value = item.data(0, USER_ROLE)
        return value if value in self._results else value

    def _set_severity(self, value):
        target = "All" if value == "TOTAL" else value
        index = self.severity_filter.findText(target)
        self.severity_filter.setCurrentIndex(index if index >= 0 else 0)

    def _rebuild_categories(self):
        previous = self.category_filter.currentText()
        categories = sorted(set(str(item.category or "General") for item in self._results))
        self.category_filter.blockSignals(True)
        self.category_filter.clear(); self.category_filter.addItem("All"); self.category_filter.addItems(categories)
        index = self.category_filter.findText(previous)
        self.category_filter.setCurrentIndex(index if index >= 0 else 0)
        self.category_filter.blockSignals(False)

    def run_validation(self):
        if self._context is None:
            return []
        self.set_results(validate(
            self._context,
            self._node_info,
            nodes=self._render_nodes,
            dependencies=self._dependencies,
            farm_context=self._farm_context,
        ))
        self.validationCompleted.emit(list(self._results))
        return list(self._results)

    def set_results(self, results):
        self._results = list(results or [])
        self._rebuild_categories()
        self.refresh_filters()
        counts = summary(self._results)
        for key in ("ERROR", "WARNING", "INFO", "PASSED"):
            self.summary_buttons[key].setText("{}\n{}".format(key.title(), counts.get(key, 0)))
        self.summary_buttons["TOTAL"].setText("Total\n{}".format(counts.get("total", 0)))
        if counts.get("ERROR"):
            self.status.setText("Validation finished with {} error(s).".format(counts["ERROR"])); self.status.set_level("error")
        elif counts.get("WARNING"):
            self.status.setText("Validation passed with {} warning(s).".format(counts["WARNING"])); self.status.set_level("warning")
        else:
            self.status.setText("Validation passed: {} check(s).".format(counts.get("PASSED", 0))); self.status.set_level("good")
        self._update_action_state()

    def refresh_filters(self, *args):
        severity = self.severity_filter.currentText()
        category = self.category_filter.currentText()
        query = self.search.text().strip().lower()
        self.table.clear()
        symbols = {"ERROR": "●", "WARNING": "▲", "PASSED": "✓", "INFO": "●"}
        for result in self._results:
            level = str(result.severity or "INFO").upper()
            if severity != "All" and level != severity: continue
            if category != "All" and str(result.category) != category: continue
            haystack = " ".join((level, str(result.category), str(result.message), str(result.node_path), str(result.code))).lower()
            if query and query not in haystack: continue
            item = QtWidgets.QTreeWidgetItem((
                "{} {}".format(symbols.get(level, ""), level),
                str(result.category or "General"),
                str(result.message or ""),
                str(result.node_path or "—"),
                fix_label(result) if can_fix_result(result) else "—",
            ))
            item.setData(0, USER_ROLE, result)
            item.setForeground(0, QtGui.QBrush(QtGui.QColor(_severity_color(level))))
            item.setToolTip(2, str(result.message or ""))
            self.table.addTopLevelItem(item)
        self.details.setVisible(False)
        self._update_action_state()

    def clear_results(self):
        self._results = []
        self.table.clear()
        self.status.setText("Validation has not been run."); self.status.set_level("neutral")
        for key, button in self.summary_buttons.items():
            button.setText("{}\n0".format("Total" if key == "TOTAL" else key.title()))
        self.details.setVisible(False)
        self._update_action_state()

    def _update_details(self):
        result = self.selected_result()
        self.details.setVisible(result is not None)
        if result is None:
            self._update_action_state(); return
        self.details_title.setText("{} · {}".format(str(result.severity).upper(), result.category))
        self.details_message.setText(result.message)
        self.details_meta.setText("Code: {}    Node: {}    Auto Fix: {}".format(result.code or "—", result.node_path or "—", fix_label(result) if can_fix_result(result) else "Not available"))
        self._update_action_state()

    def _update_action_state(self):
        result = self.selected_result()
        self.fix_selected_button.setEnabled(bool(result and can_fix_result(result)))
        self.select_button.setEnabled(bool(result and result.node_path))
        self.fix_all_button.setEnabled(bool(collect_batch_safe(self._results)))
        self.export_button.setEnabled(bool(self._results))

    def _fix_selected(self):
        result = self.selected_result()
        if result and can_fix_result(result):
            self.autoFixRequested.emit(result)

    def _fix_all(self):
        values = collect_batch_safe(self._results)
        if values:
            self.autoFixAllRequested.emit(values)

    def _select_current_node(self, *args):
        result = self.selected_result()
        if result and result.node_path:
            self.selectNodeRequested.emit(str(result.node_path))
