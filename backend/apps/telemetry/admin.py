from django.contrib import admin

from .models import DispatchTrace, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot


@admin.register(TaskExecutionLog)
class TaskExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("task", "job", "attempt_number", "worker_hostname", "exit_status", "duration_seconds", "peak_memory_mb", "created_at")
    list_filter = ("exit_status", "worker_hostname", "created_at")
    search_fields = ("task__name", "job__name", "worker_hostname", "error_tail")
    readonly_fields = (
        "id",
        "task",
        "job",
        "attempt_number",
        "worker_hostname",
        "exit_status",
        "duration_seconds",
        "peak_memory_mb",
        "output_image_path",
        "error_tail",
        "log_output",
        "created_at",
    )


@admin.register(DispatchTrace)
class DispatchTraceAdmin(admin.ModelAdmin):
    list_display = ("task", "job", "worker_hostname", "ai_invoked", "ai_latency_ms", "dispatched_at")
    list_filter = ("ai_invoked", "worker_hostname", "dispatched_at")
    search_fields = ("task__name", "job__name", "worker_hostname", "ai_reason")
    readonly_fields = ("id", "task", "job", "worker_hostname", "candidate_count", "ai_invoked", "ai_latency_ms", "ai_reason", "score_breakdown", "dispatched_at")


@admin.register(FarmEvent)
class FarmEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "severity", "actor_username", "target_type", "target_id", "target_name", "message", "created_at")
    list_filter = ("severity", "event_type", "target_type", "created_at")
    search_fields = ("event_type", "message", "actor_username", "target_id", "target_name")
    readonly_fields = ("id", "event_type", "severity", "actor_username", "target_type", "target_id", "target_name", "message", "payload", "created_at")


@admin.register(WorkerMetricSnapshot)
class WorkerMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("worker_hostname", "cpu_percent", "memory_used_mb", "vram_percent", "active_tasks", "recorded_at")
    list_filter = ("worker_hostname", "recorded_at")
    search_fields = ("worker_hostname",)
    readonly_fields = ("id", "recorded_at")
