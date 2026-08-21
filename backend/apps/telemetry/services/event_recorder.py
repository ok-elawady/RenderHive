import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

from apps.telemetry.models import DispatchTrace, EventSeverity, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot

logger = logging.getLogger(__name__)

MAX_LOG_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB ceiling


def truncate_log_output(log_text: str, max_bytes: int = MAX_LOG_SIZE_BYTES) -> str:
    """Safely truncate log text if it exceeds the maximum size limit.

    Preserves the first 500 KB (initialization/command parameters) and the last
    1.5 MB (terminal output / error trace) with a clear delimiter.
    """
    if not log_text or len(log_text.encode("utf-8", errors="replace")) <= max_bytes:
        return log_text or ""

    head_chars = 250_000
    tail_chars = 750_000
    if len(log_text) <= (head_chars + tail_chars):
        return log_text

    delimiter = (
        "\n\n"
        + "=" * 40
        + "\n[RENDERHIVE LOG TRUNCATED: Output exceeded 2MB maximum limit]\n"
        + "=" * 40
        + "\n\n"
    )
    return log_text[:head_chars] + delimiter + log_text[-tail_chars:]


def record_task_log(
    task: Any,
    worker_hostname: str,
    exit_status: int,
    log_output: str = "",
    error_tail: str = "",
    duration_seconds: float = 0.0,
    peak_memory_mb: int = 0,
    output_image_path: str = "",
    attempt_number: Optional[int] = None,
) -> Optional[TaskExecutionLog]:
    """Record execution output, diagnostics, and metrics for a task attempt."""
    try:
        if attempt_number is None:
            attempt_number = getattr(task, "retries", 0) + 1

        sanitized_log = truncate_log_output(log_output)
        sanitized_tail = str(error_tail or "").strip()
        if not sanitized_tail and exit_status != 0 and sanitized_log:
            lines = sanitized_log.splitlines()
            sanitized_tail = "\n".join(lines[-25:]).strip()

        return TaskExecutionLog.objects.create(
            task=task,
            job=task.job,
            attempt_number=attempt_number,
            worker_hostname=str(worker_hostname or "unknown"),
            exit_status=int(exit_status),
            duration_seconds=max(0.0, float(duration_seconds or 0.0)),
            peak_memory_mb=max(0, int(peak_memory_mb or 0)),
            output_image_path=str(output_image_path or "")[:2048],
            error_tail=sanitized_tail,
            log_output=sanitized_log,
        )
    except Exception as exc:
        logger.exception("Failed to record task execution log for task %s: %s", getattr(task, "pk", "unknown"), exc)
        return None


def record_dispatch_trace(
    task: Any,
    job: Any,
    worker_hostname: str,
    candidate_count: int = 1,
    ai_invoked: bool = False,
    ai_latency_ms: Optional[float] = None,
    ai_reason: str = "",
    score_breakdown: Optional[Dict[str, Any]] = None,
) -> Optional[DispatchTrace]:
    """Record a scheduler dispatch decision, scoring breakdown, and AI reasoning."""
    try:
        return DispatchTrace.objects.create(
            task=task,
            job=job,
            worker_hostname=str(worker_hostname or "unknown"),
            candidate_count=max(1, int(candidate_count or 1)),
            ai_invoked=bool(ai_invoked),
            ai_latency_ms=float(ai_latency_ms) if ai_latency_ms is not None else None,
            ai_reason=str(ai_reason or ""),
            score_breakdown=score_breakdown or {},
        )
    except Exception as exc:
        logger.exception("Failed to record dispatch trace: %s", exc)
        return None


def record_event(
    event_type: str,
    message: str,
    actor_username: str = "",
    target_type: str = "",
    target_id: str = "",
    target_name: str = "",
    payload: Optional[Dict[str, Any]] = None,
    severity: str = EventSeverity.INFO,
) -> Optional[FarmEvent]:
    """Record an audit trail event across the render farm."""
    try:
        resolved_payload = payload or {}
        resolved_name = target_name
        if not resolved_name:
            resolved_name = str(
                resolved_payload.get("hostname")
                or resolved_payload.get("worker_hostname")
                or resolved_payload.get("worker_name")
                or resolved_payload.get("worker")
                or resolved_payload.get("job_name")
                or resolved_payload.get("task_name")
                or resolved_payload.get("name")
                or ""
            )

        return FarmEvent.objects.create(
            event_type=str(event_type or "GENERAL_EVENT")[:64],
            severity=severity if severity in EventSeverity.values else EventSeverity.INFO,
            actor_username=str(actor_username or "system")[:64],
            target_type=str(target_type or "")[:32],
            target_id=str(target_id or "")[:64],
            target_name=str(resolved_name)[:128],
            message=str(message or "")[:512],
            payload=resolved_payload,
        )
    except Exception as exc:
        logger.exception("Failed to record farm event: %s", exc)
        return None


def record_worker_metrics(
    worker_hostname: str,
    cpu_percent: float = 0.0,
    memory_used_mb: int = 0,
    memory_total_mb: int = 4096,
    vram_percent: float = 0.0,
    active_tasks: int = 0,
    force: bool = False,
) -> Optional[WorkerMetricSnapshot]:
    """Record a hardware telemetry sample for a worker node.

    Throttles snapshot creation to TELEMETRY_WORKER_METRIC_INTERVAL_SECONDS
    (default: 60s) unless force=True to prevent database bloat from high-frequency heartbeats.
    """
    hostname = str(worker_hostname or "unknown")
    interval = getattr(settings, "TELEMETRY_WORKER_METRIC_INTERVAL_SECONDS", 60)

    if not force and interval > 0:
        cache_key = f"telemetry:worker_metric_lock:{hostname}"
        if not cache.add(cache_key, 1, timeout=interval):
            return None

    try:
        return WorkerMetricSnapshot.objects.create(
            worker_hostname=hostname,
            cpu_percent=max(0.0, min(100.0, float(cpu_percent or 0.0))),
            memory_used_mb=max(0, int(memory_used_mb or 0)),
            memory_total_mb=max(1, int(memory_total_mb or 4096)),
            vram_percent=max(0.0, min(100.0, float(vram_percent or 0.0))),
            active_tasks=max(0, int(active_tasks or 0)),
        )
    except Exception as exc:
        logger.exception("Failed to record worker metric sample for %s: %s", hostname, exc)
        return None

