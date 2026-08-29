"""Job configuration, scheduling and pool targeting view for RenderHive Maya Submitter."""

from __future__ import print_function

from ..qt_compat import QtCore, QtWidgets
from ..common_widgets import (
    Card,
    LabeledField,
    ScrollFilter,
    SegmentedChoice,
    StepperNumberInput,
    WorkerStatusChip,
    PathBox,
)
from ..targeting_widgets import PoolMultiSelect
from ..icons import get_icon
from ..qt_theme import COLORS


def build_job_page(self, register):
    page, body = self.scroll_page(
        "Job Configuration",
        "Configure job metadata, scheduling, pool targeting and delivery options.",
    )

    identity = Card("Job Details", "Identity and ownership information shown in the queue and reports.")
    grid = QtWidgets.QGridLayout()
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(5)

    project = register("rh_project_name", QtWidgets.QLineEdit())
    project.setPlaceholderText("Enter the project name")
    ScrollFilter.install(project)

    job = register("rh_job_name", QtWidgets.QLineEdit())
    job.setPlaceholderText("Enter a descriptive job name")
    ScrollFilter.install(job)

    priority = register("rh_priority", StepperNumberInput(minimum=1, maximum=100, default=50))
    
    department = register("rh_department", QtWidgets.QLineEdit())
    department.setPlaceholderText("e.g. Lighting, FX or Look Development")
    ScrollFilter.install(department)

    submission_mode = register("rh_submission_mode", SegmentedChoice(["Shared Storage", "Server Repository Staging"]))

    comment = register("rh_comment", QtWidgets.QLineEdit())
    comment.setPlaceholderText("Optional notes for the render team")
    ScrollFilter.install(comment)

    grid.addWidget(LabeledField("Project", project), 0, 0)
    grid.addWidget(LabeledField("Job Name", job), 0, 1)
    grid.addWidget(LabeledField("Priority", priority, "Higher values schedule first when farm capacity is shared across jobs."), 1, 0)
    grid.addWidget(LabeledField("Department", department), 1, 1)
    grid.addWidget(LabeledField("Storage & Staging Mode", submission_mode, "Choose Shared Storage for network mount paths, or Server Repository Staging to stage scene files directly to the server like Deadline."), 2, 0, 1, 2)
    grid.addWidget(LabeledField("Notes", comment), 3, 0, 1, 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    identity.layout.addLayout(grid)
    body.addWidget(identity)

    scheduling = Card(
        "Scheduling",
        "Control task chunking, concurrency and scheduler limits.",
    )
    schedule_grid = QtWidgets.QGridLayout()
    schedule_grid.setHorizontalSpacing(8)
    schedule_grid.setVerticalSpacing(5)

    chunk_size = register("rh_chunk_size", StepperNumberInput(minimum=1, maximum=10000, default=1))
    concurrent = register("rh_concurrent_tasks", StepperNumberInput(minimum=1, maximum=64, default=1))
    minimum_cores = register("rh_minimum_cores", StepperNumberInput(minimum=0, maximum=4096, default=0, special_value_text="Any"))
    minimum_ram = register("rh_minimum_ram_gb", StepperNumberInput(minimum=0, maximum=65536, default=0, suffix=" GB", special_value_text="Any"))
    minimum_gpus = register("rh_minimum_gpus", StepperNumberInput(minimum=0, maximum=64, default=0, special_value_text="Any"))

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
    sync_workers = register("sync_workers_button", QtWidgets.QPushButton("  Refresh"))
    sync_workers.setObjectName("SecondaryBtn")
    sync_workers.setIcon(get_icon("refresh", "#CBD5E1", 13))
    sync_workers.setCursor(QtCore.Qt.PointingHandCursor)
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
    target_grid.addWidget(LabeledField("Assignment Strategy", strategy, "Choose whether the job can use every pool, selected pools only, or all pools except selected ones."), 0, 0, 1, 2)
    target_grid.addWidget(selected_field, 1, 0, 1, 2)
    target_grid.addWidget(excluded_field, 2, 0, 1, 2)
    target_grid.setColumnStretch(0, 1)
    target_grid.setColumnStretch(1, 1)
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

    retry_count = register("rh_retry_count", StepperNumberInput(minimum=0, maximum=20, default=2))
    timeout = register("rh_timeout_minutes", StepperNumberInput(minimum=0, maximum=100000, default=0, suffix=" min", special_value_text="No Timeout"))

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
    browse_dependencies.setObjectName("SecondaryBtn")
    browse_dependencies.setIcon(get_icon("search", "#CBD5E1", 13))
    browse_dependencies.setCursor(QtCore.Qt.PointingHandCursor)
    browse_dependencies.clicked.connect(self.open_job_dependency_browser)

    clear_dependencies = register(
        "rh_job_dependencies_clear",
        QtWidgets.QPushButton("  Clear"),
    )
    clear_dependencies.setObjectName("GhostBtn")
    clear_dependencies.setIcon(get_icon("x", COLORS["muted"], 13))
    clear_dependencies.setCursor(QtCore.Qt.PointingHandCursor)
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

    scene_path = register("rh_scene_path", PathBox(file_mode=True))
    project_path = register("rh_project_path", PathBox())
    output_path = register("rh_output_path", PathBox())

    if hasattr(self.api, "browse_scene_path"):
        scene_path.browse_btn.clicked.connect(self.api.browse_scene_path)
    if hasattr(self.api, "browse_project_path"):
        project_path.browse_btn.clicked.connect(self.api.browse_project_path)
    if hasattr(self.api, "browse_output_path"):
        output_path.browse_btn.clicked.connect(self.api.browse_output_path)

    paths.layout.addWidget(LabeledField("Scene File", scene_path))
    paths.layout.addWidget(LabeledField("Project Root", project_path))
    paths.layout.addWidget(LabeledField("Output Directory", output_path))

    utility_row = QtWidgets.QHBoxLayout()
    utility_row.setSpacing(7)

    open_output = QtWidgets.QPushButton("  Open Output Folder")
    open_output.setObjectName("GhostBtn")
    open_output.setIcon(get_icon("folder", "#CBD5E1", 13))
    open_output.setCursor(QtCore.Qt.PointingHandCursor)
    open_output.clicked.connect(self.api.open_output_folder)

    sync_scene = QtWidgets.QPushButton("  Sync Scene Settings")
    sync_scene.setObjectName("SecondaryBtn")
    sync_scene.setIcon(get_icon("refresh", "#CBD5E1", 13))
    sync_scene.setCursor(QtCore.Qt.PointingHandCursor)
    sync_scene.clicked.connect(self.sync_from_scene)

    utility_row.addWidget(open_output)
    utility_row.addStretch()
    utility_row.addWidget(sync_scene)
    paths.layout.addLayout(utility_row)

    body.addWidget(paths)
    body.addStretch()
    return page
