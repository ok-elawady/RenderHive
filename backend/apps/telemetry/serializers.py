from rest_framework import serializers

from .models import DispatchTrace, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot


class TaskLogListSerializer(serializers.ModelSerializer):
    """Slim serializer for listing task execution logs without the heavy log body."""

    task_name = serializers.CharField(source="task.name", read_only=True)
    job_name = serializers.CharField(source="job.name", read_only=True)

    class Meta:
        model = TaskExecutionLog
        fields = [
            "id",
            "task",
            "task_name",
            "job",
            "job_name",
            "attempt_number",
            "worker_hostname",
            "exit_status",
            "duration_seconds",
            "peak_memory_mb",
            "output_image_path",
            "error_tail",
            "created_at",
        ]
        read_only_fields = fields


class TaskLogDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for inspecting a specific task log with complete stdout/stderr."""

    task_name = serializers.CharField(source="task.name", read_only=True)
    job_name = serializers.CharField(source="job.name", read_only=True)

    class Meta:
        model = TaskExecutionLog
        fields = [
            "id",
            "task",
            "task_name",
            "job",
            "job_name",
            "attempt_number",
            "worker_hostname",
            "exit_status",
            "duration_seconds",
            "peak_memory_mb",
            "output_image_path",
            "error_tail",
            "log_output",
            "created_at",
        ]
        read_only_fields = fields


class TaskLogIngestSerializer(serializers.Serializer):
    """Write serializer for uploading task execution logs from worker nodes."""

    exit_status = serializers.IntegerField(default=0)
    log_output = serializers.CharField(allow_blank=True, default="")
    error_tail = serializers.CharField(allow_blank=True, required=False, default="")
    duration_seconds = serializers.FloatField(required=False, default=0.0)
    peak_memory_mb = serializers.IntegerField(required=False, default=0)
    output_image_path = serializers.CharField(allow_blank=True, required=False, default="")
    worker_hostname = serializers.CharField(required=False, default="")
    attempt_number = serializers.IntegerField(required=False, allow_null=True, default=None)


class DispatchTraceSerializer(serializers.ModelSerializer):
    """Read serializer for scheduler and AI dispatch traces."""

    task_name = serializers.CharField(source="task.name", read_only=True, default="Deleted Task")
    job_name = serializers.CharField(source="job.name", read_only=True)
    job_visible_name = serializers.CharField(source="job.visible_name", read_only=True)

    class Meta:
        model = DispatchTrace
        fields = [
            "id",
            "task",
            "task_name",
            "job",
            "job_name",
            "job_visible_name",
            "worker_hostname",
            "candidate_count",
            "ai_invoked",
            "ai_latency_ms",
            "ai_reason",
            "score_breakdown",
            "dispatched_at",
        ]
        read_only_fields = fields


class FarmEventSerializer(serializers.ModelSerializer):
    """Serializer for audit trail and farm lifecycle events."""

    target_display = serializers.SerializerMethodField()

    class Meta:
        model = FarmEvent
        fields = [
            "id",
            "event_type",
            "severity",
            "actor_username",
            "target_type",
            "target_id",
            "target_name",
            "target_display",
            "message",
            "payload",
            "created_at",
        ]
        read_only_fields = fields

    def get_target_display(self, obj) -> str:
        """Return a human-readable display string for the target resource."""
        if obj.target_name:
            return obj.target_name

        payload = obj.payload if isinstance(obj.payload, dict) else {}
        for key in ("hostname", "worker_hostname", "worker_name", "worker", "job_name", "task_name", "name"):
            val = payload.get(key)
            if val and isinstance(val, str):
                return val

        if obj.target_id:
            if "-" not in obj.target_id and len(obj.target_id) < 32:
                return obj.target_id
            prefix = f"{obj.target_type}:" if obj.target_type else ""
            short_id = obj.target_id[:8] if len(obj.target_id) > 8 else obj.target_id
            return f"{prefix}{short_id}"

        return "Cluster Wide"


class WorkerMetricSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for raw hardware metric samples."""

    class Meta:
        model = WorkerMetricSnapshot
        fields = [
            "id",
            "worker_hostname",
            "cpu_percent",
            "memory_used_mb",
            "memory_total_mb",
            "vram_percent",
            "active_tasks",
            "recorded_at",
        ]
        read_only_fields = fields


class TelemetryPointSerializer(serializers.Serializer):
    """Single time-bucket hardware metric aggregation point."""

    x = serializers.IntegerField(help_text="Normalized x position percentage (0-100).")
    cpu = serializers.FloatField(help_text="Average CPU cluster load percentage.")
    vram = serializers.FloatField(help_text="Average GPU VRAM utilization percentage.")
    ram = serializers.FloatField(default=0.0, required=False, help_text="Average System RAM utilization percentage.")
    active_tasks = serializers.IntegerField(help_text="Peak concurrent active rendering tasks.")
    timestamp = serializers.DateTimeField(help_text="ISO timestamp of the bucket end.")


class ClusterTelemetryHistoryResponseSerializer(serializers.Serializer):
    """Aggregated historical timeseries response for the cluster."""

    range = serializers.CharField(help_text="Query range: 1h, 24h, or 7d.")
    cpu_load = serializers.FloatField(help_text="Current latest CPU load percentage.")
    vram_usage = serializers.FloatField(help_text="Current latest GPU VRAM utilization percentage.")
    ram_usage = serializers.FloatField(default=0.0, required=False, help_text="Current latest System RAM utilization percentage.")
    peak_cpu = serializers.FloatField(default=0.0, required=False, help_text="Peak CPU load percentage observed in range.")
    peak_vram = serializers.FloatField(default=0.0, required=False, help_text="Peak VRAM utilization percentage observed in range.")
    peak_ram = serializers.FloatField(default=0.0, required=False, help_text="Peak System RAM utilization percentage observed in range.")
    total_snapshots = serializers.IntegerField(default=0, required=False, help_text="Total individual worker metric samples in range.")
    points = TelemetryPointSerializer(many=True, help_text="Time-bucketed aggregation data points.")

