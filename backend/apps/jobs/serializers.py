"""
Serializers for the jobs app REST API.

Serializers are split by usage pattern:
- List serializers: slim, read-only representations for list views.
- Detail serializers: full read-only representations for retrieve views.
- Create serializers: write-only, used for POST endpoints.
- Patch serializers: write-only, limited fields for PATCH endpoints.
- Action serializers: write-only, used for task state transition endpoints.
"""

from rest_framework import serializers

from .models import Dependency, DependencyType, Task, Job, Layer
from .services import check_dependency_cycle, create_job_with_layers

# ── Dependency Serializers ────────────────────────────────────────────────────


class DependencyReadSerializer(serializers.ModelSerializer):
    """Full read-only representation of a Dependency.

    Attributes:
        id: UUID primary key.
        type: Dependency kind (TASK_ON_TASK, LAYER_ON_LAYER, JOB_ON_JOB).
        dep_job: The blocked Job UUID.
        dep_layer: The blocked Layer UUID (if applicable).
        dep_task: The blocked Task UUID (if applicable).
        parent_job: The blocking Job UUID.
        parent_layer: The blocking Layer UUID (if applicable).
        parent_task: The blocking Task UUID (if applicable).
        is_satisfied: True once the blocking entity has completed.
        created_at: Creation timestamp.
        satisfied_at: Satisfaction timestamp.
    """
    dep_job_name = serializers.ReadOnlyField(source="dep_job.name")
    dep_layer_name = serializers.ReadOnlyField(source="dep_layer.name")
    dep_task_name = serializers.ReadOnlyField(source="dep_task.name")
    parent_job_name = serializers.ReadOnlyField(source="parent_job.name")
    parent_layer_name = serializers.ReadOnlyField(source="parent_layer.name")
    parent_task_name = serializers.ReadOnlyField(source="parent_task.name")

    class Meta:
        model = Dependency
        fields = [
            "id",
            "type",
            "dep_job",
            "dep_job_name",
            "dep_layer",
            "dep_layer_name",
            "dep_task",
            "dep_task_name",
            "parent_job",
            "parent_job_name",
            "parent_layer",
            "parent_layer_name",
            "parent_task",
            "parent_task_name",
            "is_satisfied",
            "created_at",
            "satisfied_at",
        ]
        read_only_fields = fields


class DependencyCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer for creating a new Dependency.

    Validates that the dependency type matches the provided FKs, that no
    self-dependency is introduced, and that adding the edge would not form
    a cycle in the dependency graph.

    Attributes:
        type: Dependency kind (TASK_ON_TASK, LAYER_ON_LAYER, JOB_ON_JOB).
        dep_job: The blocked Job.
        dep_layer: The blocked Layer (required for LAYER_ON_LAYER).
        dep_task: The blocked Task (required for TASK_ON_TASK).
        parent_job: The blocking Job.
        parent_layer: The blocking Layer (required for LAYER_ON_LAYER).
        parent_task: The blocking Task (required for TASK_ON_TASK).
    """

    class Meta:
        model = Dependency
        fields = [
            "type",
            "dep_job",
            "dep_layer",
            "dep_task",
            "parent_job",
            "parent_layer",
            "parent_task",
        ]

    def validate(self, data: dict) -> dict:
        dep_type = data.get("type")

        # ── Type-specific FK checks (mirrors model.clean()) ────────────────────
        if dep_type == DependencyType.TASK_ON_TASK:
            if not data.get("dep_task") or not data.get("parent_task"):
                raise serializers.ValidationError(
                    "TASK_ON_TASK dependency requires both dep_task and parent_task."
                )
            if data["dep_task"].pk == data["parent_task"].pk:
                raise serializers.ValidationError("A task cannot depend on itself.")
        elif dep_type == DependencyType.LAYER_ON_LAYER:
            if not data.get("dep_layer") or not data.get("parent_layer"):
                raise serializers.ValidationError(
                    "LAYER_ON_LAYER dependency requires both dep_layer and parent_layer."
                )
            if data["dep_layer"].pk == data["parent_layer"].pk:
                raise serializers.ValidationError("A layer cannot depend on itself.")
        elif dep_type == DependencyType.JOB_ON_JOB:
            if not data.get("dep_job") or not data.get("parent_job"):
                raise serializers.ValidationError(
                    "JOB_ON_JOB dependency requires both dep_job and parent_job."
                )
            if data["dep_job"].pk == data["parent_job"].pk:
                raise serializers.ValidationError("A job cannot depend on itself.")

        # ── Cycle detection ────────────────────────────────────────────────────
        entity_type_map = {
            DependencyType.TASK_ON_TASK: ("task", "dep_task", "parent_task"),
            DependencyType.LAYER_ON_LAYER: ("layer", "dep_layer", "parent_layer"),
            DependencyType.JOB_ON_JOB: ("job", "dep_job", "parent_job"),
        }
        entity_type, dep_key, parent_key = entity_type_map[dep_type]
        dep_entity = data.get(dep_key)
        parent_entity = data.get(parent_key)

        if dep_entity and parent_entity:
            if check_dependency_cycle(dep_entity.pk, parent_entity.pk, entity_type):
                raise serializers.ValidationError(
                    f"Adding this dependency would create a cycle in the {entity_type} dependency graph."
                )

        return data


# ── Job Dependency Spec Serializer ──────────────────────────────────────────────

class JobDependencySpecSerializer(serializers.Serializer):
    """Nested serializer for declaring JOB_ON_JOB deps at job submission.

    Attributes:
        parent_job: The UUID of the job that must finish first.
        parent_layer: The name of the layer that must finish first (optional).
        dep_layer: The name of the layer that is blocked (optional).
    """

    type = serializers.CharField(default="JOB_ON_JOB")
    parent_job = serializers.UUIDField(
        help_text="UUID of the job that must complete first (the blocker)."
    )
    parent_layer = serializers.CharField(
        max_length=256, 
        allow_null=True, 
        required=False,
        help_text="Optional name of the specific layer in the parent job that must complete."
    )
    dep_layer = serializers.CharField(
        max_length=256,
        allow_null=True,
        required=False,
        help_text="Optional name of the specific layer in this job that is blocked."
    )

    def validate(self, data: dict) -> dict:
        return data


# ── Task Serializers ─────────────────────────────────────────────────────────


class TaskListSerializer(serializers.ModelSerializer):
    """Slim read-only task representation for list views.

    Attributes:
        id: UUID primary key.
        name: Display name (e.g. 'beauty_0042').
        frame_start: First render frame index.
        frame_end: Last render frame index.
        state: Current execution state.
        depend_count: Number of unresolved dependencies.
        retries: Execution attempt count.
        worker_name: Hostname of the executing Worker.
        exit_status: Process exit code (-1 if not yet run).
        started_at: Execution start timestamp.
        stopped_at: Execution stop timestamp.
    """

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "frame_start",
            "frame_end",
            "state",
            "depend_count",
            "retries",
            "worker_name",
            "exit_status",
            "started_at",
            "stopped_at",
        ]
        read_only_fields = fields


class TaskDetailSerializer(TaskListSerializer):
    """Full read-only task representation for detail and Worker poll views.

    Extends :class:`TaskListSerializer` with execution telemetry fields.

    Attributes:
        max_memory_used_mb: Peak RSS memory in MB.
        cores_used: CPU cores reserved at dispatch time.
        checkpoint_count: Number of resume checkpoints saved.
        dispatch_order: Dispatch priority within the layer.
    """

    class Meta(TaskListSerializer.Meta):
        fields = TaskListSerializer.Meta.fields + [
            "max_memory_used_mb",
            "cores_used",
            "checkpoint_count",
            "dispatch_order",
        ]
        read_only_fields = fields


# ── Layer Serializers ─────────────────────────────────────────────────────────


class LayerListSerializer(serializers.ModelSerializer):
    """Slim read-only layer representation for list views.

    Attributes:
        id: UUID primary key.
        name: Layer name (e.g. 'beauty').
        layer_type: Render pass type.
        state: Current execution state.
        frame_range: VFX frame range descriptor.
        total_tasks: Counter cache.
        waiting_tasks: Counter cache.
        ready_tasks: Counter cache.
        running_tasks: Counter cache.
        succeeded_tasks: Counter cache.
        failed_tasks: Counter cache.
        skipped_tasks: Counter cache.
        depend_tasks: Counter cache.
    """

    class Meta:
        model = Layer
        fields = [
            "id",
            "name",
            "layer_type",
            "state",
            "frame_range",
            "total_tasks",
            "waiting_tasks",
            "ready_tasks",
            "running_tasks",
            "succeeded_tasks",
            "failed_tasks",
            "skipped_tasks",
            "depend_tasks",
        ]
        read_only_fields = fields


class LayerDetailSerializer(LayerListSerializer):
    """Full read-only layer representation for detail views.

    Extends :class:`LayerListSerializer` with command, resource, and scene fields.

    Attributes:
        command: Base command template.
        chunk_size: Frames per chunk.
        min_cores: Minimum CPU cores.
        min_memory_mb: Minimum RAM in MB.
        min_gpus: Minimum GPU count.
        tags: Worker compatibility tags.
        scene_path: DCC scene file path.
        scene_info: DCC scene metadata JSON.
        env: Environment variable overrides.
        max_retries: Per-task retry ceiling.
        timeout_seconds: Task execution timeout.
    """

    class Meta(LayerListSerializer.Meta):
        fields = LayerListSerializer.Meta.fields + [
            "command",
            "chunk_size",
            "min_cores",
            "min_memory_mb",
            "min_gpus",
            "tags",
            "scene_path",
            "scene_info",
            "env",
            "max_retries",
            "timeout_seconds",
        ]
        read_only_fields = fields


class LayerCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer for layer data nested inside a job submission.

    Validates the ``frame_range`` by attempting to parse it via the service
    layer before the job is committed to the database.

    Attributes:
        name: Layer name.
        layer_type: Render pass type.
        command: Base command template.
        frame_range: VFX frame range descriptor.
        chunk_size: Frames per chunk.
        min_cores: Minimum CPU cores.
        min_memory_mb: Minimum RAM in MB.
        min_gpus: Minimum GPU count.
        tags: Worker compatibility tags.
        scene_path: DCC scene file path.
        scene_info: DCC scene metadata JSON.
        env: Environment variable overrides.
        max_retries: Per-task retry ceiling.
        timeout_seconds: Task execution timeout.
        execution_mode: Dependency logic mode.
        depends_on_layer: The layer name to wait for (if WAIT_LAYER).
        dependency_type: The dependency mapping type (if WAIT_LAYER).
    """

    execution_mode = serializers.ChoiceField(
        choices=["IMMEDIATE", "LAST", "WAIT_LAYER"],
        default="IMMEDIATE",
        write_only=True
    )
    depends_on_layer = serializers.CharField(
        max_length=256,
        allow_null=True,
        required=False,
        write_only=True
    )
    dependency_type = serializers.ChoiceField(
        choices=["TASK_ON_TASK", "LAYER_ON_LAYER"],
        allow_null=True,
        required=False,
        write_only=True
    )

    class Meta:
        model = Layer
        exclude = [
            "id",
            "job",
            "state",
            "total_tasks",
            "waiting_tasks",
            "ready_tasks",
            "running_tasks",
            "succeeded_tasks",
            "failed_tasks",
            "skipped_tasks",
            "depend_tasks",
        ]

    def validate_frame_range(self, value: str) -> str:
        """Validate that the frame range string is parseable.

        Args:
            value: The raw frame range string from the request.

        Returns:
            The validated frame range string.

        Raises:
            serializers.ValidationError: If the frame range is invalid.
        """
        from .services import expand_frame_range

        try:
            frames = expand_frame_range(value)
            if not frames:
                raise serializers.ValidationError("Frame range produced zero frames.")
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value


# ── Job Serializers ───────────────────────────────────────────────────────────


class JobListSerializer(serializers.ModelSerializer):
    """Slim read-only job representation for list views.

    Attributes:
        id: UUID primary key.
        name: System-generated stable identifier.
        visible_name: Human-readable label.
        project: Active show or production segment.
        department: Department name.
        user: Submitter's display name.
        state: Current execution state.
        priority: Dispatch priority (1-100).
        is_paused: Standalone pause flag.
        total_tasks: Counter cache.
        waiting_tasks: Counter cache.
        ready_tasks: Counter cache.
        running_tasks: Counter cache.
        succeeded_tasks: Counter cache.
        failed_tasks: Counter cache.
        skipped_tasks: Counter cache.
        depend_tasks: Counter cache.
        created_at: Submission timestamp.
        updated_at: Last update timestamp.
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "name",
            "visible_name",
            "project",
            "department",
            "user",
            "state",
            "priority",
            "is_paused",
            "total_tasks",
            "waiting_tasks",
            "ready_tasks",
            "running_tasks",
            "succeeded_tasks",
            "failed_tasks",
            "skipped_tasks",
            "depend_tasks",
            "created_at",
            "updated_at",
            "included_pools",
            "excluded_pools",
        ]
        read_only_fields = fields


class JobDetailSerializer(JobListSerializer):
    """Full read-only job representation for detail views.

    Extends :class:`JobListSerializer` with nested layers, log directory,
    worker concurrency limit, and stop timestamp.

    Attributes:
        layers: Nested list of all layers belonging to this job.
        log_directory: Absolute path for task logs.
        max_tasks_per_worker: Concurrent tasks per Worker limit.
        stopped_at: Timestamp when job reached FINISHED or FAILED.
    """

    layers = LayerDetailSerializer(many=True, read_only=True)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "layers",
            "log_directory",
            "max_tasks_per_worker",
            "stopped_at",
        ]
        read_only_fields = fields


class JobCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer for job submission.

    Accepts a nested ``layers`` array. The ``name`` field is auto-generated
    by the service layer if not provided. The ``submitted_by`` field is
    populated from the authenticated session user if available.

    Attributes:
        layers: Nested list of layer data (required, at least one).
        visible_name: Human-readable label for the job.
        project: Active show or production segment.
        department: Department name.
        user: Submitter's display name.
        priority: Dispatch priority (1-100).
        log_directory: Absolute path for task logs.
        max_tasks_per_worker: Concurrent tasks per Worker limit.
    """

    layers = LayerCreateSerializer(many=True)
    dependencies = JobDependencySpecSerializer(
        many=True,
        required=False,
        default=list,
        help_text="Optional list of JOB_ON_JOB external dependencies.",
    )

    class Meta:
        model = Job
        fields = [
            "visible_name",
            "project",
            "department",
            "user",
            "priority",
            "log_directory",
            "max_tasks_per_worker",
            "included_pools",
            "excluded_pools",
            "layers",
            "dependencies",
        ]

    def validate(self, data: dict) -> dict:
        included = data.get("included_pools", [])
        excluded = data.get("excluded_pools", [])

        if included and excluded:
            intersection = set(included) & set(excluded)
            if intersection:
                raise serializers.ValidationError("A pool cannot be both included and excluded.")
        return data

    def validate_layers(self, value: list) -> list:
        """Ensure at least one layer is provided.

        Args:
            value: The list of deserialized layer data dicts.

        Returns:
            The validated layer list.

        Raises:
            serializers.ValidationError: If the list is empty.
        """
        if not value:
            raise serializers.ValidationError("A job must contain at least one layer.")
        return value

    def create(self, validated_data: dict) -> Job:
        """Delegate creation to the service layer for atomic job + layer + task creation.

        Args:
            validated_data: The fully validated data dict including nested layers
                and an optional ``dependencies`` list.

        Returns:
            The newly created :class:`Job` instance.

        Raises:
            serializers.ValidationError: If the service raises :exc:`ValueError`
                (e.g. invalid layer name in dependency spec, self-dependency,
                cycle detected).
        """
        request = self.context.get("request")
        submitted_by = request.user if request and request.user.is_authenticated else None
        try:
            return create_job_with_layers(
                validated_data,
                submitted_by=submitted_by,
            )
        except ValueError as exc:
            raise serializers.ValidationError({"dependencies": str(exc)}) from exc


class JobPatchSerializer(serializers.ModelSerializer):
    """Write-only serializer for partial job updates.

    Only exposes fields that are safe to mutate post-submission. State
    transitions (pause, resume) use dedicated action endpoints instead.

    Attributes:
        visible_name: Human-readable label.
        priority: Dispatch priority (1-100).
        max_tasks_per_worker: Concurrent tasks per Worker limit.
    """

    class Meta:
        model = Job
        fields = [
            "visible_name",
            "priority",
            "max_tasks_per_worker",
            "included_pools",
            "excluded_pools",
        ]

    def validate(self, data: dict) -> dict:
        # Since this is a PATCH, we need to consider existing pools if not provided in the request
        included = data.get("included_pools", self.instance.included_pools.all() if self.instance else [])
        excluded = data.get("excluded_pools", self.instance.excluded_pools.all() if self.instance else [])

        if included and excluded:
            intersection = set(included) & set(excluded)
            if intersection:
                raise serializers.ValidationError("A pool cannot be both included and excluded.")
        return data


# ── Task Action Serializers ──────────────────────────────────────────────────


class TaskStartSerializer(serializers.Serializer):
    """Validates payload when a Worker marks a task as RUNNING.

    Attributes:
        worker_name: Hostname of the Worker claiming this task.
    """

    worker_name = serializers.CharField(max_length=256, help_text="Hostname of the Worker claiming this task.")


class TaskSucceedSerializer(serializers.Serializer):
    """Validates payload when a Worker reports a task as SUCCEEDED.

    Attributes:
        exit_status: Process exit code (should be 0).
        max_memory_used_mb: Peak RSS memory in MB.
        cores_used: Actual CPU cores used.
    """

    exit_status = serializers.IntegerField(default=0, help_text="Process exit code. Should be 0 on success.")
    max_memory_used_mb = serializers.IntegerField(
        default=0, min_value=0, help_text="Peak RSS memory used by the render process, in MB."
    )
    cores_used = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Actual CPU cores reserved by the Worker at dispatch time.",
    )


class TaskFailSerializer(serializers.Serializer):
    """Validates payload when a Worker reports a task as FAILED.

    Attributes:
        exit_status: Non-zero process exit code.
    """

    exit_status = serializers.IntegerField(help_text="Non-zero process exit code from the render process.")
