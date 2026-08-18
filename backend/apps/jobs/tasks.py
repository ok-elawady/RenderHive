import datetime
import logging
from typing import Any, Dict

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.jobs.models import Job, JobState, Layer, Task, TaskState
from apps.telemetry.models import EventSeverity
from apps.telemetry.services import record_event

logger = logging.getLogger(__name__)


@shared_task(name="apps.jobs.tasks.reconcile_queue_state")
def reconcile_queue_state() -> Dict[str, Any]:
    """Periodic health sweep to audit and reconcile render queue integrity.

    Performs 3 critical audits:
    1. **Task Execution Timeout**: Detects tasks in RUNNING/CHECKPOINT state that
       have exceeded their layer's ``timeout_seconds`` and either requeues or fails them.
    2. **Counter Cache Audit & Repair**: Recalculates exact task state counts for all
       in-flight (non-FINISHED) Jobs and Layers and repairs any counter drift.
    3. **State Consistency Alignment**:
       - Ensures entities with ``running_tasks > 0`` are marked ``RUNNING``.
       - Ensures entities with ``running_tasks == 0`` and ready/waiting frames are marked ``PENDING``.
       - Ensures entities with 100% succeeded/skipped frames are marked ``FINISHED``.
       - Ensures entities with 0 active frames and unrecovered failures are marked ``FAILED``.

    Returns:
        Dict summarizing actions taken during the sweep.
    """
    now = timezone.now()
    reconciled_jobs = 0
    reconciled_layers = 0
    timed_out_tasks_requeued = 0
    timed_out_tasks_failed = 0

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Task Execution Timeout Audit
    # ─────────────────────────────────────────────────────────────────────────
    default_timeout = getattr(settings, "TASK_DEFAULT_TIMEOUT_SECONDS", 7200)  # 2 hours default
    active_tasks = list(
        Task.objects.select_related("layer", "job")
        .filter(state__in=[TaskState.RUNNING, TaskState.CHECKPOINT], started_at__isnull=False)
    )

    with transaction.atomic():
        for task in active_tasks:
            timeout_sec = task.layer.timeout_seconds or default_timeout
            if timeout_sec <= 0:
                continue

            elapsed_sec = (now - task.started_at).total_seconds()
            if elapsed_sec > timeout_sec:
                worker_name = task.worker_name or "unknown"
                if task.retries < task.max_retries:
                    task.retries += 1
                    task.state = TaskState.READY
                    task.worker_name = ""
                    task.started_at = None
                    task.stopped_at = None
                    task.exit_status = -1
                    task.save()
                    timed_out_tasks_requeued += 1

                    logger.warning(
                        "Task %s timed out after %.1fs on %s (limit %ds). Requeued (attempt %d/%d).",
                        task.name,
                        elapsed_sec,
                        worker_name,
                        timeout_sec,
                        task.retries,
                        task.max_retries,
                    )
                    record_event(
                        event_type="TASK_TIMEOUT",
                        severity=EventSeverity.WARNING,
                        actor_username="system",
                        target_type="task",
                        target_id=str(task.id),
                        target_name=task.name,
                        message=f"Task '{task.name}' timed out after {elapsed_sec:.0f}s on '{worker_name}' and was requeued.",
                        payload={
                            "task_id": str(task.id),
                            "elapsed_seconds": elapsed_sec,
                            "timeout_seconds": timeout_sec,
                            "retries": task.retries,
                            "max_retries": task.max_retries,
                        },
                    )
                else:
                    task.state = TaskState.FAILED
                    task.exit_status = 124  # Standard timeout exit code
                    task.stopped_at = now
                    task.save()
                    timed_out_tasks_failed += 1

                    logger.error(
                        "Task %s timed out after %.1fs on %s (limit %ds). Max retries reached; marked FAILED.",
                        task.name,
                        elapsed_sec,
                        worker_name,
                        timeout_sec,
                    )
                    record_event(
                        event_type="TASK_FAILED",
                        severity=EventSeverity.ERROR,
                        actor_username="system",
                        target_type="task",
                        target_id=str(task.id),
                        target_name=task.name,
                        message=f"Task '{task.name}' timed out after {elapsed_sec:.0f}s on '{worker_name}' and failed (max retries reached).",
                        payload={
                            "task_id": str(task.id),
                            "elapsed_seconds": elapsed_sec,
                            "timeout_seconds": timeout_sec,
                            "exit_status": 124,
                        },
                    )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Counter & State Reconciliation for In-Flight Layers
    # ─────────────────────────────────────────────────────────────────────────
    active_layers = list(Layer.objects.exclude(state=JobState.FINISHED).select_related("job"))
    with transaction.atomic():
        for layer in active_layers:
            # Query true counts from DB
            counts = Task.objects.filter(layer=layer).aggregate(
                total=Count("id"),
                waiting=Count("id", filter=Q(state=TaskState.WAITING)),
                ready=Count("id", filter=Q(state=TaskState.READY)),
                running=Count("id", filter=Q(state__in=[TaskState.RUNNING, TaskState.CHECKPOINT])),
                succeeded=Count("id", filter=Q(state=TaskState.SUCCEEDED)),
                failed=Count("id", filter=Q(state=TaskState.FAILED)),
                skipped=Count("id", filter=Q(state=TaskState.SKIPPED)),
            )

            # Determine expected macro state
            total = counts["total"] or 0
            succeeded = counts["succeeded"] or 0
            skipped = counts["skipped"] or 0
            running = counts["running"] or 0
            ready = counts["ready"] or 0
            failed = counts["failed"] or 0
            waiting = counts["waiting"] or 0

            if total > 0 and (succeeded + skipped == total):
                expected_state = JobState.FINISHED
            elif running == 0 and ready == 0 and waiting == 0 and failed > 0:
                expected_state = JobState.FAILED
            elif running > 0:
                expected_state = JobState.RUNNING
            else:
                expected_state = JobState.PENDING

            needs_update = (
                layer.total_tasks != total
                or layer.waiting_tasks != waiting
                or layer.ready_tasks != ready
                or layer.running_tasks != running
                or layer.succeeded_tasks != succeeded
                or layer.failed_tasks != failed
                or layer.skipped_tasks != skipped
                or layer.state != expected_state
            )

            if needs_update:
                layer.total_tasks = total
                layer.waiting_tasks = waiting
                layer.ready_tasks = ready
                layer.running_tasks = running
                layer.succeeded_tasks = succeeded
                layer.failed_tasks = failed
                layer.skipped_tasks = skipped
                layer.state = expected_state
                layer.save(
                    update_fields=[
                        "total_tasks",
                        "waiting_tasks",
                        "ready_tasks",
                        "running_tasks",
                        "succeeded_tasks",
                        "failed_tasks",
                        "skipped_tasks",
                        "state",
                    ]
                )
                reconciled_layers += 1

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Counter & State Reconciliation for In-Flight Jobs
    # ─────────────────────────────────────────────────────────────────────────
    active_jobs = list(Job.objects.exclude(state=JobState.FINISHED))
    with transaction.atomic():
        for job in active_jobs:
            counts = Task.objects.filter(job=job).aggregate(
                total=Count("id"),
                waiting=Count("id", filter=Q(state=TaskState.WAITING)),
                ready=Count("id", filter=Q(state=TaskState.READY)),
                running=Count("id", filter=Q(state__in=[TaskState.RUNNING, TaskState.CHECKPOINT])),
                succeeded=Count("id", filter=Q(state=TaskState.SUCCEEDED)),
                failed=Count("id", filter=Q(state=TaskState.FAILED)),
                skipped=Count("id", filter=Q(state=TaskState.SKIPPED)),
            )

            total = counts["total"] or 0
            succeeded = counts["succeeded"] or 0
            skipped = counts["skipped"] or 0
            running = counts["running"] or 0
            ready = counts["ready"] or 0
            failed = counts["failed"] or 0
            waiting = counts["waiting"] or 0

            if total > 0 and (succeeded + skipped == total):
                expected_state = JobState.FINISHED
            elif running == 0 and ready == 0 and waiting == 0 and failed > 0:
                expected_state = JobState.FAILED
            elif job.is_paused:
                expected_state = JobState.PAUSED
            elif running > 0:
                expected_state = JobState.RUNNING
            else:
                expected_state = JobState.PENDING

            needs_update = (
                job.total_tasks != total
                or job.waiting_tasks != waiting
                or job.ready_tasks != ready
                or job.running_tasks != running
                or job.succeeded_tasks != succeeded
                or job.failed_tasks != failed
                or job.skipped_tasks != skipped
                or job.state != expected_state
            )

            if needs_update:
                job.total_tasks = total
                job.waiting_tasks = waiting
                job.ready_tasks = ready
                job.running_tasks = running
                job.succeeded_tasks = succeeded
                job.failed_tasks = failed
                job.skipped_tasks = skipped
                job.state = expected_state
                if expected_state in (JobState.FINISHED, JobState.FAILED) and not job.stopped_at:
                    job.stopped_at = now
                job.save(
                    update_fields=[
                        "total_tasks",
                        "waiting_tasks",
                        "ready_tasks",
                        "running_tasks",
                        "succeeded_tasks",
                        "failed_tasks",
                        "skipped_tasks",
                        "state",
                        "stopped_at",
                        "updated_at",
                    ]
                )
                reconciled_jobs += 1

    if reconciled_jobs or reconciled_layers or timed_out_tasks_requeued or timed_out_tasks_failed:
        logger.info(
            "Reconciled queue: %d jobs, %d layers, %d tasks requeued, %d tasks failed on timeout.",
            reconciled_jobs,
            reconciled_layers,
            timed_out_tasks_requeued,
            timed_out_tasks_failed,
        )

    return {
        "reconciled_jobs": reconciled_jobs,
        "reconciled_layers": reconciled_layers,
        "timed_out_tasks_requeued": timed_out_tasks_requeued,
        "timed_out_tasks_failed": timed_out_tasks_failed,
    }
