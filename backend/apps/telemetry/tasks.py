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
    from apps.telemetry.services import record_worker_metrics

    online_workers = WorkerNode.objects.filter(status__in=[WorkerStatus.ONLINE, WorkerStatus.RENDERING])
    recorded_count = 0

    for worker in online_workers:
        sys_info = worker.system_info if isinstance(worker.system_info, dict) else {}
        cpu = float(sys_info.get("cpu_percent", 0.0))
        if "vram_percent" in sys_info:
            vram = float(sys_info["vram_percent"])
        elif float(sys_info.get("gpu_vram_mb", 0)) > 0:
            vram_used = float(sys_info.get("gpu_vram_used_mb", 0))
            vram_total = float(sys_info.get("gpu_vram_mb", 1))
            vram = round((vram_used / vram_total) * 100.0, 1)
        else:
            vram = 0.0
        mem_used = int(sys_info.get("used_memory_mb", sys_info.get("memory_used_mb", 0)))
        mem_total = int(sys_info.get("total_memory_mb", worker.memory_mb or 4096))
        active_tasks = 1 if worker.status == WorkerStatus.RENDERING else int(sys_info.get("active_tasks", 0))

        sample = record_worker_metrics(
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


@shared_task(bind=True, name="apps.telemetry.tasks.generate_ai_explanation_for_log", rate_limit="5/m")
def generate_ai_explanation_for_log(self, log_id: str) -> Optional[str]:
    """Asynchronously generate an AI explanation for a failed task log.
    Includes load-aware pausing to avoid hogging resources.
    """
    import psutil
    import requests
    from django.conf import settings
    from apps.telemetry.models import TaskExecutionLog

    # Check host system load (avoid running AI inference if CPU is pegged)
    cpu_usage = psutil.cpu_percent(interval=1.0)
    if cpu_usage > 85.0:
        logger.warning(f"Host CPU usage at {cpu_usage}%. Pausing AI explanation for log {log_id}. Retrying in 60s.")
        raise self.retry(countdown=60)

    try:
        log = TaskExecutionLog.objects.get(id=log_id)
    except TaskExecutionLog.DoesNotExist:
        logger.error(f"TaskExecutionLog {log_id} not found.")
        return None

    log_text = log.error_tail or log.log_output
    if not log_text:
        return None

    ai_url = getattr(settings, "AI_SERVICE_URL", "http://ai_service:8001/api/v1/rank-tasks")
    explain_url = ai_url.replace("/rank-tasks", "/explain-log")

    try:
        resp = requests.post(explain_url, json={"log_text": log_text}, timeout=120)
        resp.raise_for_status()
        explanation = resp.json().get("explanation", "")
        
        log.ai_explanation = explanation
        log.save(update_fields=["ai_explanation"])
        return explanation
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to generate AI explanation for log {log_id}: {e}")
        # Could retry here, but we'll just fail silently to avoid endless retries on broken AI service.
        return None
