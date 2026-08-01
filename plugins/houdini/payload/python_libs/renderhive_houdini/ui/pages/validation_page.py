"""Maya-parity validation page for Houdini scenes and render nodes."""

from __future__ import absolute_import

from renderhive_houdini.ui.qt_compat import QtWidgets, HEADER_STRETCH, HEADER_RESIZE_TO_CONTENTS, ALIGN_CENTER
from renderhive_houdini.ui.widgets import PageHeader, SectionCard, InlineStatus
from renderhive_houdini.validation.validator import validate


class ValidationPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._context = None; self._node_info = None
        root = QtWidgets.QVBoxLayout(self); root.setContentsMargins(8,4,8,8); root.setSpacing(10)
        root.addWidget(PageHeader("Scene Validation", "Errors block submission. Warnings should be reviewed."))

        summary_card = SectionCard("Validation Summary")
        summary_grid = QtWidgets.QGridLayout(); summary_grid.setHorizontalSpacing(7)
        self.summary_labels = {}
        for index, key in enumerate(("ERROR", "WARNING", "INFO", "PASSED", "TOTAL")):
            label = QtWidgets.QLabel("{}\n0".format(key.title()))
            label.setObjectName("MetaChip"); label.setMinimumHeight(48); label.setAlignment(ALIGN_CENTER)
            self.summary_labels[key] = label; summary_grid.addWidget(label, 0, index)
        summary_card.layout.addLayout(summary_grid)

        results = SectionCard("Results", "Run validation after choosing a render node.")
        actions = QtWidgets.QHBoxLayout()
        self.validate_button = QtWidgets.QPushButton("Validate Scene"); self.validate_button.setObjectName("PrimaryButton"); self.validate_button.clicked.connect(self.run_validation)
        self.clear_button = QtWidgets.QPushButton("Clear Results"); self.clear_button.clicked.connect(self.clear_results)
        actions.addWidget(self.validate_button); actions.addWidget(self.clear_button); actions.addStretch(); results.layout.addLayout(actions)
        self.summary = InlineStatus("Validation has not been run.", "neutral"); results.layout.addWidget(self.summary)
        self.table = QtWidgets.QTreeWidget(); self.table.setColumnCount(4); self.table.setHeaderLabels(["Status", "Category", "Message", "Node"]); self.table.setRootIsDecorated(False); self.table.setAlternatingRowColors(True)
        self.table.header().setStretchLastSection(False); self.table.header().setSectionResizeMode(0, HEADER_RESIZE_TO_CONTENTS); self.table.header().setSectionResizeMode(1, HEADER_RESIZE_TO_CONTENTS); self.table.header().setSectionResizeMode(2, HEADER_STRETCH); self.table.header().setSectionResizeMode(3, HEADER_STRETCH)
        results.layout.addWidget(self.table, 1)
        root.addWidget(summary_card); root.addWidget(results, 1)

    def set_context(self, context): self._context = context
    def set_render_node(self, node_info): self._node_info = node_info

    def clear_results(self):
        self.table.clear(); self.summary.setText("Validation has not been run."); self.summary.set_level("neutral")
        for key, label in self.summary_labels.items(): label.setText("{}\n0".format(key.title()))

    def run_validation(self):
        if self._context is None: return
        results = validate(self._context, self._node_info); self.table.clear()
        counts = {"ERROR":0,"WARNING":0,"PASSED":0,"INFO":0}
        symbols = {"ERROR":"●", "WARNING":"▲", "PASSED":"✓", "INFO":"●"}
        for result in results:
            severity = result.severity.upper(); counts[severity] = counts.get(severity,0)+1
            item = QtWidgets.QTreeWidgetItem(["{} {}".format(symbols.get(severity,""), severity), result.category, result.message, result.node_path]); item.setToolTip(2, result.message); self.table.addTopLevelItem(item)
        total = sum(counts.values())
        for key in ("ERROR","WARNING","INFO","PASSED"): self.summary_labels[key].setText("{}\n{}".format(key.title(), counts[key]))
        self.summary_labels["TOTAL"].setText("Total\n{}".format(total))
        if counts["ERROR"]:
            self.summary.setText("Validation finished with {} error(s).".format(counts["ERROR"])); self.summary.set_level("error")
        elif counts["WARNING"]:
            self.summary.setText("Validation passed with {} warning(s).".format(counts["WARNING"])); self.summary.set_level("warning")
        else:
            self.summary.setText("Validation passed: {} check(s).".format(counts["PASSED"])); self.summary.set_level("good")
