"""Production validation, filtering and Auto Fix UI for Houdini."""

from __future__ import absolute_import

from renderhive_houdini.ui.qt_compat import (
    QtWidgets,
    QtGui,
    Signal,
    USER_ROLE,
    HEADER_STRETCH,
    HEADER_RESIZE_TO_CONTENTS,
    ALIGN_CENTER,
)
from renderhive_houdini.ui.widgets import PageHeader, SectionCard, LabeledField, InlineStatus
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
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(PageHeader("Scene Validation", "Errors block submission. Safe issues can be fixed automatically."))

        summary_card = SectionCard("Validation Summary", "Select a counter to filter the results table.")
        summary_grid = QtWidgets.QHBoxLayout()
        summary_grid.setSpacing(6)
        self.summary_buttons = {}
        for key in ("ERROR", "WARNING", "INFO", "PASSED", "TOTAL"):
            button = QtWidgets.QPushButton("{}\n0".format(key.title()))
            button.setObjectName("CounterCard")
            button.setMinimumHeight(48)
            button.setStyleSheet(
                "QPushButton#CounterCard { border-top: 3px solid %s; }"
                % _severity_color(key)
            )
            button.clicked.connect(lambda checked=False, value=key: self._set_severity(value))
            self.summary_buttons[key] = button
            summary_grid.addWidget(button, 1)
        summary_card.layout.addLayout(summary_grid)

        filters = SectionCard("Filter Results")
        filter_grid = QtWidgets.QGridLayout()
        filter_grid.setHorizontalSpacing(10)
        self.severity_filter = QtWidgets.QComboBox()
        self.severity_filter.addItems(("All", "ERROR", "WARNING", "INFO", "PASSED"))
        self.category_filter = QtWidgets.QComboBox()
        self.category_filter.addItem("All")
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search message, node, category or code")
        self.severity_filter.currentIndexChanged.connect(self.refresh_filters)
        self.category_filter.currentIndexChanged.connect(self.refresh_filters)
        self.search.textChanged.connect(self.refresh_filters)
        filter_grid.addWidget(LabeledField("Severity", self.severity_filter), 0, 0)
        filter_grid.addWidget(LabeledField("Category", self.category_filter), 0, 1)
        filter_grid.addWidget(LabeledField("Search", self.search), 0, 2)
        filter_grid.setColumnStretch(0, 1); filter_grid.setColumnStretch(1, 1); filter_grid.setColumnStretch(2, 2)
        filters.layout.addLayout(filter_grid)

        results_card = SectionCard("Results", "Double-click a result to select its Houdini node when available.")
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
        details_layout.setContentsMargins(10, 8, 10, 8)
        self.details_title = QtWidgets.QLabel("Selected Result")
        self.details_title.setObjectName("SectionTitle")
        self.details_message = QtWidgets.QLabel("Select a result to inspect it.")
        self.details_message.setWordWrap(True)
        self.details_meta = QtWidgets.QLabel("")
        self.details_meta.setObjectName("SceneMeta")
        self.details_meta.setWordWrap(True)
        details_layout.addWidget(self.details_title)
        details_layout.addWidget(self.details_message)
        details_layout.addWidget(self.details_meta)
        self.details.setVisible(False)
        results_card.layout.addWidget(self.details)

        actions = QtWidgets.QHBoxLayout()
        self.validate_button = QtWidgets.QPushButton("Validate Scene")
        self.validate_button.setObjectName("PrimaryButton")
        self.fix_selected_button = QtWidgets.QPushButton("Fix Selected")
        self.fix_all_button = QtWidgets.QPushButton("Fix All Safe")
        self.select_button = QtWidgets.QPushButton("Select Node")
        self.export_button = QtWidgets.QPushButton("Export Report")
        self.clear_button = QtWidgets.QPushButton("Clear Results")
        self.validate_button.clicked.connect(self.run_validation)
        self.fix_selected_button.clicked.connect(self._fix_selected)
        self.fix_all_button.clicked.connect(self._fix_all)
        self.select_button.clicked.connect(self._select_current_node)
        self.export_button.clicked.connect(lambda: self.exportRequested.emit(list(self._results)))
        self.clear_button.clicked.connect(self.clear_results)
        for button in (self.validate_button, self.fix_selected_button, self.fix_all_button, self.select_button, self.export_button):
            actions.addWidget(button)
        actions.addStretch(); actions.addWidget(self.clear_button)
        results_card.layout.addLayout(actions)

        root.addWidget(summary_card)
        root.addWidget(filters)
        root.addWidget(results_card, 1)
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
