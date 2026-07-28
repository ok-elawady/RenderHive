import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import (
    CASCADE,
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    Index,
    IntegerField,
    JSONField,
    PositiveIntegerField,
    TextChoices,
    TextField,
    UUIDField,
)


class JobState(TextChoices):
    PENDING = "PENDING", "Pending"  # Queued, not yet dispatching
    RUNNING = "RUNNING", "Running"  # At least one frame is active
    FINISHED = "FINISHED", "Finished"  # All frames succeeded
    FAILED = "FAILED", "Failed"  # One or more frames failed beyond retries
    PAUSED = "PAUSED", "Paused"  # Operator-suspended


class LayerType(TextChoices):
    RENDER = "RENDER", "Render"  # Standard render pass (beauty, shadow, AO, etc.)
    UTIL = "UTIL", "Utility"  # Pre/post processing script (file move, convert, etc.)
    POST = "POST", "Post"  # Composite or delivery step (Nuke, FFmpeg, etc.)


class TaskState(TextChoices):
    WAITING = "WAITING", "Waiting"  # Blocked by unresolved dependencies
    READY = "READY", "Ready"  # Unblocked, awaiting a free Worker
    RUNNING = "RUNNING", "Running"  # Actively executing on a Worker
    CHECKPOINT = "CHECKPOINT", "Checkpointing"  # Saving intermediate progress (e.g. V-Ray resume)
    SUCCEEDED = "SUCCEEDED", "Succeeded"  # Completed with exit code 0
    FAILED = "FAILED", "Failed"  # Terminated with non-zero exit status
    SKIPPED = "SKIPPED", "Skipped"  # Failed but dismissed by a supervisor; unblocks dependents
    # SKIPPED: supervisor acknowledges the failure and removes the task from retry.
    # The job can reach FINISHED even with skipped tasks.


class DependencyType(TextChoices):
    JOB_ON_JOB = "JOB_ON_JOB", "Job on Job"
    LAYER_ON_LAYER = "LAYER_ON_LAYER", "Layer on Layer"
    TASK_ON_TASK = "TASK_ON_TASK", "Task on Task"


class Job(models.Model):
    """The top-level submission entity for a render.

    Attributes:
        id: UUID primary key.
        name: System-generated stable identifier.
        visible_name: Human-readable label shown in the UI.
        project: Active show or production segment.
        department: Department name (e.g. Lighting, FX).
        user: The submitter's display name.
        submitted_by: FK to User if submitted via the web.
        state: Current execution state.
        is_paused: Standalone pause flag.
        priority: Dispatch priority (1-100).
        max_tasks_per_worker: Concurrent tasks per worker limit.
        log_directory: Absolute path for task logs.
        total_tasks: Counter cache.
        waiting_tasks: Counter cache.
        ready_tasks: Counter cache.
        running_tasks: Counter cache.
        succeeded_tasks: Counter cache.
        failed_tasks: Counter cache.
        skipped_tasks: Counter cache.
        depend_tasks: Counter cache.
        created_at: Timestamp.
        updated_at: Timestamp.
        stopped_at: Timestamp when state became FINISHED or FAILED.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = CharField(max_length=255, unique=True, db_index=True)
    visible_name = CharField(max_length=255, blank=True)

    project = CharField(max_length=64, db_index=True)
    department = CharField(max_length=64, blank=True, db_index=True)

    user = CharField(
        max_length=64,
        db_index=True,
        help_text=(
            "The submitter's display name. Defaults to the OS username in the DCC "
            "plugin but is manually editable. Matches Deadline's UserName field."
        ),
    )

    submitted_by = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_jobs",
        help_text="Populated ONLY when submitted via the web frontend. NULL for DCC plugin submissions.",
    )

    state = CharField(max_length=16, choices=JobState.choices, default=JobState.PENDING, db_index=True)
    is_paused = BooleanField(default=False)

    priority = IntegerField(default=50, db_index=True, validators=[MinValueValidator(1), MaxValueValidator(100)])

    max_tasks_per_worker = PositiveIntegerField(
        default=1,
        verbose_name="max concurrent tasks per worker",
        help_text=(
            "Limits how many tasks from this job a single machine can run at once. "
            "Used to prevent a single job from monopolizing nodes with high core counts."
        ),
    )

    log_directory = CharField(max_length=2048)

    total_tasks = IntegerField(default=0)
    waiting_tasks = IntegerField(default=0)
    ready_tasks = IntegerField(default=0)
    running_tasks = IntegerField(default=0)
    succeeded_tasks = IntegerField(default=0)
    failed_tasks = IntegerField(default=0)
    skipped_tasks = IntegerField(default=0)
    depend_tasks = IntegerField(default=0)

    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    stopped_at = DateTimeField(null=True, blank=True)

    included_pools = models.ManyToManyField(
        "workers.WorkerPool",
        blank=True,
        related_name="included_jobs",
        help_text="If specified, only workers in these pools can process this job.",
    )
    excluded_pools = models.ManyToManyField(
        "workers.WorkerPool",
        blank=True,
        related_name="excluded_jobs",
        help_text="If specified, workers in these pools are strictly prevented from processing this job.",
    )

    class Meta:
        verbose_name = "job"
        verbose_name_plural = "jobs"
        ordering = ["-priority", "created_at"]
        indexes = [
            Index(fields=["state", "priority"]),
            Index(fields=["project", "state"]),
            Index(fields=["user", "state"]),
        ]

    def save(self, *args, **kwargs):
        if not self.name:
            from apps.jobs.services import generate_job_name

            self.name = generate_job_name(
                project=self.project or "unknown",
                user=self.user or "unknown",
                visible_name=self.visible_name or "job",
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # ManyToMany fields cannot be queried before the instance is saved to the DB.
        # We use `_state.adding` (Django's canonical unsaved-instance flag) instead of
        # `self.pk`, because UUIDField assigns a pk at Python instantiation time —
        # making `self.pk` always truthy even for brand-new, unsaved instances.
        if not self._state.adding:
            intersection = set(self.included_pools.values_list("pk", flat=True)) & set(
                self.excluded_pools.values_list("pk", flat=True)
            )
            if intersection:
                raise ValidationError({"included_pools": "A pool cannot be both included and excluded."})

    def __str__(self):
        return self.name


class Layer(models.Model):
    """A collection of frames that share the same command, requirements, and state.

    Attributes:
        id: UUID primary key.
        job: FK to parent Job.
        name: Name of the layer (e.g. 'beauty').
        layer_type: Dispatch and execution type.
        command: Base command template.
        frame_range: VFX frame range descriptor.
        chunk_size: Consecutive frames batched into one Frame.
        min_cores: Minimum CPU cores.
        min_memory_mb: Minimum RAM in MB.
        min_gpus: Minimum GPU count.
        tags: Worker compatibility tags array.
        scene_path: DCC scene file path.
        scene_info: DCC scene metadata JSON.
        env: Environment variable overrides JSON.
        max_retries: Per-task retry ceiling.
        timeout_seconds: Task execution timeout.
        state: Layer-level state.
        total_tasks: Counter cache.
        waiting_tasks: Counter cache.
        ready_tasks: Counter cache.
        running_tasks: Counter cache.
        succeeded_tasks: Counter cache.
        failed_tasks: Counter cache.
        skipped_tasks: Counter cache.
        depend_tasks: Counter cache.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = ForeignKey(Job, on_delete=CASCADE, related_name="layers")
    name = CharField(max_length=256)

    layer_type = CharField(
        max_length=8, choices=LayerType.choices, default=LayerType.RENDER, verbose_name="render pass type"
    )

    command = TextField()
    frame_range = CharField(max_length=1024)
    chunk_size = PositiveIntegerField(
        default=1,
        verbose_name="frames per chunk",
        help_text=(
            "Groups this many consecutive frames into a single worker task. High values "
            "reduce startup overhead for fast-rendering frames (e.g. comp, playblasts)."
        ),
    )

    min_cores = PositiveIntegerField(default=1, verbose_name="minimum CPU cores")
    min_memory_mb = PositiveIntegerField(default=4096, verbose_name="minimum memory (MB)")
    min_gpus = PositiveIntegerField(default=0, verbose_name="minimum GPUs")
    tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)

    scene_path = CharField(max_length=2048, blank=True)
    scene_info = JSONField(default=dict, blank=True, verbose_name="scene metadata")
    env = JSONField(default=dict, blank=True)

    max_retries = PositiveIntegerField(default=3)
    timeout_seconds = PositiveIntegerField(null=True, blank=True)

    state = CharField(max_length=16, choices=JobState.choices, default=JobState.PENDING, db_index=True)

    total_tasks = IntegerField(default=0)
    waiting_tasks = IntegerField(default=0)
    ready_tasks = IntegerField(default=0)
    running_tasks = IntegerField(default=0)
    succeeded_tasks = IntegerField(default=0)
    failed_tasks = IntegerField(default=0)
    skipped_tasks = IntegerField(default=0)
    depend_tasks = IntegerField(default=0)

    class Meta:
        verbose_name = "layer"
        verbose_name_plural = "layers"
        unique_together = ("job", "name")
        indexes = [
            Index(fields=["job", "state"]),
        ]

    def __str__(self):
        return f"{self.job.name} / {self.name}"


class Task(models.Model):
    """The smallest schedulable unit of work within a Layer.

    Attributes:
        id: UUID primary key.
        layer: The parent Layer this task belongs to.
        job: Denormalized FK to the parent Job for bulk operations.
        name: Derived display name, e.g. 'beauty_0042'.
        frame_start: The first render frame in this task's chunk.
        frame_end: The last render frame in this task's chunk.
        dispatch_order: Scheduler dispatch priority within the layer.
        state: Current execution state.
        depend_count: Counter of unresolved blocking dependencies.
        retries: Number of execution attempts so far.
        max_retries: Maximum allowed attempts before transitioning to FAILED.
        checkpoint_count: Number of resume checkpoints saved (e.g. V-Ray .vrimg).
        exit_status: Process exit code. -1 = not yet run.
        max_memory_used_mb: Peak RSS memory in MB reported by the Worker.
        cores_used: Actual CPU cores reserved at dispatch time.
        worker_name: Hostname of the executing Worker.
        started_at: Timestamp when execution began.
        stopped_at: Timestamp when execution ended.
        updated_at: Last modification timestamp.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    layer = ForeignKey(Layer, on_delete=CASCADE, related_name="tasks")
    job = ForeignKey(Job, on_delete=CASCADE, related_name="tasks")

    name = CharField(max_length=256)
    frame_start = IntegerField(db_index=True)
    frame_end = IntegerField(db_index=True)
    dispatch_order = IntegerField(
        default=0, db_index=True, help_text="Scheduler priority within the layer. Lower numbers are dispatched first."
    )

    state = CharField(max_length=16, choices=TaskState.choices, default=TaskState.WAITING, db_index=True)

    depend_count = IntegerField(default=0, db_index=True, verbose_name="dependency count")

    retries = PositiveIntegerField(default=0)
    max_retries = PositiveIntegerField(default=3)
    checkpoint_count = PositiveIntegerField(
        default=0,
        help_text=(
            "How many times the worker has reported saving intermediate progress (useful for resuming aborted tasks)."
        ),
    )

    exit_status = IntegerField(
        default=-1, help_text="Raw process exit code returned by the worker. -1 means the task has not completed."
    )

    max_memory_used_mb = PositiveIntegerField(default=0, verbose_name="peak memory used (MB)")
    cores_used = PositiveIntegerField(null=True, blank=True)
    worker_name = CharField(max_length=256, null=True, blank=True, verbose_name="worker hostname")

    started_at = DateTimeField(null=True, blank=True)
    stopped_at = DateTimeField(null=True, blank=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "task"
        verbose_name_plural = "tasks"
        unique_together = ("layer", "frame_start", "frame_end")
        indexes = [
            Index(fields=["job", "state"]),
            Index(fields=["layer", "state"]),
            Index(fields=["state", "depend_count"]),
        ]

    def __str__(self):
        return self.name


class Dependency(models.Model):
    """Represents a blocking requirement between entities.

    Attributes:
        id: UUID primary key.
        type: Dependency kind (TASK_ON_TASK, LAYER_ON_LAYER, JOB_ON_JOB).
        dep_job: The blocked Job.
        dep_layer: The blocked Layer (optional).
        dep_task: The blocked Task (optional).
        parent_job: The blocking Job.
        parent_layer: The blocking Layer (optional).
        parent_task: The blocking Task (optional).
        is_satisfied: Status flag.
        created_at: Creation timestamp.
        satisfied_at: Satisfaction timestamp.
    """

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = CharField(max_length=24, choices=DependencyType.choices, db_index=True)

    dep_job = ForeignKey(
        Job,
        on_delete=CASCADE,
        related_name="blocked_dependencies",
        verbose_name="blocked job",
        help_text="The job that is WAITING. It cannot start until the blocking (parent) entity completes.",
    )
    dep_layer = ForeignKey(
        Layer,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="blocked_dependencies",
        verbose_name="blocked layer",
        help_text="The specific layer that is WAITING (required for LAYER_ON_LAYER dependencies).",
    )
    dep_task = ForeignKey(
        Task,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="blocked_dependencies",
        verbose_name="blocked task",
        help_text="The specific task that is WAITING (required for TASK_ON_TASK dependencies).",
    )

    parent_job = ForeignKey(
        Job,
        on_delete=CASCADE,
        related_name="blocking_dependencies",
        verbose_name="blocking job",
        help_text="The job that must complete FIRST before the blocked entity is released.",
    )
    parent_layer = ForeignKey(
        Layer,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="blocking_dependencies",
        verbose_name="blocking layer",
        help_text="The specific layer that must complete FIRST (required for LAYER_ON_LAYER dependencies).",
    )
    parent_task = ForeignKey(
        Task,
        on_delete=CASCADE,
        null=True,
        blank=True,
        related_name="blocking_dependencies",
        verbose_name="blocking task",
        help_text="The specific task that must complete FIRST (required for TASK_ON_TASK dependencies).",
    )

    is_satisfied = BooleanField(default=False, db_index=True)
    created_at = DateTimeField(auto_now_add=True)
    satisfied_at = DateTimeField(null=True, blank=True)

    def clean(self):
        if self.type == DependencyType.TASK_ON_TASK:
            if not self.dep_task_id or not self.parent_task_id:
                raise ValidationError("TASK_ON_TASK dependency requires both dep_task and parent_task.")
            if self.dep_task_id == self.parent_task_id:
                raise ValidationError("A task cannot depend on itself.")
        elif self.type == DependencyType.LAYER_ON_LAYER:
            if not self.dep_layer_id or not self.parent_layer_id:
                raise ValidationError("LAYER_ON_LAYER dependency requires both dep_layer and parent_layer.")
        elif self.type == DependencyType.JOB_ON_JOB:
            if not self.dep_job_id or not self.parent_job_id:
                raise ValidationError("JOB_ON_JOB dependency requires both dep_job and parent_job.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "dependency"
        verbose_name_plural = "dependencies"
        indexes = [
            Index(fields=["parent_task", "is_satisfied"]),
            Index(fields=["parent_layer", "is_satisfied"]),
            Index(fields=["parent_job", "is_satisfied"]),
            Index(fields=["dep_task", "is_satisfied"]),
            Index(fields=["dep_layer", "is_satisfied"]),
        ]
