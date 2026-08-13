import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Upper bound for dispatch_order when computing the ordering penalty.
# Tasks with dispatch_order >= this constant all receive an equal (maximum)
# penalty so that very long layers (> MAX_ORDER_SCALE tasks) do not produce
# out-of-range scores. Increase if you routinely submit layers with more tasks.
MAX_ORDER_SCALE = 10_000

@dataclass
class TaskScore:
    task: Any
    base_score: float = 0.0
    ai_adjustment: float = 0.0
    final_score: float = 0.0
    # Values are floats for numeric factors, but strings are also stored
    # for "ai_reason" and "_floor_clamp" — hence Dict[str, Any].
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    scorer_version: str = "v1.0"


class BaseScorer:
    """Deterministic scoring of tasks against a worker's constraints."""
    
    def score(self, worker: Any, tasks: List[Any]) -> List[TaskScore]:
        """
        Score a list of tasks for the given worker.
        Higher score is better.
        """
        scored = []
        for task in tasks:
            base, breakdown = self._calculate_base_score(worker, task)
            ts = TaskScore(
                task=task,
                base_score=base,
                final_score=base,
                score_breakdown=breakdown
            )
            scored.append(ts)
            
        # Sort highest base score first
        scored.sort(key=lambda ts: ts.base_score, reverse=True)
        return scored

    def _calculate_base_score(self, worker: Any, task: Any) -> tuple[float, Dict[str, float]]:
        breakdown = {}
        
        # 1. Job Priority (0 to 1 scale, weight: 40%)
        # job.priority is 1-100
        priority_val = (task.job.priority / 100.0) * 0.40
        breakdown["job_priority"] = priority_val
        
        # 2. Failure Penalty (Subtract based on retries, weight: 10%)
        # More retries = lower score to prevent failing tasks from starving the queue
        retry_penalty = 0.0
        if task.max_retries > 0:
            retry_penalty = (task.retries / task.max_retries) * 0.10
        breakdown["failure_penalty"] = -retry_penalty
        
        # 3. Resource Fit (weight: 20%)
        # Reward workers whose available resources are a close, efficient match to the
        # task's minimum requirements. A perfect fit (worker has exactly min_cores and
        # min_memory_mb) scores 1.0. Excess capacity is penalised to preserve large
        # machines for tasks that actually need them, but the penalty is asymptotic so
        # a 2× excess still scores 0.5 and a worker is never excluded by this factor.
        resource_fit = 0.0
        if worker:
            layer = task.layer

            worker_cores = max(int(worker.cores or 1), 1)
            worker_memory = max(int(worker.memory_mb or 1), 1)

            # ratio = min_needed / available.  1.0 = perfect fit, 0.5 = worker has 2× excess.
            core_ratio = min(layer.min_cores / worker_cores, 1.0)
            mem_ratio = min(layer.min_memory_mb / worker_memory, 1.0)

            fit = (core_ratio + mem_ratio) / 2.0
            resource_fit = fit * 0.20

        breakdown["resource_fit"] = resource_fit

        # 4. Dispatch Order Tiebreaker (small weight to maintain frame sequence)
        # Subtract a tiny amount based on dispatch_order so earlier frames are preferred.
        # Capped at MAX_ORDER_SCALE so very long layers don't push scores negative.
        order_penalty = (min(task.dispatch_order, MAX_ORDER_SCALE) / MAX_ORDER_SCALE) * 0.05
        breakdown["dispatch_order"] = -order_penalty

        raw_score = sum(breakdown.values())
        base_score = max(raw_score, 0.0)

        # If the score was clamped to zero, add a synthetic _floor_clamp entry
        # equal to the deficit so that sum(breakdown.values()) == base_score (0.0).
        # Without this the breakdown fields sum to a negative number, which makes
        # the Django Admin audit trail misleading.
        if raw_score < 0.0:
            breakdown["_floor_clamp"] = -raw_score

        return base_score, breakdown
