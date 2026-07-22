import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone


class WorkerPool(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True, db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "worker pool"
        verbose_name_plural = "worker pools"
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkerStatus(models.TextChoices):
    ONLINE = "ONLINE", "Online"
    OFFLINE = "OFFLINE", "Offline"
    RENDERING = "RENDERING", "Rendering"


class WorkerNode(models.Model):
    hostname = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=WorkerStatus.choices, default=WorkerStatus.OFFLINE, db_index=True)

    pools = models.ManyToManyField(WorkerPool, blank=True, related_name="workers")
    tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    cores = models.PositiveIntegerField(default=1)
    memory_mb = models.PositiveIntegerField(default=4096)
    gpu_models = ArrayField(models.CharField(max_length=128), default=list, blank=True)

    system_info = models.JSONField(default=dict, blank=True, help_text="Transient and live utilization metrics.")
    last_ping = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "worker node"
        verbose_name_plural = "worker nodes"
        ordering = ["-last_ping"]

    def __str__(self):
        return self.hostname
