import logging
import time
import threading
import requests
from typing import Any, Dict, List, Optional
from django.conf import settings

from .base import TaskScore

logger = logging.getLogger(__name__)

# Maximum absolute value the AI service is allowed to adjust a base score by.
# This keeps the AI as a tie-breaker and prevents it from overriding job priorities
# set by artists. Must match the score_delta range documented in prompts.py.
AI_SCORE_DELTA_MAX = 0.20

# Maximum tasks to send in a single AI ranking request.
# Must stay in sync with MAX_TASKS_PER_REQUEST in the AI service's main.py.
AI_MAX_TASKS = 10


# ---------------------------------------------------------------------------
# In-process circuit breaker
# ---------------------------------------------------------------------------
# Prevents a downed AI service from stalling every worker dispatch for the full
# timeout duration. After _CB_FAILURE_THRESHOLD consecutive failures, the
# circuit opens and all AI calls are skipped for _CB_COOLDOWN_SECONDS seconds.
# This is a module-level singleton so it persists across requests within the
# same Django process.

_CB_FAILURE_THRESHOLD = 5
_CB_COOLDOWN_SECONDS = 60.0

_cb_lock = threading.Lock()
_cb_failures = 0
_cb_open_until: float = 0.0  # epoch seconds; 0 means circuit is closed


def _circuit_is_open() -> bool:
    """Return True if the circuit breaker is open (AI calls should be skipped)."""
    global _cb_failures, _cb_open_until
    with _cb_lock:
        if _cb_open_until == 0.0:
            return False
        if time.monotonic() < _cb_open_until:
            return True
        # Cooldown has elapsed — transition to closed state.
        # Reset both counters atomically so that only the first post-cooldown
        # caller enters probe mode. Without this reset every concurrent Django
        # worker would simultaneously probe the AI service (thundering herd).
        _cb_open_until = 0.0
        _cb_failures = 0
        return False


def _record_success() -> None:
    """Record a successful AI call, resetting the failure counter."""
    global _cb_failures, _cb_open_until
    with _cb_lock:
        _cb_failures = 0
        _cb_open_until = 0.0


def _record_failure() -> None:
    """Record a failed AI call; open the circuit after the threshold is reached."""
    global _cb_failures, _cb_open_until
    with _cb_lock:
        _cb_failures += 1
        if _cb_failures >= _CB_FAILURE_THRESHOLD:
            _cb_open_until = time.monotonic() + _CB_COOLDOWN_SECONDS
            logger.warning(
                f"AI Scheduler circuit breaker OPENED after {_cb_failures} consecutive failures. "
                f"AI calls will be skipped for {_CB_COOLDOWN_SECONDS:.0f}s."
            )


class AIScoreAdjuster:
    """Client for the external FastAPI AI Scheduler service.

    Includes an in-process circuit breaker that opens after repeated failures,
    preventing a downed AI service from stalling every worker dispatch.
    """

    def __init__(self, worker: Any):
        self.worker = worker
        # IMPORTANT: Set SCHEDULER_AI_URL in your environment for production.
        # Defaults to localhost:8001 — the AI service port, not Django (8000).
        self.ai_url = getattr(settings, "SCHEDULER_AI_URL", "http://localhost:8001/api/v1/rank-tasks")
        # Default timeout of 2.5 seconds to prevent Django worker thread starvation.
        # Set SCHEDULER_AI_TIMEOUT in settings to override.
        self.timeout = getattr(settings, "SCHEDULER_AI_TIMEOUT", 2.5)

    def adjust(self, task_scores: List[TaskScore], capabilities_snapshot: Optional[dict] = None) -> List[TaskScore]:
        if not task_scores:
            return []

        # Fast-path: circuit is open — skip AI entirely
        if _circuit_is_open():
            logger.debug("AI Scheduler circuit breaker is open; using base scores.")
            return list(task_scores)

        worker_caps: Dict[str, Any] = {}
        if self.worker:
            worker_caps = {
                "hostname": self.worker.hostname,
                "cores": self.worker.cores,
                "memory_mb": self.worker.memory_mb,
                "gpu_models": self.worker.gpu_models,
                "capabilities": self.worker.system_info.get("capabilities", {}),
            }

        # Include live stats if the worker payload sent them
        if capabilities_snapshot:
            worker_caps["live_metrics"] = capabilities_snapshot

        # Limit payload size to stay within the AI service's context window.
        capped_scores = task_scores[:AI_MAX_TASKS]

        candidate_payloads = []
        for ts in capped_scores:
            candidate_payloads.append({
                "task_id": str(ts.task.id),
                "priority": ts.task.job.priority,
                "base_score": ts.base_score,
                "scene_info": ts.task.layer.scene_info if isinstance(ts.task.layer.scene_info, dict) else {}
            })

        payload = {
            "worker_caps": worker_caps,
            "tasks": candidate_payloads,
        }

        try:
            t0 = time.monotonic()
            resp = requests.post(self.ai_url, json=payload, timeout=self.timeout)
            latency_ms = (time.monotonic() - t0) * 1000.0
            resp.raise_for_status()

            ai_results = resp.json()

            # Guard: the service must return a list, not a dict (e.g. error payload).
            if not isinstance(ai_results, list):
                logger.warning(
                    f"AI Scheduler returned unexpected response type {type(ai_results).__name__!r}. "
                    "Falling back to base scores."
                )
                _record_failure()
                return list(task_scores)

            _record_success()

            # Stamp the measured HTTP round-trip on every task in the capped set.
            # The caller (TaskDispatchView) reads ai_latency_ms from the winning
            # task to store it in the DispatchTrace telemetry record.
            for ts in capped_scores:
                ts.ai_latency_ms = round(latency_ms, 1)

            delta_map = {item["task_id"]: item for item in ai_results}

            for ts in capped_scores:
                task_id_str = str(ts.task.id)
                if task_id_str in delta_map:
                    delta = float(delta_map[task_id_str].get("score_delta", 0.0))
                    reason = str(delta_map[task_id_str].get("reason", ""))

                    # Clamp delta to ±AI_SCORE_DELTA_MAX to prevent the AI from
                    # completely overriding base priorities set by the artist.
                    delta = max(min(delta, AI_SCORE_DELTA_MAX), -AI_SCORE_DELTA_MAX)

                    ts.ai_adjustment = delta
                    ts.final_score = ts.base_score + delta
                    # Store ai_adjustment and reason in the breakdown separately;
                    # the numeric breakdown fields (job_priority, resource_fit, etc.)
                    # already correctly sum to base_score. final_score = base_score + ai_adjustment.
                    ts.score_breakdown["ai_adjustment"] = delta
                    ts.score_breakdown["ai_reason"] = reason
                    ts.scorer_version = "v1.1-ai"

            # Return a new sorted list; do NOT mutate the caller's list in place.
            return sorted(task_scores, key=lambda ts: ts.final_score, reverse=True)

        except requests.exceptions.RequestException as e:
            logger.warning(f"AI Scheduler request failed ({type(e).__name__}): {e}. Falling back to base scores.")
            _record_failure()
            return list(task_scores)
        except Exception:
            logger.exception("Unexpected error in AI Scheduler client. Falling back to base scores.")
            _record_failure()
            return list(task_scores)
