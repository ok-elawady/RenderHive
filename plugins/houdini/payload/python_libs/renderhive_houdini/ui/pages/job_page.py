"""Production Houdini job configuration and API 0.2.0 farm targeting UI."""

from __future__ import absolute_import

from renderhive_houdini.api.models import (
    worker_gpu_label,
    worker_is_online,
    worker_memory_label,
    worker_meets_requirements,
    worker_supports_houdini,
)
from renderhive_houdini.ui.qt_compat import (
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
    SegmentedChoice,
    apply_status_appearance,
)
from renderhive_houdini.ui.theme import COLORS


class PoolDetailsDialog(QtWidgets.QDialog):
    def __init__(self, pool, workers, parent=None):
        super().__init__(parent)
        self.pool = dict(pool or {})
        self.workers = list(workers or [])
        self.setWindowTitle("Pool Details")
        self.resize(900, 510)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        title = QtWidgets.QLabel(str(self.pool.get("name") or "Unnamed Pool"))
        title.setObjectName("PageTitle")
        root.addWidget(title)
        description = QtWidgets.QLabel(str(self.pool.get("description") or "No description provided."))
        description.setWordWrap(True)
        description.setObjectName("MutedText")
        root.addWidget(description)
        online = len([worker for worker in self.workers if worker_is_online(worker)])
        root.addWidget(InlineStatus(
            "{} member(s) · {} online".format(len(self.workers), online),
            "good" if online else "warning",
        ))

        table = QtWidgets.QTreeWidget()
        table.setColumnCount(8)
        table.setHeaderLabels(("Worker", "Status", "IP Address", "Cores", "RAM", "GPU", "Tags", "Last Ping"))
        table.setRootIsDecorated(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(SINGLE_SELECTION)
        table.header().setSectionResizeMode(0, HEADER_STRETCH)
        for column in (1, 2, 3, 4, 7):
            table.header().setSectionResizeMode(column, HEADER_RESIZE_TO_CONTENTS)
        table.header().setSectionResizeMode(5, HEADER_STRETCH)
        table.header().setSectionResizeMode(6, HEADER_STRETCH)
        for worker in self.workers:
            status = str(worker.get("status") or "UNKNOWN").replace("_", " ").title()
            item = QtWidgets.QTreeWidgetItem((
                str(worker.get("hostname") or "Unnamed Worker"),
                status,
                str(worker.get("ip_address") or "—"),
                str(worker.get("cores") or "—"),
                worker_memory_label(worker),
                worker_gpu_label(worker),
                ", ".join(str(tag) for tag in worker.get("tags") or []) or "—",
                str(worker.get("last_ping") or "—"),
            ))
            color = COLORS["success"] if worker_is_online(worker) else COLORS["muted"]
            item.setForeground(1, QtGui.QBrush(QtGui.QColor(color)))
            table.addTopLevelItem(item)
        if not self.workers:
            item = QtWidgets.QTreeWidgetItem(("No workers are assigned to this pool.", "—", "—", "—", "—", "—", "—", "—"))
            item.setFlags(ITEM_IS_ENABLED)
            table.addTopLevelItem(item)
        root.addWidget(table, 1)
        buttons = QtWidgets.QDialogButtonBox(DIALOG_CLOSE)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


class JobPage(QtWidgets.QWidget):
    refreshFarmRequested = Signal()
    browseDependenciesRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._context = None
        self._scene_key = ""
        self._workers = []
        self._pools = []
        self._checked_pool_ids = set()
        self._job_dependency_ids = []
        self._job_dependency_records = {}
        self._houdini_version = ""
        self._render_requirements = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(10)
        root.addWidget(PageHeader(
            "Job Configuration",
            "Configure job metadata, scheduling, pool targeting and dependencies.",
        ))

        details = SectionCard("Job Details", "Identity and ownership information shown in the queue and reports.")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.project_name = QtWidgets.QLineEdit(); self.project_name.setPlaceholderText("Project name")
        self.job_name = QtWidgets.QLineEdit(); self.job_name.setPlaceholderText("Job name")
        self.priority = QtWidgets.QSpinBox(); self.priority.setRange(1, 100); self.priority.setValue(50)
        self.department = QtWidgets.QLineEdit(); self.department.setPlaceholderText("Lighting, FX, LookDev…")
        self.comment = QtWidgets.QLineEdit(); self.comment.setPlaceholderText("Optional notes for the render team")
        grid.addWidget(LabeledField("Project", self.project_name, "Project label used to organize and report submitted jobs."), 0, 0)
        grid.addWidget(LabeledField("Job Name", self.job_name, "Name displayed in the RenderHive queue and reports."), 0, 1)
        grid.addWidget(LabeledField("Priority", self.priority, "Higher values are scheduled before lower-priority jobs when resources are available."), 1, 0)
        grid.addWidget(LabeledField("Department", self.department, "Optional department or production discipline."), 1, 1)
        grid.addWidget(LabeledField("Notes", self.comment, "Optional information for artists, operators or supervisors."), 2, 0, 1, 2)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        details.layout.addLayout(grid)

        scheduling = SectionCard("Scheduling", "Control task chunking, worker concurrency and minimum hardware.")
        schedule_grid = QtWidgets.QGridLayout()
        schedule_grid.setHorizontalSpacing(10); schedule_grid.setVerticalSpacing(8)
        self.chunk_size = QtWidgets.QSpinBox(); self.chunk_size.setRange(1, 10000); self.chunk_size.setValue(1)
        self.concurrent_tasks = QtWidgets.QSpinBox(); self.concurrent_tasks.setRange(1, 64); self.concurrent_tasks.setValue(1)
        self.min_cores = QtWidgets.QSpinBox(); self.min_cores.setRange(0, 4096); self.min_cores.setSpecialValueText("Any")
        self.min_memory_gb = QtWidgets.QSpinBox(); self.min_memory_gb.setRange(0, 65536); self.min_memory_gb.setSpecialValueText("Any"); self.min_memory_gb.setSuffix(" GB")
        self.min_gpus = QtWidgets.QSpinBox(); self.min_gpus.setRange(0, 64); self.min_gpus.setSpecialValueText("Any")
        for widget in (self.min_cores, self.min_memory_gb, self.min_gpus):
            widget.valueChanged.connect(self._update_targeting_summary)
        schedule_grid.addWidget(LabeledField("Chunk Size", self.chunk_size, "Number of consecutive frames assigned to each farm task."), 0, 0)
        schedule_grid.addWidget(LabeledField("Tasks per Worker", self.concurrent_tasks, "Maximum tasks from this job that one worker may run concurrently."), 0, 1)
        schedule_grid.addWidget(LabeledField("Minimum CPU Cores", self.min_cores, "Minimum CPU core count required by the scheduler. Any disables this requirement."), 1, 0)
        schedule_grid.addWidget(LabeledField("Minimum RAM", self.min_memory_gb, "Minimum physical memory required by an eligible worker."), 1, 1)
        schedule_grid.addWidget(LabeledField("Minimum GPUs", self.min_gpus, "Minimum GPU count. Karma XPU tasks automatically require at least one GPU in the payload."), 2, 0)
        schedule_grid.setColumnStretch(0, 1); schedule_grid.setColumnStretch(1, 1)
        scheduling.layout.addLayout(schedule_grid)

        targeting = SectionCard("Pool Selection", "Choose which backend worker pools are eligible to receive this job.")
        status_row = QtWidgets.QHBoxLayout(); status_row.setSpacing(6)
        self.backend_chip = StatusChip("Backend: Not Checked")
        self.worker_chip = StatusChip("Workers: 0")
        self.pool_chip = StatusChip("Pools: 0")
        self.sync_chip = StatusChip("Last Sync: Never")
        self.refresh_farm_button = QtWidgets.QPushButton("Refresh")
        self.refresh_farm_button.setObjectName("InfoButton")
        self.refresh_farm_button.clicked.connect(self.refreshFarmRequested.emit)
        for chip in (self.backend_chip, self.worker_chip, self.pool_chip, self.sync_chip):
            status_row.addWidget(chip)
        status_row.addStretch(); status_row.addWidget(self.refresh_farm_button)
        targeting.layout.addLayout(status_row)

        self.pool_strategy = SegmentedChoice(("All Pools", "Selected Pools Only", "All Except Selected"))
        self.pool_strategy.currentTextChanged.connect(self._on_strategy_changed)
        targeting.layout.addWidget(LabeledField(
            "Assignment Strategy", self.pool_strategy,
            "Use every pool, selected pools only, or every pool except selected pools.",
        ))

        self.pool_list = QtWidgets.QTreeWidget()
        self.pool_list.setObjectName("RenderLayerTree")
        self.pool_list.setColumnCount(4)
        self.pool_list.setHeaderLabels(("Pool", "Online", "Members", "Description"))
        self.pool_list.setRootIsDecorated(False)
        self.pool_list.setAlternatingRowColors(True)
        self.pool_list.setSelectionMode(SINGLE_SELECTION)
        self.pool_list.itemChanged.connect(self._on_pool_item_changed)
        self.pool_list.itemSelectionChanged.connect(self._on_pool_row_changed)
        self.pool_list.itemDoubleClicked.connect(self._show_pool_details)
        self.pool_list.setMinimumHeight(145)
        self.pool_list.header().setSectionResizeMode(0, HEADER_STRETCH)
        self.pool_list.header().setSectionResizeMode(1, HEADER_RESIZE_TO_CONTENTS)
        self.pool_list.header().setSectionResizeMode(2, HEADER_RESIZE_TO_CONTENTS)
        self.pool_list.header().setSectionResizeMode(3, HEADER_STRETCH)
        targeting.layout.addWidget(self.pool_list)

        pool_actions = QtWidgets.QHBoxLayout()
        self.selection_label = QtWidgets.QLabel("0 Selected / 0 Available"); self.selection_label.setObjectName("SecondaryText")
        self.details_button = QtWidgets.QPushButton("View Pool Details"); self.details_button.setObjectName("GhostButton")
        self.details_button.setEnabled(False); self.details_button.clicked.connect(self._show_current_pool_details)
        pool_actions.addWidget(self.selection_label); pool_actions.addStretch(); pool_actions.addWidget(self.details_button)
        targeting.layout.addLayout(pool_actions)
        self.targeting_summary = InlineStatus("No pool data has been synchronized yet.", "neutral")
        self.targeting_summary.setObjectName("EligibilitySummary")
        targeting.layout.addWidget(self.targeting_summary)

        recovery = SectionCard("Recovery & Dependencies", "Configure task recovery and cross-DCC backend job dependencies.")
        recovery_grid = QtWidgets.QGridLayout(); recovery_grid.setHorizontalSpacing(10); recovery_grid.setVerticalSpacing(8)
        self.retry_count = QtWidgets.QSpinBox(); self.retry_count.setRange(0, 20); self.retry_count.setValue(2)
        self.timeout_minutes = QtWidgets.QSpinBox(); self.timeout_minutes.setRange(0, 100000); self.timeout_minutes.setSpecialValueText("No Timeout"); self.timeout_minutes.setSuffix(" min")
        recovery_grid.addWidget(LabeledField("Retry Attempts", self.retry_count, "Number of automatic retries allowed after a task failure."), 0, 0)
        recovery_grid.addWidget(LabeledField("Task Timeout", self.timeout_minutes, "Maximum runtime for one task before the backend marks it as timed out."), 0, 1)

        self.dependency_summary = QtWidgets.QLabel("No dependencies selected")
        self.dependency_summary.setObjectName("SecondaryText")
        self.dependency_summary.setMinimumHeight(30); self.dependency_summary.setWordWrap(True)
        self.browse_dependencies = QtWidgets.QPushButton("Browse Jobs…"); self.browse_dependencies.setObjectName("InfoButton")
        self.browse_dependencies.clicked.connect(self.browseDependenciesRequested.emit)
        self.clear_dependencies = QtWidgets.QPushButton("Clear"); self.clear_dependencies.setObjectName("GhostButton")
        self.clear_dependencies.clicked.connect(self.clear_job_dependencies)
        dependency_row = QtWidgets.QHBoxLayout(); dependency_row.setContentsMargins(0, 0, 0, 0); dependency_row.setSpacing(7)
        dependency_row.addWidget(self.dependency_summary, 1); dependency_row.addWidget(self.browse_dependencies); dependency_row.addWidget(self.clear_dependencies)
        dependency_widget = QtWidgets.QWidget(); dependency_widget.setObjectName("InlineFieldContainer"); dependency_widget.setAutoFillBackground(False); dependency_widget.setLayout(dependency_row)
        recovery_grid.addWidget(LabeledField(
            "Job Dependencies", dependency_widget,
            "Select existing Maya or Houdini RenderHive jobs that must complete before this job can start.",
        ), 1, 0, 1, 2)
        recovery_grid.setColumnStretch(0, 1); recovery_grid.setColumnStretch(1, 1)
        recovery.layout.addLayout(recovery_grid)

        paths = SectionCard("Scene & Project Paths", "Review the HIP and project locations used by farm workers.")
        path_grid = QtWidgets.QGridLayout(); path_grid.setHorizontalSpacing(10); path_grid.setVerticalSpacing(8)
        self.hip_file = ReadOnlyRow("HIP File", tooltip="Current .hip, .hiplc or .hipnc file.")
        self.project_path = ReadOnlyRow("Project Path", tooltip="Uses $JOB when available, otherwise the HIP directory.")
        self.hip_directory = ReadOnlyRow("$HIP")
        self.job_directory = ReadOnlyRow("$JOB")
        path_grid.addWidget(self.hip_file, 0, 0, 1, 2); path_grid.addWidget(self.project_path, 1, 0, 1, 2)
        path_grid.addWidget(self.hip_directory, 2, 0); path_grid.addWidget(self.job_directory, 2, 1)
        path_grid.setColumnStretch(0, 1); path_grid.setColumnStretch(1, 1)
        paths.layout.addLayout(path_grid)

        for card in (details, scheduling, targeting, recovery, paths):
            root.addWidget(card)
        root.addStretch()
        self._update_dependency_summary()

    @staticmethod
    def _context_key(context):
        path = str(getattr(context, "hip_path", "") or "").strip().lower()
        return path or "__untitled__:{}".format(str(getattr(context, "hip_name", "") or ""))

    def set_context(self, context, force_identity=False):
        new_key = self._context_key(context)
        identity_changed = bool(force_identity or new_key != self._scene_key)
        self._context = context; self._scene_key = new_key
        self._houdini_version = str(getattr(context, "houdini_version", "") or "")
        if identity_changed:
            self.project_name.setText(context.project_name or "Houdini Project")
            self.job_name.setText(context.scene_name or "houdini_job")
        elif not self.project_name.text().strip():
            self.project_name.setText(context.project_name or "Houdini Project")
        elif not self.job_name.text().strip():
            self.job_name.setText(context.scene_name or "houdini_job")
        self.hip_file.set_value(context.hip_path or "Unsaved HIP file")
        self.project_path.set_value(context.project_path or "Not Set")
        self.hip_directory.set_value(context.hip_directory or "Not Set")
        self.job_directory.set_value(context.job_directory or "Not Set")
        self._update_targeting_summary()
        return identity_changed

    def set_render_requirements(self, houdini_version="", sources=None):
        if houdini_version:
            self._houdini_version = str(houdini_version)
        self._render_requirements = []
        for source in sources or []:
            if source is None:
                continue
            self._render_requirements.append({
                "execution_mode": str(getattr(source, "execution_mode", "") or ""),
                "renderer": str(getattr(source, "renderer", "") or ""),
            })
        self._update_targeting_summary()

    def set_syncing(self, syncing):
        self.refresh_farm_button.setEnabled(not bool(syncing))
        self.refresh_farm_button.setText("Refreshing…" if syncing else "Refresh")
        if syncing:
            self.backend_chip.setText("Backend: Connecting")

    def set_backend_error(self, message):
        self.backend_chip.setText("Backend: Offline"); apply_status_appearance(self.backend_chip, "error")
        self.targeting_summary.setText(str(message or "Backend connection failed.")); self.targeting_summary.set_level("error")
        self.set_syncing(False)

    @staticmethod
    def _pool_worker_id(value):
        if isinstance(value, dict):
            return str(value.get("id") or value.get("worker_id") or "")
        return str(value or "")

    def _worker_pool_ids(self, worker):
        worker_id = str(worker.get("id") or "")
        ids = set(str(item.get("id") or "") for item in worker.get("pools") or [] if isinstance(item, dict) and item.get("id"))
        for pool in self._pools:
            pool_id = str(pool.get("id") or "")
            member_ids = set(self._pool_worker_id(value) for value in pool.get("workers") or [])
            if worker_id and worker_id in member_ids and pool_id:
                ids.add(pool_id)
        return ids

    def _workers_for_pool(self, pool_id):
        pool_id = str(pool_id or "")
        return [worker for worker in self._workers if pool_id and pool_id in self._worker_pool_ids(worker)]

    def set_farm_data(self, workers, pools, synced_at=""):
        self._workers = list(workers or []); self._pools = list(pools or [])
        online_total = len([worker for worker in self._workers if worker_is_online(worker)])
        self.backend_chip.setText("Backend: Online"); apply_status_appearance(self.backend_chip, "good")
        self.worker_chip.setText("Workers: {} / {} Online".format(online_total, len(self._workers)))
        self.pool_chip.setText("Pools: {}".format(len(self._pools)))
        self.sync_chip.setText("Last Sync: {}".format(synced_at or "Now"))

        checked_ids = set(self.selected_pool_ids()) or set(self._checked_pool_ids)
        available_ids = set(str(pool.get("id") or "") for pool in self._pools if pool.get("id"))
        checked_ids.intersection_update(available_ids); self._checked_pool_ids = set(checked_ids)
        self.pool_list.blockSignals(True); self.pool_list.clear()
        for pool in self._pools:
            pool_id = str(pool.get("id") or "")
            members = self._workers_for_pool(pool_id)
            online = len([worker for worker in members if worker_is_online(worker)])
            item = QtWidgets.QTreeWidgetItem((
                str(pool.get("name") or "Unnamed Pool"), str(online), str(len(members)), str(pool.get("description") or "")
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
        checking_enabled = self.pool_strategy.currentText() != "All Pools"
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
        result = []
        for index in range(self.pool_list.topLevelItemCount()):
            item = self.pool_list.topLevelItem(index)
            value = str(item.data(0, USER_ROLE) or "")
            if value and item.checkState(0) == CHECKED:
                result.append(value)
        return result

    def selected_pool_names(self):
        return [
            str(self.pool_list.topLevelItem(index).text(0) or "")
            for index in range(self.pool_list.topLevelItemCount())
            if self.pool_list.topLevelItem(index).checkState(0) == CHECKED
        ]

    def _pool_from_item(self, item):
        if item is None:
            return None
        pool_id = str(item.data(0, USER_ROLE) or "")
        return next((pool for pool in self._pools if str(pool.get("id") or "") == pool_id), None)

    def _show_pool_details(self, item, column=0):
        pool = self._pool_from_item(item)
        if pool:
            dialog_exec(PoolDetailsDialog(pool, self._workers_for_pool(pool.get("id")), parent=self))

    def _show_current_pool_details(self):
        self._show_pool_details(self.pool_list.currentItem())

    def _worker_is_eligible_for_any_source(self, worker, min_cores, min_memory_mb, min_gpus):
        requirements = self._render_requirements or [{"execution_mode": "", "renderer": ""}]
        for item in requirements:
            renderer = str(item.get("renderer") or "")
            required_gpus = max(int(min_gpus or 0), 1 if "xpu" in renderer.lower() else 0)
            if not worker_meets_requirements(worker, min_cores, min_memory_mb, required_gpus):
                continue
            if worker_supports_houdini(
                worker,
                self._houdini_version,
                item.get("execution_mode"),
                renderer,
            ):
                return True
        return False

    def pool_targeting(self):
        all_ids = [str(pool.get("id") or "") for pool in self._pools if pool.get("id")]
        all_names = [str(pool.get("name") or "") for pool in self._pools if pool.get("name")]
        selected_ids = self.selected_pool_ids(); selected_names = self.selected_pool_names()
        strategy_text = self.pool_strategy.currentText()
        if strategy_text == "Selected Pools Only":
            strategy, effective_ids, effective_names = "selected_only", selected_ids, selected_names
            excluded_ids, excluded_names = [], []
        elif strategy_text == "All Except Selected":
            strategy = "all_except_selected"
            selected_set = set(selected_ids); selected_name_set = set(selected_names)
            effective_ids = [value for value in all_ids if value not in selected_set]
            effective_names = [value for value in all_names if value not in selected_name_set]
            excluded_ids, excluded_names = selected_ids, selected_names
        else:
            strategy, effective_ids, effective_names = "all", all_ids, all_names
            excluded_ids, excluded_names = [], []

        effective_set = set(effective_ids)
        min_cores = self.min_cores.value()
        min_memory_mb = self.min_memory_gb.value() * 1024
        min_gpus = self.min_gpus.value()
        eligible = []
        for worker in self._workers:
            if not worker_is_online(worker):
                continue
            worker_pool_ids = self._worker_pool_ids(worker)
            if effective_set and not worker_pool_ids.intersection(effective_set):
                continue
            if not self._worker_is_eligible_for_any_source(worker, min_cores, min_memory_mb, min_gpus):
                continue
            eligible.append(worker)
        return {
            "strategy": strategy,
            "selected_pool_ids": selected_ids,
            "selected_pool_names": selected_names,
            "excluded_pool_ids": excluded_ids,
            "excluded_pool_names": excluded_names,
            "effective_pool_ids": effective_ids,
            "effective_pool_names": effective_names,
            "eligible_worker_ids": [worker.get("id") for worker in eligible],
            "eligible_worker_count": len(eligible),
            "online_worker_count": len([worker for worker in self._workers if worker_is_online(worker)]),
        }

    def _update_targeting_summary(self, *args):
        data = self.pool_targeting()
        selected_count = len(data.get("selected_pool_ids") or [])
        self.selection_label.setText("{} Selected / {} Available".format(selected_count, len(self._pools)))
        if not self._pools:
            self.targeting_summary.setText("No pool data has been synchronized yet.")
            self.targeting_summary.set_level("neutral")
            return
        if data.get("strategy") == "selected_only" and not data.get("selected_pool_ids"):
            self.targeting_summary.setText("Select at least one pool before submitting.")
            self.targeting_summary.set_level("warning")
            return
        self.targeting_summary.setText(
            "{} eligible / {} online worker(s) across {} effective pool(s).".format(
                data.get("eligible_worker_count", 0),
                data.get("online_worker_count", 0),
                len(data.get("effective_pool_ids") or []),
            )
        )
        self.targeting_summary.set_level("good" if data.get("eligible_worker_count") else "warning")

    def selected_job_dependency_ids(self):
        return list(self._job_dependency_ids)

    def set_job_dependencies(self, ids, records=None):
        values = []
        for value in ids or []:
            clean = str(value or "").strip()
            if clean and clean not in values:
                values.append(clean)
        self._job_dependency_ids = values
        if records is not None:
            self._job_dependency_records = {}
            for record in records or []:
                if not isinstance(record, dict):
                    continue
                job_id = str(record.get("id") or record.get("job_id") or record.get("uid") or "").strip()
                if job_id:
                    self._job_dependency_records[job_id] = dict(record)
        self._update_dependency_summary()

    def clear_job_dependencies(self):
        self.set_job_dependencies([], [])

    def _update_dependency_summary(self):
        if not self._job_dependency_ids:
            self.dependency_summary.setText("No dependencies selected")
            self.clear_dependencies.setEnabled(False)
            return
        labels = []
        for job_id in self._job_dependency_ids:
            record = self._job_dependency_records.get(job_id) or {}
            name = str(record.get("visible_name") or record.get("name") or "").strip()
            labels.append(name or job_id)
        preview = ", ".join(labels[:3])
        if len(labels) > 3:
            preview += " +{} more".format(len(labels) - 3)
        self.dependency_summary.setText("{} selected · {}".format(len(labels), preview))
        self.clear_dependencies.setEnabled(True)

    def job_settings(self):
        return {
            "project_name": self.project_name.text().strip(),
            "job_name": self.job_name.text().strip(),
            "priority": self.priority.value(),
            "department": self.department.text().strip(),
            "comment": self.comment.text().strip(),
            "chunk_size": self.chunk_size.value(),
            "concurrent_tasks": self.concurrent_tasks.value(),
            "retry_count": self.retry_count.value(),
            "timeout_seconds": self.timeout_minutes.value() * 60 if self.timeout_minutes.value() else None,
            "min_cores": self.min_cores.value(),
            "min_memory_mb": self.min_memory_gb.value() * 1024,
            "min_gpus": self.min_gpus.value(),
            "job_dependencies": self.selected_job_dependency_ids(),
        }

    def state_values(self):
        value = self.job_settings()
        value.update({
            "pool_strategy": self.pool_strategy.currentText(),
            "selected_pool_ids": self.selected_pool_ids(),
            "job_dependency_ids": self.selected_job_dependency_ids(),
        })
        return value

    def apply_state(self, data):
        data = dict(data or {})
        if data.get("project_name"):
            self.project_name.setText(str(data.get("project_name")))
        if data.get("job_name"):
            self.job_name.setText(str(data.get("job_name")))
        self.priority.setValue(int(data.get("priority", self.priority.value())))
        self.department.setText(str(data.get("department") or ""))
        self.comment.setText(str(data.get("comment") or ""))
        for widget, key in (
            (self.chunk_size, "chunk_size"),
            (self.concurrent_tasks, "concurrent_tasks"),
            (self.retry_count, "retry_count"),
            (self.min_cores, "min_cores"),
            (self.min_gpus, "min_gpus"),
        ):
            if key in data:
                widget.setValue(int(data.get(key) or 0))
        if "min_memory_mb" in data:
            self.min_memory_gb.setValue(int(data.get("min_memory_mb") or 0) // 1024)
        if "timeout_seconds" in data:
            self.timeout_minutes.setValue(int(data.get("timeout_seconds") or 0) // 60)
        strategy = str(data.get("pool_strategy") or "All Pools")
        if not self.pool_strategy.setCurrentText(strategy):
            self.pool_strategy.setCurrentText("All Pools")
        self._checked_pool_ids = set(str(item) for item in data.get("selected_pool_ids") or [])
        deps = data.get("job_dependency_ids") or data.get("job_dependencies") or []
        self.set_job_dependencies(deps)
        self._update_targeting_summary()
