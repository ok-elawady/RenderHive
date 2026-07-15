from django.db import models
from django.utils import timezone

class WorkerStatus(models.TextChoices):
    ONLINE = "ONLINE", "Online"
    OFFLINE = "OFFLINE", "Offline"
    RENDERING = "RENDERING", "Rendering"

class WorkerNode(models.Model):
    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=WorkerStatus.choices, default=WorkerStatus.OFFLINE, db_index=True
    )
    system_info = models.JSONField(default=dict, blank=True, help_text="CPU, RAM, OS, and live utilization metrics.")
    last_ping = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "worker node"
        verbose_name_plural = "worker nodes"
        ordering = ["-last_ping"]

    def __str__(self):
        return self.hostname
