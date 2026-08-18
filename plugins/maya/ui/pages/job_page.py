from __future__ import print_function

from ..qt_compat import QtWidgets
from ..common_widgets import Card, LabeledField, SegmentedChoice, WorkerStatusChip
from ..targeting_widgets import PoolMultiSelect

def build_job_page(self, register):
    page, body = self.scroll_page(
        "Job Configuration",
        "Configure job metadata, scheduling, pool targeting and delivery options.",
    )

    identity = Card("Job Details", "Identity and ownership information shown in the queue and reports.")
    grid = QtWidgets.QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(8)

    project = register("rh_project_name", QtWidgets.QLineEdit())
    project.setPlaceholderText("Enter the project name")
    job = register("rh_job_name", QtWidgets.QLineEdit())
    job.setPlaceholderText("Enter a descriptive job name")
    priority = register("rh_priority", QtWidgets.QSpinBox())
    priority.setRange(1, 100)
    priority.setValue(50)
    department = register("rh_department", QtWidgets.QLineEdit())
    department.setPlaceholderText("e.g. Lighting, FX or Look Development")
    comment = register("rh_comment", QtWidgets.QLineEdit())
    comment.setPlaceholderText("Optional notes for the render team")

    grid.addWidget(LabeledField("Project", project, "Project label used to organize and report submitted jobs."), 0, 0)
    grid.addWidget(LabeledField("Job Name", job, "Name displayed in the RenderHive queue and reports."), 0, 1)
    grid.addWidget(LabeledField("Priority", priority, "Higher values are scheduled before lower-priority jobs when resources are available."), 1, 0)
    grid.addWidget(LabeledField("Department", department, "Optional department or discipline responsible for this job."), 1, 1)
    grid.addWidget(LabeledField("Notes", comment, "Optional information for artists, operators or supervisors."), 2, 0, 1, 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    identity.layout.addLayout(grid)
    body.addWidget(identity)

    scheduling = Card(
        "Scheduling",
        "Control task chunking, concurrency and scheduler limits.",
    )
    schedule_grid = QtWidgets.QGridLayout()
    schedule_grid.setHorizontalSpacing(10)
    schedule_grid.setVerticalSpacing(8)

    chunk_size = register("rh_chunk_size", QtWidgets.QSpinBox())
    chunk_size.setRange(1, 10000)
    chunk_size.setValue(1)

    concurrent = register("rh_concurrent_tasks", QtWidgets.QSpinBox())
    concurrent.setRange(1, 64)
    concurrent.setValue(1)

    minimum_cores = register("rh_minimum_cores", QtWidgets.QSpinBox())
    minimum_cores.setRange(0, 4096)
    minimum_cores.setSpecialValueText("Any")

    minimum_ram = register("rh_minimum_ram_gb", QtWidgets.QSpinBox())
    minimum_ram.setRange(0, 65536)
    minimum_ram.setSpecialValueText("Any")
    minimum_ram.setSuffix(" GB")

    minimum_gpus = register("rh_minimum_gpus", QtWidgets.QSpinBox())
    minimum_gpus.setRange(0, 64)
    minimum_gpus.setSpecialValueText("Any")

    for requirement_widget in (minimum_cores, minimum_ram, minimum_gpus):
        requirement_widget.valueChanged.connect(self.update_worker_targeting_summary)

    schedule_grid.addWidget(LabeledField("Chunk Size", chunk_size, "Number of consecutive frames assigned to each farm task."), 0, 0)
    schedule_grid.addWidget(LabeledField("Tasks per Worker", concurrent, "Maximum number of tasks from this job that one worker may run concurrently."), 0, 1)
    schedule_grid.addWidget(LabeledField("Minimum CPU Cores", minimum_cores, "Minimum worker CPU core count required by the backend scheduler. Any disables this requirement."), 1, 0)
    schedule_grid.addWidget(LabeledField("Minimum RAM", minimum_ram, "Minimum worker memory required by the backend scheduler. Any disables this requirement."), 1, 1)
    schedule_grid.addWidget(LabeledField("Minimum GPUs", minimum_gpus, "Minimum number of GPUs required on an eligible worker. Any disables this requirement."), 2, 0)
    schedule_grid.setColumnStretch(0, 1)
    schedule_grid.setColumnStretch(1, 1)
    scheduling.layout.addLayout(schedule_grid)
    body.addWidget(scheduling)

    targeting = Card(
        "Pool Selection",
        "Choose which backend worker pools are eligible to receive this job.",
    )

    worker_status_row = QtWidgets.QHBoxLayout()
    worker_status_row.setSpacing(6)
    api_chip = register("worker_api_chip", WorkerStatusChip("Not Synced"))
    worker_chip = register("worker_count_chip", WorkerStatusChip("0 Workers"))
    pool_chip = register("worker_pool_count_chip", WorkerStatusChip("0 Pools"))
    sync_chip = register("worker_sync_time_chip", WorkerStatusChip("Never"))
    sync_workers = register("sync_workers_button", QtWidgets.QPushButton("Refresh"))
    sync_workers.setObjectName("InfoButton")
    sync_workers.clicked.connect(self.sync_available_workers)
    worker_status_row.addWidget(api_chip)
    worker_status_row.addWidget(worker_chip)
    worker_status_row.addWidget(pool_chip)
    worker_status_row.addWidget(sync_chip)
    worker_status_row.addStretch()
    worker_status_row.addWidget(sync_workers)
    targeting.layout.addLayout(worker_status_row)

    target_grid = QtWidgets.QGridLayout()
    target_grid.setHorizontalSpacing(10)
    target_grid.setVerticalSpacing(8)
    strategy = register(
        "rh_pool_strategy",
        SegmentedChoice(["All Pools", "Selected Pools Only", "All Except Selected"]),
    )
    strategy.currentTextChanged.connect(self.on_pool_strategy_changed)
    selected = register("rh_selected_pools", PoolMultiSelect("Selected Pools", "Select Pools"))
    selected.selectionChanged.connect(self.on_selected_pools_changed)
    excluded = register("rh_excluded_pools", PoolMultiSelect("Excluded Pools", "None"))
    excluded.selectionChanged.connect(self.on_excluded_pools_changed)
    selected_field = register("pool_selected_field", LabeledField("Selected Pools", selected))
    excluded_field = register("pool_excluded_field", LabeledField("Excluded Pools", excluded))
    target_grid.addWidget(LabeledField("Assignment Strategy", strategy, "Choose whether the job can use every pool, selected pools only, or all pools except selected ones."),0,0,1,2)
    target_grid.addWidget(selected_field,1,0,1,2)
    target_grid.addWidget(excluded_field,2,0,1,2)
    target_grid.setColumnStretch(0,1)
    target_grid.setColumnStretch(1,1)
    targeting.layout.addLayout(target_grid)

    eligibility = register(
        "worker_eligibility_summary",
        QtWidgets.QLabel("No pool data has been synchronized yet."),
    )
    eligibility.setObjectName("EligibilitySummary")
    eligibility.setWordWrap(True)
    targeting.layout.addWidget(eligibility)
    self.update_pool_selection_widgets()
    self.update_pool_strategy_ui()
    self.update_worker_sync_chips()
    self.update_worker_targeting_summary()
    body.addWidget(targeting)

    delivery = Card("Recovery & Dependencies", "Configure retries, timeouts and backend job dependencies.")
    delivery_grid = QtWidgets.QGridLayout()
    delivery_grid.setHorizontalSpacing(10)
    delivery_grid.setVerticalSpacing(8)

    retry_count = register("rh_retry_count", QtWidgets.QSpinBox())
    retry_count.setRange(0, 20)
    retry_count.setValue(2)

    timeout = register("rh_timeout_minutes", QtWidgets.QSpinBox())
    timeout.setRange(0, 100000)
    timeout.setSpecialValueText("No Timeout")
    timeout.setSuffix(" min")

    # Persist backend UUIDs in a hidden QLineEdit so existing scene-state and
    # task-builder contracts remain stable while artists use the Job browser.
    dependencies = register("rh_job_dependencies", QtWidgets.QLineEdit(page))
    dependencies.setVisible(False)
    dependencies.textChanged.connect(self.update_job_dependency_summary)

    dependency_summary = register(
        "rh_job_dependencies_summary",
        QtWidgets.QLabel("No dependencies selected"),
    )
    dependency_summary.setObjectName("SecondaryText")
    dependency_summary.setMinimumHeight(30)
    dependency_summary.setWordWrap(True)

    browse_dependencies = register(
        "rh_job_dependencies_browse",
        QtWidgets.QPushButton("Browse Jobs…"),
    )
    browse_dependencies.setObjectName("InfoButton")
    browse_dependencies.clicked.connect(self.open_job_dependency_browser)

    clear_dependencies = register(
        "rh_job_dependencies_clear",
        QtWidgets.QPushButton("Clear"),
    )
    clear_dependencies.setObjectName("GhostButton")
    clear_dependencies.clicked.connect(self.clear_job_dependencies)

    dependency_row = QtWidgets.QHBoxLayout()
    dependency_row.setContentsMargins(0, 0, 0, 0)
    dependency_row.setSpacing(7)
    dependency_row.addWidget(dependency_summary, 1)
    dependency_row.addWidget(browse_dependencies)
    dependency_row.addWidget(clear_dependencies)
    dependency_widget = QtWidgets.QWidget()
    dependency_widget.setObjectName("InlineFieldContainer")
    dependency_widget.setAutoFillBackground(False)
    dependency_widget.setLayout(dependency_row)

    delivery_grid.addWidget(LabeledField("Retry Attempts", retry_count, "Number of automatic retries allowed after a task failure."), 0, 0)
    delivery_grid.addWidget(LabeledField("Task Timeout", timeout, "Maximum runtime for one task before the backend marks it as timed out."), 0, 1)
    delivery_grid.addWidget(LabeledField("Job Dependencies", dependency_widget, "Select existing RenderHive jobs that must complete before this job can start."), 1, 0, 1, 2)
    self.update_job_dependency_summary()
    delivery_grid.setColumnStretch(0, 1)
    delivery_grid.setColumnStretch(1, 1)
    delivery.layout.addLayout(delivery_grid)
    body.addWidget(delivery)

    paths = Card("File Paths", "Review the scene, project and output locations used by farm workers.")

    scene_path = register("rh_scene_path", QtWidgets.QLineEdit())
    project_path = register("rh_project_path", QtWidgets.QLineEdit())
    output_path = register("rh_output_path", QtWidgets.QLineEdit())

    for widget in (scene_path, project_path, output_path):
        widget.setClearButtonEnabled(True)

    paths.layout.addWidget(LabeledField("Scene File", scene_path, "Maya scene file submitted to the farm."))
    paths.layout.addWidget(LabeledField("Project Root", project_path, "Maya project root used to resolve relative paths and dependencies."))

    output_row = QtWidgets.QHBoxLayout()
    output_row.setContentsMargins(0, 0, 0, 0)
    output_row.setSpacing(7)
    output_row.addWidget(output_path, 1)

    browse = QtWidgets.QPushButton("Browse…")
    browse.clicked.connect(self.api.browse_output_path)
    output_row.addWidget(browse)

    output_widget = QtWidgets.QWidget()
    output_widget.setLayout(output_row)
    paths.layout.addWidget(LabeledField("Output Directory", output_widget, "Destination directory accessible to RenderHive workers."))

    utility_row = QtWidgets.QHBoxLayout()
    utility_row.setSpacing(7)

    open_output = QtWidgets.QPushButton("Open Output Folder")
    open_output.setObjectName("GhostButton")
    open_output.clicked.connect(
        self.api.open_output_folder
    )

    sync_scene = QtWidgets.QPushButton("Sync Scene Settings")
    sync_scene.setObjectName("InfoButton")
    sync_scene.clicked.connect(self.sync_from_scene)

    utility_row.addWidget(open_output)
    utility_row.addStretch()
    utility_row.addWidget(sync_scene)
    paths.layout.addLayout(utility_row)

    body.addWidget(paths)
    body.addStretch()
    return page

