import datetime
import logging
from typing import Any, Dict, Optional

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.telemetry.models import DispatchTrace, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot

logger = logging.getLogger(__name__)


@shared_task(name="apps.telemetry.tasks.snapshot_online_worker_metrics")
def snapshot_online_worker_metrics() -> Dict[str, Any]:
    """Capture real-time hardware telemetry samples for all online/rendering worker nodes."""
    from apps.workers.models import WorkerNode, WorkerStatus
    from apps.telemetry.services.event_recorder import record_worker_metric_sample

    online_workers = WorkerNode.objects.filter(status__in=[WorkerStatus.ONLINE, WorkerStatus.RENDERING])
    recorded_count = 0

    for worker in online_workers:
        sys_info = worker.system_info if isinstance(worker.system_info, dict) else {}
        cpu = float(sys_info.get("cpu_percent", 0.0))
        vram = float(sys_info.get("vram_percent", sys_info.get("memory_percent", 0.0)))
        mem_used = int(sys_info.get("memory_used_mb", 0))
        mem_total = int(sys_info.get("memory_total_mb", worker.memory_mb or 4096))
        active_tasks = int(sys_info.get("active_tasks", 0))

        sample = record_worker_metric_sample(
            worker_hostname=worker.hostname,
            cpu_percent=cpu,
            memory_used_mb=mem_used,
            memory_total_mb=mem_total,
            vram_percent=vram,
            active_tasks=active_tasks,
            force=True,
        )
        if sample:
            recorded_count += 1

    return {"online_workers": online_workers.count(), "recorded_snapshots": recorded_count}


@shared_task(name="apps.telemetry.tasks.prune_old_telemetry")
def prune_old_telemetry(days: Optional[int] = None) -> Dict[str, Any]:
    """Prune historical telemetry data older than the retention threshold.

    Deletes expired TaskExecutionLog, DispatchTrace, FarmEvent, and WorkerMetricSnapshot records.
    """
    if days is None:
        days = getattr(settings, "TELEMETRY_RETENTION_DAYS", 30)

    cutoff_date = timezone.now() - datetime.timedelta(days=days)
    logger.info("Starting telemetry pruning for records older than %d days (cutoff: %s)", days, cutoff_date.isoformat())

    deleted_logs, _ = TaskExecutionLog.objects.filter(created_at__lt=cutoff_date).delete()
    deleted_dispatches, _ = DispatchTrace.objects.filter(dispatched_at__lt=cutoff_date).delete()
    deleted_events, _ = FarmEvent.objects.filter(created_at__lt=cutoff_date).delete()
    deleted_metrics, _ = WorkerMetricSnapshot.objects.filter(recorded_at__lt=cutoff_date).delete()

    result = {
        "days": days,
        "cutoff": cutoff_date.isoformat(),
        "deleted_task_logs": deleted_logs,
        "deleted_dispatches": deleted_dispatches,
        "deleted_events": deleted_events,
        "deleted_metric_snapshots": deleted_metrics,
        "total_deleted": deleted_logs + deleted_dispatches + deleted_events + deleted_metrics,
    }

    logger.info("Telemetry pruning finished: %s", result)
    return result
