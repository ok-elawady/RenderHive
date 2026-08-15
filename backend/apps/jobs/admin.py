"""
Django Admin registration for the jobs app.

Provides list views, search, filtering, and read-only protection on
auto-managed fields (counter caches, timestamps, UUIDs) for all four
jobs models: Job, Layer, Task, and Dependency.
"""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Dependency, Job, Layer, Task


class LayerInline(admin.TabularInline):
    """Inline display of Layers within the Job detail page.

    Shows key fields without requiring a separate Layer admin page visit.
    All fields are read-only to prevent accidental edits from the job view.

    Attributes:
        model: The Layer model.
        extra: No blank rows shown by default.
        show_change_link: Allows navigating to the full Layer admin page.
    """

    model = Layer
    extra = 0
    show_change_link = True
    readonly_fields = (
        "id",
        "name",
        "layer_type",
        "state",
        "frame_range",
        "chunk_size",
        "total_tasks",
        "waiting_tasks",
        "ready_tasks",
        "running_tasks",
        "succeeded_tasks",
        "failed_tasks",
        "skipped_tasks",
    )
    fields = readonly_fields
    can_delete = False


class JobAdminForm(forms.ModelForm):
    """Custom form for JobAdmin to validate many-to-many pool fields before save."""

    class Meta:
        model = Job
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        included = cleaned_data.get("included_pools")
        excluded = cleaned_data.get("excluded_pools")

        if included and excluded:
            intersection = set(included.values_list("pk", flat=True)) & set(excluded.values_list("pk", flat=True))
            if intersection:
                raise ValidationError("A pool cannot be both included and excluded.")
        return cleaned_data


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin view for the Job model.

    Counter cache fields and timestamps are read-only — they are managed
    atomically by signals and must not be edited manually.
    """

    list_display = (
        "name",
        "visible_name",
        "project",
        "department",
        "user",
        "state",
        "priority",
        "is_paused",
        "total_tasks",
        "running_tasks",
        "failed_tasks",
        "created_at",
    )
    list_filter = ("state", "is_paused", "project", "department")
    search_fields = ("name", "visible_name", "project", "user")
    ordering = ("-priority", "created_at")
    filter_horizontal = ("included_pools", "excluded_pools")
    form = JobAdminForm
    readonly_fields = (
        "id",
        "name",
        "submitted_by",
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
        "stopped_at",
    )
    inlines = [LayerInline]

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("id", "name", "visible_name"),
            },
        ),
        (
            "Ownership",
            {
                "fields": ("project", "department", "user", "submitted_by"),
            },
        ),
        (
            "State",
            {
                "fields": ("state", "is_paused", "priority", "max_tasks_per_worker"),
            },
        ),
        (
            "Routing",
            {
                "fields": ("included_pools", "excluded_pools"),
                "description": "Control which worker pools can or cannot process this job.",
            },
        ),
        (
            "Paths",
            {
                "fields": ("log_directory",),
            },
        ),
        (
            "Progress Counters (read-only)",
            {
                "fields": (
                    "total_tasks",
                    "waiting_tasks",
                    "ready_tasks",
                    "running_tasks",
                    "succeeded_tasks",
                    "failed_tasks",
                    "skipped_tasks",
                    "depend_tasks",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "stopped_at"),
            },
        ),
    )


@admin.register(Layer)
class LayerAdmin(admin.ModelAdmin):
    """Admin view for the Layer model.

    Counter cache fields and state are read-only — they are managed
    atomically by signals and must not be edited manually.
    """

    list_display = (
        "name",
        "job",
        "layer_type",
        "state",
        "frame_range",
        "chunk_size",
        "total_tasks",
        "running_tasks",
        "failed_tasks",
    )
    list_filter = ("state", "layer_type")
    search_fields = ("name", "job__name", "job__visible_name")
    ordering = ("job", "name")
    readonly_fields = (
        "id",
        "state",
        "total_tasks",
        "waiting_tasks",
        "ready_tasks",
        "running_tasks",
        "succeeded_tasks",
        "failed_tasks",
        "skipped_tasks",
        "depend_tasks",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("id", "job", "name", "layer_type"),
            },
        ),
        (
            "Execution",
            {
                "fields": ("command", "frame_range", "chunk_size"),
            },
        ),
        (
            "Resource Requirements",
            {
                "fields": ("min_cores", "min_memory_mb", "min_gpus", "tags"),
            },
        ),
        (
            "Scene",
            {
                "fields": ("scene_path", "scene_info"),
            },
        ),
        (
            "Environment",
            {
                "fields": ("env",),
            },
        ),
        (
            "Reliability",
            {
                "fields": ("max_retries", "timeout_seconds"),
            },
        ),
        (
            "State & Progress (read-only)",
            {
                "fields": (
                    "state",
                    "total_tasks",
                    "waiting_tasks",
                    "ready_tasks",
                    "running_tasks",
                    "succeeded_tasks",
                    "failed_tasks",
                    "skipped_tasks",
                    "depend_tasks",
                ),
            },
        ),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin view for the Task model.

    The ``depend_count`` field is read-only — it is managed atomically
    by signals and must not be edited manually.
    """

    list_display = (
        "name",
        "job",
        "layer",
        "frame_start",
        "frame_end",
        "state",
        "depend_count",
        "retries",
        "worker_name",
        "exit_status",
        "started_at",
        "stopped_at",
    )
    list_filter = ("state",)
    search_fields = ("name", "worker_name", "job__name", "layer__name")
    ordering = ("job", "layer", "dispatch_order")
    readonly_fields = (
        "id",
        "job",
        "layer",
        "depend_count",
        "updated_at",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("id", "job", "layer", "name", "frame_start", "frame_end", "dispatch_order"),
            },
        ),
        (
            "State",
            {
                "fields": ("state", "depend_count"),
            },
        ),
        (
            "Retry Logic",
            {
                "fields": ("retries", "max_retries", "checkpoint_count"),
            },
        ),
        (
            "Execution Telemetry",
            {
                "fields": ("exit_status", "max_memory_used_mb", "cores_used", "worker_name"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("started_at", "stopped_at", "updated_at"),
            },
        ),
    )


@admin.register(Dependency)
class DependencyAdmin(admin.ModelAdmin):
    """Admin view for the Dependency model.

    Provides visibility into the dependency graph. All fields are
    effectively read-only in practice — dependencies should only be
    created and satisfied via the API or signals.
    """

    list_display = (
        "id",
        "type",
        "dep_job",
        "dep_task",
        "parent_job",
        "parent_task",
        "is_satisfied",
        "created_at",
        "satisfied_at",
    )
    list_filter = ("type", "is_satisfied")
    search_fields = ("dep_job__name", "parent_job__name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "satisfied_at")
