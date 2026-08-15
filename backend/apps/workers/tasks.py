import datetime
import logging
from typing import Any, Dict

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import Task, TaskState
from apps.telemetry.models import EventSeverity
from apps.telemetry.services import record_event
from apps.workers.models import WorkerNode, WorkerStatus

logger = logging.getLogger(__name__)


@shared_task(name="apps.workers.tasks.reap_stale_workers_and_tasks")
def reap_stale_workers_and_tasks() -> Dict[str, Any]:
    """Identify workers whose heartbeat has timed out and remediate orphaned tasks.

    - Transitions stale workers from ONLINE/RENDERING to OFFLINE.
    - Requeues RUNNING/CHECKPOINT tasks whose retries have not exceeded max_retries.
    - Marks RUNNING/CHECKPOINT tasks as FAILED if retry budget is exhausted.
    - Emits FarmEvent telemetry for worker drops and task state changes.
    """
    threshold_seconds = getattr(settings, "WORKER_STALE_THRESHOLD_SECONDS", 30)
    cutoff = timezone.now() - datetime.timedelta(seconds=threshold_seconds)

    stale_workers = list(
        WorkerNode.objects.filter(last_ping__lt=cutoff).exclude(status=WorkerStatus.OFFLINE)
    )

    reaped_worker_count = 0
    requeued_task_count = 0
    failed_task_count = 0

    if not stale_workers:
        return {
            "reaped_workers": 0,
            "requeued_tasks": 0,
            "failed_tasks": 0,
        }

    stale_hostnames = [w.hostname for w in stale_workers]

    with transaction.atomic():
        for worker in stale_workers:
            logger.warning(
                "Worker %s timed out (last ping %s). Marking OFFLINE.",
                worker.hostname,
                worker.last_ping,
            )
            worker.status = WorkerStatus.OFFLINE
            worker.save(update_fields=["status"])
            reaped_worker_count += 1

            record_event(
                event_type="WORKER_OFFLINE",
                severity=EventSeverity.WARNING,
                actor_username="system",
                target_type="worker",
                target_id=str(worker.id),
                target_name=worker.hostname,
                message=f"Worker {worker.hostname} timed out and was marked OFFLINE.",
                payload={"last_ping": worker.last_ping.isoformat() if worker.last_ping else None},
            )

        # Handle orphaned tasks assigned to stale workers
        orphaned_tasks = list(
            Task.objects.select_for_update()
            .filter(
                worker_name__in=stale_hostnames,
                state__in=[TaskState.RUNNING, TaskState.CHECKPOINT],
            )
        )

        for task in orphaned_tasks:
            prev_worker = task.worker_name
            if task.retries < task.max_retries:
                task.retries += 1
                task.worker_name = ""
                task.state = TaskState.READY
                task.save()
                requeued_task_count += 1

                logger.info(
                    "Requeued task %s after worker %s dropped (attempt %d/%d).",
                    task.name,
                    prev_worker,
                    task.retries,
                    task.max_retries,
                )
                record_event(
                    event_type="TASK_REQUEUED",
                    severity=EventSeverity.WARNING,
                    actor_username="system",
                    target_type="task",
                    target_id=str(task.id),
                    target_name=task.name,
                    message=f"Task '{task.name}' requeued after worker '{prev_worker}' disconnected.",
                    payload={
                        "task_id": str(task.id),
                        "worker_hostname": prev_worker,
                        "retries": task.retries,
                        "max_retries": task.max_retries,
                    },
                )
            else:
                task.state = TaskState.FAILED
                task.exit_status = -1
                task.save()
                failed_task_count += 1

                logger.error(
                    "Task %s failed after worker %s dropped: max retries reached.",
                    task.name,
                    prev_worker,
                )
                record_event(
                    event_type="TASK_FAILED",
                    severity=EventSeverity.ERROR,
                    actor_username="system",
                    target_type="task",
                    target_id=str(task.id),
                    target_name=task.name,
                    message=f"Task '{task.name}' failed on worker '{prev_worker}' disconnect (exceeded max retries).",
                    payload={
                        "task_id": str(task.id),
                        "worker_hostname": prev_worker,
                        "retries": task.retries,
                        "max_retries": task.max_retries,
                    },
                )

    return {
        "reaped_workers": reaped_worker_count,
        "requeued_tasks": requeued_task_count,
        "failed_tasks": failed_task_count,
    }
