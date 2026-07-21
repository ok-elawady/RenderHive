import json

from django.contrib import admin
from django.utils.html import format_html

from .models import WorkerNode, WorkerPool


@admin.register(WorkerPool)
class WorkerPoolAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


@admin.register(WorkerNode)
class WorkerNodeAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "status", "cores", "memory_mb", "last_ping", "created_at")
    list_filter = ("status", "pools", "created_at")
    search_fields = ("hostname", "ip_address", "tags", "gpu_models")
    readonly_fields = ("created_at", "last_ping", "pretty_system_info")
    ordering = ("-last_ping",)
    filter_horizontal = ("pools",)

    fieldsets = (
        ("Basic Information", {
            "fields": ("hostname", "ip_address", "status")
        }),
        ("Capabilities", {
            "fields": ("pools", "cores", "memory_mb", "gpu_models", "tags"),
            "description": "Hardware specifications and pool assignments."
        }),
        ("Telemetry", {
            "fields": ("pretty_system_info",),
            "description": "Transient and live utilization metrics reported by the worker."
        }),
        ("Timestamps", {
            "fields": ("last_ping", "created_at"),
            "classes": ("collapse",)
        }),
    )

    def pretty_system_info(self, instance):
        """Returns the system_info JSON nicely formatted."""
        if not instance.system_info:
            return "{}"
        formatted_json = json.dumps(instance.system_info, indent=4)
        # Use <pre> for monospaced font and preserved whitespace
        return format_html(
            "<pre style='margin: 0; padding: 10px; "
            "background-color: #f8f8f8; border-radius: 4px;'>{}</pre>",
            formatted_json
        )
    
    pretty_system_info.short_description = "System Info"
