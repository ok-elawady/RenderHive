"""Houdini job configuration and backend pool targeting."""

from __future__ import absolute_import

from renderhive_houdini.api.models import (
    worker_gpu_label,
    worker_is_online,
    worker_memory_label,
)
from renderhive_houdini.ui.qt_compat import (
    QtCore,
    QtGui,
    QtWidgets,
    Signal,
    USER_ROLE,
    CHECKED,
    UNCHECKED,
    ITEM_IS_ENABLED,
    ITEM_IS_SELECTABLE,
    ITEM_IS_USER_CHECKABLE,
    SINGLE_SELECTION,
    HEADER_STRETCH,
    HEADER_RESIZE_TO_CONTENTS,
    dialog_exec,
    DIALOG_CLOSE,
)
from renderhive_houdini.ui.widgets import (
    PageHeader,
    SectionCard,
    LabeledField,
    ReadOnlyRow,
    StatusChip,
    InlineStatus,
    apply_status_appearance,
)
from renderhive_houdini.ui.theme import COLORS


class PoolDetailsDialog(QtWidgets.QDialog):
    def __init__(self, pool, workers, parent=None):
        super().__init__(parent)
        self.pool = dict(pool or {})
        self.workers = list(workers or [])
        self.setWindowTitle("Pool Details")
        self.resize(820, 480)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QtWidgets.QLabel(str(self.pool.get("name") or "Unnamed Pool"))
        title.setObjectName("PageTitle")
        root.addWidget(title)

        description = QtWidgets.QLabel(
            str(self.pool.get("description") or "No description provided.")
        )
        description.setWordWrap(True)
        description.setObjectName("SceneMeta")
        root.addWidget(description)

        online = len([worker for worker in self.workers if worker_is_online(worker)])
        summary = QtWidgets.QLabel(
            "{} member(s) · {} online".format(len(self.workers), online)
        )
        summary.setObjectName("InlineStatus")
        apply_status_appearance(summary, "good" if online else "warning")
        root.addWidget(summary)

        table = QtWidgets.QTreeWidget()
        table.setColumnCount(7)
        table.setHeaderLabels((
            "Worker",
            "Status",
            "IP Address",
            "Cores",
            "RAM",
            "GPU",
            "Last Ping",
        ))
        table.setRootIsDecorated(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(SINGLE_SELECTION)
        table.header().setSectionResizeMode(0, HEADER_STRETCH)
        for column in (1, 2, 3, 4, 6):
            table.header().setSectionResizeMode(column, HEADER_RESIZE_TO_CONTENTS)
        table.header().setSectionResizeMode(5, HEADER_STRETCH)

        for worker in self.workers:
            status = str(worker.get("status") or "UNKNOWN").replace("_", " ").title()
            item = QtWidgets.QTreeWidgetItem((
                str(worker.get("hostname") or "Unnamed Worker"),
                status,
                str(worker.get("ip_address") or "—"),
                str(worker.get("cores") or "—"),
                worker_memory_label(worker),
                worker_gpu_label(worker),
                str(worker.get("last_ping") or "—"),
            ))
            color = COLORS["success"] if worker_is_online(worker) else COLORS["muted"]
            item.setForeground(1, QtGui.QBrush(QtGui.QColor(color)))
            table.addTopLevelItem(item)

        if not self.workers:
            item = QtWidgets.QTreeWidgetItem((
                "No workers are assigned to this pool.",
                "—", "—", "—", "—", "—", "—",
            ))
            item.setFlags(ITEM_IS_ENABLED)
            table.addTopLevelItem(item)

        root.addWidget(table, 1)

        buttons = QtWidgets.QDialogButtonBox(DIALOG_CLOSE)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


class JobPage(QtWidgets.QWidget):
    refreshFarmRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._context = None
        self._scene_key = ""
        self._workers = []
        self._pools = []
        self._checked_pool_ids = set()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(PageHeader(
            "Job Configuration",
            "Configure job identity, scheduling and worker-pool targeting.",
        ))

        details = SectionCard("Job Details", "Core information shown in the queue and reports.")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.project_name = QtWidgets.QLineEdit()
        self.project_name.setPlaceholderText("Project name")
        self.job_name = QtWidgets.QLineEdit()
        self.job_name.setPlaceholderText("Job name")
        self.priority = QtWidgets.QSpinBox()
        self.priority.setRange(1, 100)
        self.priority.setValue(50)
        self.department = QtWidgets.QLineEdit()
        self.department.setPlaceholderText("Lighting, FX, LookDev…")
        self.comment = QtWidgets.QTextEdit()
        self.comment.setPlaceholderText("Optional notes for the render team")
        self.comment.setFixedHeight(58)

        grid.addWidget(LabeledField("Project", self.project_name, "Automatically derived from $JOB or the HIP directory."), 0, 0)
        grid.addWidget(LabeledField("Job Name", self.job_name, "Automatically derived from the HIP filename."), 0, 1)
        grid.addWidget(LabeledField("Priority", self.priority, "Higher values are scheduled before lower values."), 1, 0)
        grid.addWidget(LabeledField("Department", self.department, "Optional production department or discipline."), 1, 1)
        grid.addWidget(LabeledField("Notes", self.comment, "Optional information for artists and farm operators."), 2, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        details.layout.addLayout(grid)

        scheduling = SectionCard("Scheduling", "Configure frame chunking and worker concurrency.")
        schedule_grid = QtWidgets.QGridLayout()
        schedule_grid.setHorizontalSpacing(10)
        schedule_grid.setVerticalSpacing(8)
        self.chunk_size = QtWidgets.QSpinBox()
        self.chunk_size.setRange(1, 1000)
        self.chunk_size.setValue(1)
        self.machine_limit = QtWidgets.QSpinBox()
        self.machine_limit.setRange(0, 10000)
        self.machine_limit.setSpecialValueText("Unlimited")
        self.concurrent_tasks = QtWidgets.QSpinBox()
        self.concurrent_tasks.setRange(1, 64)
        self.concurrent_tasks.setValue(1)
        self.start_suspended = QtWidgets.QCheckBox("Start Suspended")
        schedule_grid.addWidget(LabeledField("Chunk Size", self.chunk_size, "Number of frames assigned to each task."), 0, 0)
        schedule_grid.addWidget(LabeledField("Machine Limit", self.machine_limit, "Maximum workers allowed for the job. Zero means unlimited."), 0, 1)
        schedule_grid.addWidget(LabeledField("Concurrent Tasks per Worker", self.concurrent_tasks, "Maximum simultaneous frames from this job on one worker."), 1, 0)
        schedule_grid.addWidget(self.start_suspended, 1, 1)
        schedule_grid.setColumnStretch(0, 1)
        schedule_grid.setColumnStretch(1, 1)
        scheduling.layout.addLayout(schedule_grid)

        targeting = SectionCard("Pool Targeting", "Select which backend pools are eligible to receive this job.")
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(6)
        self.backend_chip = StatusChip("Backend: Not Checked")
        self.worker_chip = StatusChip("Workers: 0")
        self.pool_chip = StatusChip("Pools: 0")
        self.sync_chip = StatusChip("Last Sync: Never")
        self.refresh_farm_button = QtWidgets.QPushButton("Refresh Data")
        self.refresh_farm_button.clicked.connect(self.refreshFarmRequested.emit)
        status_row.addWidget(self.backend_chip)
        status_row.addWidget(self.worker_chip)
        status_row.addWidget(self.pool_chip)
        status_row.addWidget(self.sync_chip)
        status_row.addStretch()
        status_row.addWidget(self.refresh_farm_button)
        targeting.layout.addLayout(status_row)

        strategy_row = QtWidgets.QGridLayout()
        strategy_row.setHorizontalSpacing(10)
        self.pool_strategy = QtWidgets.QComboBox()
        self.pool_strategy.addItems((
            "All Pools",
            "Selected Pools Only",
            "All Except Selected",
        ))
        self.pool_strategy.currentIndexChanged.connect(self._on_strategy_changed)
        strategy_row.addWidget(LabeledField(
            "Pool Assignment",
            self.pool_strategy,
            "Use every pool, only selected pools, or exclude selected pools.",
        ), 0, 0)
        strategy_row.setColumnStretch(0, 1)
        targeting.layout.addLayout(strategy_row)

        self.pool_list = QtWidgets.QTreeWidget()
        self.pool_list.setColumnCount(4)
        self.pool_list.setHeaderLabels(("Pool", "Online", "Members", "Description"))
        self.pool_list.setRootIsDecorated(False)
        self.pool_list.setAlternatingRowColors(True)
        self.pool_list.setSelectionMode(SINGLE_SELECTION)
        self.pool_list.itemChanged.connect(self._on_pool_item_changed)
        self.pool_list.itemSelectionChanged.connect(self._on_pool_row_changed)
        self.pool_list.itemDoubleClicked.connect(self._show_pool_details)
        self.pool_list.setMinimumHeight(150)
        self.pool_list.header().setSectionResizeMode(0, HEADER_STRETCH)
        self.pool_list.header().setSectionResizeMode(1, HEADER_RESIZE_TO_CONTENTS)
        self.pool_list.header().setSectionResizeMode(2, HEADER_RESIZE_TO_CONTENTS)
        self.pool_list.header().setSectionResizeMode(3, HEADER_STRETCH)
        targeting.layout.addWidget(self.pool_list)

        pool_actions = QtWidgets.QHBoxLayout()
        self.selection_label = QtWidgets.QLabel("No pools selected")
        self.selection_label.setObjectName("SceneMeta")
        self.details_button = QtWidgets.QPushButton("View Pool Details")
        self.details_button.setEnabled(False)
        self.details_button.clicked.connect(self._show_current_pool_details)
        pool_actions.addWidget(self.selection_label)
        pool_actions.addStretch()
        pool_actions.addWidget(self.details_button)
        targeting.layout.addLayout(pool_actions)

        self.targeting_summary = InlineStatus("Backend pool data has not been synchronized.", "neutral")
        targeting.layout.addWidget(self.targeting_summary)

        paths = SectionCard("Scene & Project Paths", "Paths detected from the current Houdini session.")
        path_grid = QtWidgets.QGridLayout()
        path_grid.setHorizontalSpacing(10)
        path_grid.setVerticalSpacing(8)
        self.hip_file = ReadOnlyRow("HIP File", tooltip="Current .hip, .hiplc or .hipnc file.")
        self.project_path = ReadOnlyRow("Project Path", tooltip="Uses $JOB when available, otherwise the HIP directory.")
        self.hip_directory = ReadOnlyRow("$HIP")
        self.job_directory = ReadOnlyRow("$JOB")
        path_grid.addWidget(self.hip_file, 0, 0, 1, 2)
        path_grid.addWidget(self.project_path, 1, 0, 1, 2)
        path_grid.addWidget(self.hip_directory, 2, 0)
        path_grid.addWidget(self.job_directory, 2, 1)
        path_grid.setColumnStretch(0, 1)
        path_grid.setColumnStretch(1, 1)
        paths.layout.addLayout(path_grid)

        root.addWidget(details)
        root.addWidget(scheduling)
        root.addWidget(targeting)
        root.addWidget(paths)
        root.addStretch()

    @staticmethod
    def _context_key(context):
        path = str(getattr(context, "hip_path", "") or "").strip().lower()
        if path:
            return path
        return "__untitled__:{}".format(str(getattr(context, "hip_name", "") or ""))

    def set_context(self, context, force_identity=False):
        new_key = self._context_key(context)
        identity_changed = bool(force_identity or new_key != self._scene_key)
        self._context = context
        self._scene_key = new_key

        if identity_changed:
            self.project_name.setText(context.project_name or "Houdini Project")
            self.job_name.setText(context.scene_name or "houdini_job")
        else:
            if not self.project_name.text().strip():
                self.project_name.setText(context.project_name or "Houdini Project")
            if not self.job_name.text().strip():
                self.job_name.setText(context.scene_name or "houdini_job")

        self.hip_file.set_value(context.hip_path or "Unsaved HIP file")
        self.project_path.set_value(context.project_path or "Not Set")
        self.hip_directory.set_value(context.hip_directory or "Not Set")
        self.job_directory.set_value(context.job_directory or "Not Set")
        return identity_changed

    def set_syncing(self, syncing):
        self.refresh_farm_button.setEnabled(not bool(syncing))
        self.refresh_farm_button.setText("Refreshing…" if syncing else "Refresh Data")
        if syncing:
            self.backend_chip.setText("Backend: Connecting")

    def set_backend_error(self, message):
        self.backend_chip.setText("Backend: Offline")
        apply_status_appearance(self.backend_chip, "error")
        self.targeting_summary.setText(str(message or "Backend connection failed."))
        self.targeting_summary.set_level("error")
        self.set_syncing(False)

    def _workers_for_pool(self, pool_id):
        pool_id = str(pool_id or "")
        return [
            worker for worker in self._workers
            if pool_id and any(
                str(item.get("id") or "") == pool_id
                for item in worker.get("pools") or []
            )
        ]

    def set_farm_data(self, workers, pools, synced_at=""):
        self._workers = list(workers or [])
        self._pools = list(pools or [])
        online_total = len([worker for worker in self._workers if worker_is_online(worker)])

        self.backend_chip.setText("Backend: Online")
        apply_status_appearance(self.backend_chip, "good")
        self.worker_chip.setText("Workers: {} / {} Online".format(online_total, len(self._workers)))
        self.pool_chip.setText("Pools: {}".format(len(self._pools)))
        self.sync_chip.setText("Last Sync: {}".format(synced_at or "Now"))

        checked_ids = set(self.selected_pool_ids()) or set(self._checked_pool_ids)
        available_ids = set(str(pool.get("id") or "") for pool in self._pools if pool.get("id"))
        checked_ids.intersection_update(available_ids)
        self._checked_pool_ids = set(checked_ids)
        self.pool_list.blockSignals(True)
        self.pool_list.clear()
        for pool in self._pools:
            pool_id = str(pool.get("id") or "")
            members = self._workers_for_pool(pool_id)
            online = len([worker for worker in members if worker_is_online(worker)])
            item = QtWidgets.QTreeWidgetItem((
                str(pool.get("name") or "Unnamed Pool"),
                str(online),
                str(len(members)),
                str(pool.get("description") or ""),
            ))
            item.setData(0, USER_ROLE, pool_id)
            item.setFlags(ITEM_IS_ENABLED | ITEM_IS_SELECTABLE | ITEM_IS_USER_CHECKABLE)
            item.setCheckState(0, CHECKED if pool_id in checked_ids else UNCHECKED)
            item.setToolTip(0, "Double-click to view assigned workers.")
            self.pool_list.addTopLevelItem(item)
        self.pool_list.blockSignals(False)
        self.set_syncing(False)
        self._on_strategy_changed()

    def _on_strategy_changed(self, *args):
        strategy = self.pool_strategy.currentText()
        checking_enabled = strategy != "All Pools"
        self.pool_list.blockSignals(True)
        for index in range(self.pool_list.topLevelItemCount()):
            item = self.pool_list.topLevelItem(index)
            flags = ITEM_IS_ENABLED | ITEM_IS_SELECTABLE
            if checking_enabled:
                flags = flags | ITEM_IS_USER_CHECKABLE
            item.setFlags(flags)
        self.pool_list.blockSignals(False)
        self._update_targeting_summary()

    def _on_pool_item_changed(self, item, column):
        if column != 0:
            return
        pool_id = str(item.data(0, USER_ROLE) or "")
        if item.checkState(0) == CHECKED:
            self._checked_pool_ids.add(pool_id)
        else:
            self._checked_pool_ids.discard(pool_id)
        self._update_targeting_summary()

    def _on_pool_row_changed(self):
        self.details_button.setEnabled(self.pool_list.currentItem() is not None)

    def selected_pool_ids(self):
        values = []
        for index in range(self.pool_list.topLevelItemCount()):
            item = self.pool_list.topLevelItem(index)
            if item.checkState(0) == CHECKED:
                value = str(item.data(0, USER_ROLE) or "")
                if value:
                    values.append(value)
        return values

    def selected_pool_names(self):
        values = []
        for index in range(self.pool_list.topLevelItemCount()):
            item = self.pool_list.topLevelItem(index)
            if item.checkState(0) == CHECKED:
                values.append(str(item.text(0) or ""))
        return values

    def _pool_from_item(self, item):
        if item is None:
            return None
        pool_id = str(item.data(0, USER_ROLE) or "")
        for pool in self._pools:
            if str(pool.get("id") or "") == pool_id:
                return pool
        return None

    def _show_pool_details(self, item, column=0):
        pool = self._pool_from_item(item)
        if not pool:
            return
        dialog = PoolDetailsDialog(
            pool,
            self._workers_for_pool(pool.get("id")),
            parent=self,
        )
        dialog_exec(dialog)

    def _show_current_pool_details(self):
        self._show_pool_details(self.pool_list.currentItem())

    def pool_targeting(self):
        all_ids = [str(pool.get("id") or "") for pool in self._pools if pool.get("id")]
        all_names = [str(pool.get("name") or "") for pool in self._pools if pool.get("name")]
        selected_ids = self.selected_pool_ids()
        selected_names = self.selected_pool_names()
        strategy_text = self.pool_strategy.currentText()

        if strategy_text == "Selected Pools Only":
            strategy = "selected_only"
            effective_ids = selected_ids
            effective_names = selected_names
            excluded_ids = []
            excluded_names = []
        elif strategy_text == "All Except Selected":
            strategy = "all_except_selected"
            selected_set = set(selected_ids)
            effective_ids = [value for value in all_ids if value not in selected_set]
            selected_name_set = set(selected_names)
            effective_names = [value for value in all_names if value not in selected_name_set]
            excluded_ids = selected_ids
            excluded_names = selected_names
        else:
            strategy = "all"
            effective_ids = all_ids
            effective_names = all_names
            excluded_ids = []
            excluded_names = []

        eligible_workers = []
        effective_set = set(effective_ids)
        for worker in self._workers:
            if not worker_is_online(worker):
                continue
            worker_pool_ids = set(
                str(item.get("id") or "")
                for item in worker.get("pools") or []
            )
            if not effective_set or worker_pool_ids.intersection(effective_set):
                eligible_workers.append(worker)

        return {
            "strategy": strategy,
            "selected_pool_ids": selected_ids,
            "selected_pool_names": selected_names,
            "excluded_pool_ids": excluded_ids,
            "excluded_pool_names": excluded_names,
            "effective_pool_ids": effective_ids,
            "effective_pool_names": effective_names,
            "eligible_worker_ids": [worker.get("id") for worker in eligible_workers],
            "eligible_worker_count": len(eligible_workers),
        }

    def _update_targeting_summary(self):
        data = self.pool_targeting()
        selected_count = len(data.get("selected_pool_ids") or [])
        self.selection_label.setText(
            "{} pool{} selected".format(
                selected_count,
                "" if selected_count == 1 else "s",
            )
        )
        strategy = data.get("strategy")
        if strategy == "selected_only" and not data.get("selected_pool_ids"):
            self.targeting_summary.setText("Select at least one pool before submitting.")
            self.targeting_summary.set_level("warning")
            return
        self.targeting_summary.setText(
            "{} eligible online worker(s) across {} effective pool(s).".format(
                data.get("eligible_worker_count", 0),
                len(data.get("effective_pool_ids") or []),
            )
        )
        self.targeting_summary.set_level("good" if data.get("eligible_worker_count") else "warning")

    def job_settings(self):
        return {
            "project_name": self.project_name.text().strip(),
            "job_name": self.job_name.text().strip(),
            "priority": self.priority.value(),
            "department": self.department.text().strip(),
            "comment": self.comment.toPlainText().strip(),
            "chunk_size": self.chunk_size.value(),
            "machine_limit": self.machine_limit.value(),
            "concurrent_tasks": self.concurrent_tasks.value(),
            "start_suspended": self.start_suspended.isChecked(),
        }
