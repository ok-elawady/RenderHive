import logging
import requests
from typing import Any, Dict, List, Optional
from django.conf import settings

from .base import TaskScore

logger = logging.getLogger(__name__)

# Maximum absolute value the AI service is allowed to adjust a base score by.
# This keeps the AI as a tie-breaker and prevents it from overriding job priorities
# set by artists. Must match the score_delta range documented in prompts.py.
AI_SCORE_DELTA_MAX = 0.20

class AIScoreAdjuster:
    """Client for the external FastAPI AI Scheduler service."""
    
    def __init__(self, worker: Any):
        self.worker = worker
        # Default to localhost if not configured in settings.
        # IMPORTANT: Set SCHEDULER_AI_URL in your environment for production.
        self.ai_url = getattr(settings, "SCHEDULER_AI_URL", "http://localhost:8000/api/v1/rank-tasks")
        # Default timeout of 5 seconds. LLM inference is slow; 2s is too aggressive.
        # Set SCHEDULER_AI_TIMEOUT in settings to override.
        self.timeout = getattr(settings, "SCHEDULER_AI_TIMEOUT", 5.0)
        
    def adjust(self, task_scores: List[TaskScore], capabilities_snapshot: Optional[dict] = None) -> List[TaskScore]:
        if not task_scores:
            return []
            
        worker_caps = {}
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
            
        candidate_payloads = []
        for ts in task_scores:
            candidate_payloads.append({
                "task_id": str(ts.task.id),
                "priority": ts.task.job.priority,
                "base_score": ts.base_score,
                "scene_info": ts.task.layer.scene_info if isinstance(ts.task.layer.scene_info, dict) else {}
            })
            
        payload = {
            "worker_caps": worker_caps,
            "tasks": candidate_payloads
        }
        
        try:
            resp = requests.post(self.ai_url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            
            ai_results = resp.json()

            # Guard: the service must return a list, not a dict (e.g. error payload).
            if not isinstance(ai_results, list):
                logger.warning(
                    f"AI Scheduler returned unexpected response type {type(ai_results).__name__!r}. "
                    "Falling back to base scores."
                )
                return list(task_scores)

            delta_map = {item["task_id"]: item for item in ai_results}
            
            for ts in task_scores:
                task_id_str = str(ts.task.id)
                if task_id_str in delta_map:
                    delta = float(delta_map[task_id_str].get("score_delta", 0.0))
                    reason = str(delta_map[task_id_str].get("reason", ""))

                    # Clamp delta to ±AI_SCORE_DELTA_MAX to prevent the AI from
                    # completely overriding base priorities set by the artist.
                    delta = max(min(delta, AI_SCORE_DELTA_MAX), -AI_SCORE_DELTA_MAX)

                    ts.ai_adjustment = delta
                    ts.final_score = ts.base_score + delta
                    ts.score_breakdown["ai_adjustment"] = delta
                    ts.score_breakdown["ai_reason"] = reason
                    ts.scorer_version = "v1.1-ai"

            # Return a new sorted list; do NOT mutate the caller's list in place.
            return sorted(task_scores, key=lambda ts: ts.final_score, reverse=True)
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"AI Scheduler request failed ({type(e).__name__}): {e}. Falling back to base scores.")
            return list(task_scores)
        except Exception as e:
            logger.exception(f"Unexpected error in AI Scheduler client. Falling back to base scores.")
            return list(task_scores)
