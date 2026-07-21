"""
Serializers for the jobs app REST API.

Serializers are split by usage pattern:
- List serializers: slim, read-only representations for list views.
- Detail serializers: full read-only representations for retrieve views.
- Create serializers: write-only, used for POST endpoints.
- Patch serializers: write-only, limited fields for PATCH endpoints.
- Action serializers: write-only, used for frame state transition endpoints.
"""

from rest_framework import serializers

from .models import Frame, Job, Layer
from .services import create_job_with_layers

# ── Frame Serializers ─────────────────────────────────────────────────────────


class FrameListSerializer(serializers.ModelSerializer):
    """Slim read-only frame representation for list views.

    Attributes:
        id: UUID primary key.
        name: Display name (e.g. 'beauty_0042').
        number: Render frame index.
        state: Current execution state.
        depend_count: Number of unresolved dependencies.
        retries: Execution attempt count.
        worker_name: Hostname of the executing Worker.
        exit_status: Process exit code (-1 if not yet run).
        started_at: Execution start timestamp.
        stopped_at: Execution stop timestamp.
    """

    class Meta:
        model = Frame
        fields = [
            "id",
            "name",
            "number",
            "state",
            "depend_count",
            "retries",
            "worker_name",
            "exit_status",
            "started_at",
            "stopped_at",
        ]
        read_only_fields = fields


class FrameDetailSerializer(FrameListSerializer):
    """Full read-only frame representation for detail and Worker poll views.

    Extends :class:`FrameListSerializer` with execution telemetry fields.

    Attributes:
        max_memory_used_mb: Peak RSS memory in MB.
        cores_used: CPU cores reserved at dispatch time.
        checkpoint_count: Number of resume checkpoints saved.
        dispatch_order: Dispatch priority within the layer.
    """

    class Meta(FrameListSerializer.Meta):
        fields = FrameListSerializer.Meta.fields + [
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
        total_frames: Counter cache.
        waiting_frames: Counter cache.
        ready_frames: Counter cache.
        running_frames: Counter cache.
        succeeded_frames: Counter cache.
        failed_frames: Counter cache.
        skipped_frames: Counter cache.
        depend_frames: Counter cache.
    """

    class Meta:
        model = Layer
        fields = [
            "id",
            "name",
            "layer_type",
            "state",
            "frame_range",
            "total_frames",
            "waiting_frames",
            "ready_frames",
            "running_frames",
            "succeeded_frames",
            "failed_frames",
            "skipped_frames",
            "depend_frames",
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
        max_retries: Per-frame retry ceiling.
        timeout_seconds: Frame execution timeout.
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
        max_retries: Per-frame retry ceiling.
        timeout_seconds: Frame execution timeout.
    """

    class Meta:
        model = Layer
        exclude = [
            "id",
            "job",
            "state",
            "total_frames",
            "waiting_frames",
            "ready_frames",
            "running_frames",
            "succeeded_frames",
            "failed_frames",
            "skipped_frames",
            "depend_frames",
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
        total_frames: Counter cache.
        waiting_frames: Counter cache.
        ready_frames: Counter cache.
        running_frames: Counter cache.
        succeeded_frames: Counter cache.
        failed_frames: Counter cache.
        skipped_frames: Counter cache.
        depend_frames: Counter cache.
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
            "total_frames",
            "waiting_frames",
            "ready_frames",
            "running_frames",
            "succeeded_frames",
            "failed_frames",
            "skipped_frames",
            "depend_frames",
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
        log_directory: Absolute path for frame logs.
        max_frames_per_worker: Concurrent frames per Worker limit.
        stopped_at: Timestamp when job reached FINISHED or FAILED.
    """

    layers = LayerDetailSerializer(many=True, read_only=True)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "layers",
            "log_directory",
            "max_frames_per_worker",
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
        log_directory: Absolute path for frame logs.
        max_frames_per_worker: Concurrent frames per Worker limit.
    """

    layers = LayerCreateSerializer(many=True)

    class Meta:
        model = Job
        fields = [
            "visible_name",
            "project",
            "department",
            "user",
            "priority",
            "log_directory",
            "max_frames_per_worker",
            "included_pools",
            "excluded_pools",
            "layers",
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
        """Delegate creation to the service layer for atomic job + layer + frame creation.

        Args:
            validated_data: The fully validated data dict including nested layers.

        Returns:
            The newly created :class:`Job` instance.
        """
        request = self.context.get("request")
        submitted_by = request.user if request and request.user.is_authenticated else None
        return create_job_with_layers(validated_data, submitted_by=submitted_by)


class JobPatchSerializer(serializers.ModelSerializer):
    """Write-only serializer for partial job updates.

    Only exposes fields that are safe to mutate post-submission. State
    transitions (pause, resume) use dedicated action endpoints instead.

    Attributes:
        visible_name: Human-readable label.
        priority: Dispatch priority (1-100).
        max_frames_per_worker: Concurrent frames per Worker limit.
    """

    class Meta:
        model = Job
        fields = [
            "visible_name",
            "priority",
            "max_frames_per_worker",
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


# ── Frame Action Serializers ──────────────────────────────────────────────────


class FrameStartSerializer(serializers.Serializer):
    """Validates payload when a Worker marks a frame as RUNNING.

    Attributes:
        worker_name: Hostname of the Worker claiming this frame.
    """

    worker_name = serializers.CharField(max_length=256, help_text="Hostname of the Worker claiming this frame.")


class FrameSucceedSerializer(serializers.Serializer):
    """Validates payload when a Worker reports a frame as SUCCEEDED.

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


class FrameFailSerializer(serializers.Serializer):
    """Validates payload when a Worker reports a frame as FAILED.

    Attributes:
        exit_status: Non-zero process exit code.
    """

    exit_status = serializers.IntegerField(help_text="Non-zero process exit code from the render process.")
