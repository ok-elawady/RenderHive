"""Backend job browser used for cross-DCC dependency selection."""

from __future__ import absolute_import

from renderhive_houdini.ui.qt_compat import (
    QtCore,
    QtGui,
    QtWidgets,
    USER_ROLE,
    CHECKED,
    UNCHECKED,
    ITEM_IS_USER_CHECKABLE,
    NO_ITEM_FLAGS,
    NO_SELECTION,
    HEADER_STRETCH,
    HEADER_RESIZE_TO_CONTENTS,
    DIALOG_OK,
    DIALOG_CANCEL,
)
from renderhive_houdini.ui.theme import COLORS


def job_identifier(job):
    if not isinstance(job, dict):
        return ""
    return str(job.get("id") or job.get("job_id") or job.get("uid") or "").strip()


def job_display_name(job):
    if not isinstance(job, dict):
        return "Unnamed Job"
    return str(job.get("visible_name") or job.get("name") or job_identifier(job) or "Unnamed Job").strip()


def job_state(job):
    if not isinstance(job, dict):
        return "UNKNOWN"
    return str(job.get("state") or job.get("status") or "UNKNOWN").strip().upper()


def job_dcc(job):
    if not isinstance(job, dict):
        return "—"
    direct = str(job.get("dcc") or "").strip()
    if direct:
        return direct.title()
    for layer in job.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        info = layer.get("scene_info") if isinstance(layer.get("scene_info"), dict) else {}
        value = str(info.get("dcc") or "").strip()
        if value:
            return value.title()
    return "—"


def _state_color(state):
    state = str(state or "").upper()
    if state in ("FINISHED", "SUCCEEDED", "COMPLETED", "DONE"):
        return COLORS["success"]
    if state in ("FAILED", "ERROR", "CANCELLED", "CANCELED"):
        return COLORS["error"]
    if state in ("RUNNING", "RENDERING", "ACTIVE"):
        return COLORS["info"]
    if state in ("PAUSED", "SUSPENDED"):
        return COLORS["warning"]
    return COLORS["secondary"]


class JobDependencyDialog(QtWidgets.QDialog):
    """Read-only RenderHive job browser with explicit checkbox selection."""

    def __init__(self, jobs, selected_ids=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Job Dependencies")
        self.setObjectName("JobDependencyDialog")
        self.setModal(True)
        self.resize(1040, 620)
        self._jobs = [dict(job) for job in (jobs or []) if isinstance(job, dict)]
        self._selected_ids = []
        for value in selected_ids or []:
            clean = str(value or "").strip()
            if clean and clean not in self._selected_ids:
                self._selected_ids.append(clean)
        self._items = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(9)

        title = QtWidgets.QLabel("Job Dependencies")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        description = QtWidgets.QLabel(
            "Select existing Maya or Houdini RenderHive jobs that must complete before this Houdini job can start."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)
        root.addWidget(description)

        filters = QtWidgets.QHBoxLayout()
        filters.setSpacing(7)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search job, DCC, project, user, state or ID…")
        try:
            self.search.setClearButtonEnabled(True)
        except Exception:
            pass
        self.search.textChanged.connect(self.filter_items)
        filters.addWidget(self.search, 1)
        self.state_filter = QtWidgets.QComboBox()
        self.state_filter.addItem("All States", "")
        for state in sorted({job_state(job) for job in self._jobs if job_state(job)}):
            self.state_filter.addItem(state.replace("_", " ").title(), state)
        self.state_filter.currentIndexChanged.connect(self.filter_items)
        filters.addWidget(self.state_filter)
        root.addLayout(filters)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("JobDependencyTree")
        self.tree.setColumnCount(9)
        self.tree.setHeaderLabels((
            "Job", "DCC", "Project", "User", "State", "Priority", "Tasks", "Submitted", "Job ID"
        ))
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(NO_SELECTION)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, HEADER_STRETCH)
        for column in (1, 2, 3, 4, 5, 6, 7):
            self.tree.header().setSectionResizeMode(column, HEADER_RESIZE_TO_CONTENTS)
        self.tree.header().setSectionResizeMode(8, HEADER_STRETCH)
        root.addWidget(self.tree, 1)

        selected_set = set(self._selected_ids)
        known_ids = set()
        for job in self._jobs:
            job_id = job_identifier(job)
            if not job_id:
                continue
            known_ids.add(job_id)
            state = job_state(job)
            task_count = job.get("total_tasks")
            if task_count is None:
                task_count = job.get("task_count")
            created = str(job.get("created_at") or job.get("submitted_at") or "").replace("T", " ")
            if created.endswith("Z"):
                created = created[:-1] + " UTC"
            item = QtWidgets.QTreeWidgetItem((
                job_display_name(job),
                job_dcc(job),
                str(job.get("project") or "—"),
                str(job.get("user") or "—"),
                state.replace("_", " ").title(),
                str(job.get("priority") if job.get("priority") is not None else "—"),
                str(task_count if task_count is not None else "—"),
                created or "—",
                job_id,
            ))
            item.setData(0, USER_ROLE, job_id)
            item.setData(0, USER_ROLE + 1, state)
            item.setFlags(item.flags() | ITEM_IS_USER_CHECKABLE)
            item.setCheckState(0, CHECKED if job_id in selected_set else UNCHECKED)
            item.setForeground(4, QtGui.QBrush(QtGui.QColor(_state_color(state))))
            item.setToolTip(0, "Dependency Job ID: {}".format(job_id))
            self.tree.addTopLevelItem(item)
            self._items.append(item)

        for job_id in self._selected_ids:
            if job_id in known_ids:
                continue
            item = QtWidgets.QTreeWidgetItem((
                "Previously selected job", "—", "—", "—", "Unavailable", "—", "—", "—", job_id
            ))
            item.setData(0, USER_ROLE, job_id)
            item.setData(0, USER_ROLE + 1, "UNAVAILABLE")
            item.setFlags(item.flags() | ITEM_IS_USER_CHECKABLE)
            item.setCheckState(0, CHECKED)
            item.setForeground(4, QtGui.QBrush(QtGui.QColor(COLORS["warning"])))
            item.setToolTip(0, "This saved dependency was not returned by the backend.")
            self.tree.addTopLevelItem(item)
            self._items.append(item)

        if not self._items:
            item = QtWidgets.QTreeWidgetItem(("No RenderHive jobs were returned.", "—", "—", "—", "—", "—", "—", "—", "—"))
            item.setFlags(NO_ITEM_FLAGS)
            item.setForeground(0, QtGui.QBrush(QtGui.QColor(COLORS["muted"])))
            self.tree.addTopLevelItem(item)

        utility = QtWidgets.QHBoxLayout()
        utility.setSpacing(7)
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setObjectName("SecondaryText")
        utility.addWidget(self.count_label)
        utility.addStretch()
        select_visible = QtWidgets.QPushButton("Select Visible")
        select_visible.setObjectName("GhostButton")
        select_visible.clicked.connect(self.select_visible)
        clear = QtWidgets.QPushButton("Clear")
        clear.setObjectName("GhostButton")
        clear.clicked.connect(self.clear_all)
        utility.addWidget(select_visible)
        utility.addWidget(clear)
        root.addLayout(utility)

        buttons = QtWidgets.QDialogButtonBox(DIALOG_CANCEL | DIALOG_OK)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.tree.itemChanged.connect(self.update_count)
        self.update_count()

    def filter_items(self, *args):
        query = str(self.search.text() or "").strip().lower()
        state_value = str(self.state_filter.currentData() or "").strip().upper()
        for item in self._items:
            text = " ".join(item.text(column) for column in range(item.columnCount())).lower()
            item_state = str(item.data(0, USER_ROLE + 1) or "").upper()
            item.setHidden(bool((query and query not in text) or (state_value and item_state != state_value)))

    def select_visible(self):
        self.tree.blockSignals(True)
        try:
            for item in self._items:
                if not item.isHidden():
                    item.setCheckState(0, CHECKED)
        finally:
            self.tree.blockSignals(False)
        self.update_count()

    def clear_all(self):
        self.tree.blockSignals(True)
        try:
            for item in self._items:
                item.setCheckState(0, UNCHECKED)
        finally:
            self.tree.blockSignals(False)
        self.update_count()

    def selected_ids(self):
        result = []
        for item in self._items:
            if item.checkState(0) != CHECKED:
                continue
            value = str(item.data(0, USER_ROLE) or "").strip()
            if value and value not in result:
                result.append(value)
        return result

    def selected_records(self):
        selected = set(self.selected_ids())
        return [dict(job) for job in self._jobs if job_identifier(job) in selected]

    def update_count(self, *args):
        count = len(self.selected_ids())
        self.count_label.setText("{} job{} selected".format(count, "" if count == 1 else "s"))
