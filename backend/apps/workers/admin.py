from django.contrib import admin
from .models import WorkerNode

@admin.register(WorkerNode)
class WorkerNodeAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "status", "last_ping", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("hostname", "ip_address")
    readonly_fields = ("created_at", "last_ping")
    ordering = ("-last_ping",)

    fieldsets = (
        ("Basic Information", {
            "fields": ("hostname", "ip_address", "status")
        }),
        ("Telemetry", {
            "fields": ("system_info",),
            "description": "Hardware and resource telemetry reported by the worker."
        }),
        ("Timestamps", {
            "fields": ("last_ping", "created_at"),
            "classes": ("collapse",)
        }),
    )
