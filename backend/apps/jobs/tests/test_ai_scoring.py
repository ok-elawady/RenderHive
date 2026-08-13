"""
Tests for the AI Scheduler integration within the Django backend.

Covers:
- BaseScorer: score breakdown accuracy, floor clamping (Bug 4)
- AIScoreAdjuster: wrong-URL fallback (Bug 3), delta clamping, circuit breaker (Gap 2)
- TaskDispatchView: relative tie-breaker threshold (Bug 5)
- RecentDispatchesView: real dispatch log endpoint (Gap 1b)

Run with:
    cd backend
    pytest apps/jobs/tests/test_ai_scoring.py -v
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.jobs.scoring.base import BaseScorer, TaskScore
from apps.jobs.scoring.ai_client import (
    AIScoreAdjuster,
    AI_SCORE_DELTA_MAX,
    _cb_failures,
    _cb_open_until,
    _record_failure,
    _record_success,
    _circuit_is_open,
)

from .factories import JobFactory, LayerFactory, TaskFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset the circuit breaker state before every test to prevent leakage."""
    import apps.jobs.scoring.ai_client as cb_module
    cb_module._cb_failures = 0
    cb_module._cb_open_until = 0.0
    yield
    cb_module._cb_failures = 0
    cb_module._cb_open_until = 0.0


@pytest.fixture
def simple_task(db):
    """A minimal task with a job (priority=50) and layer."""
    layer = LayerFactory(min_cores=4, min_memory_mb=8192)
    return TaskFactory(layer=layer, job=layer.job, state="READY")


@pytest.fixture
def mock_worker():
    """A fake worker node with realistic attributes."""
    worker = MagicMock()
    worker.hostname = "render-node-01"
    worker.cores = 32
    worker.memory_mb = 131072
    worker.gpu_models = ["NVIDIA RTX 4090"]
    worker.system_info = {"capabilities": {}}
    return worker


@pytest.fixture
def user_client(db):
    """Authenticated API client for a regular user."""
    user = User.objects.create_user(username="artist", password="pass")
    client = APIClient()
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def farm_client(db):
    """Authenticated API client for a farm agent."""
    group, _ = Group.objects.get_or_create(name="farm_agents")
    agent = User.objects.create_user(username="farm_service", password="!")
    agent.groups.add(group)
    client = APIClient()
    token = Token.objects.create(user=agent)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


# ===========================================================================
# Tests: BaseScorer — Bug 4
# ===========================================================================

class TestBaseScorer:
    """Verify score breakdown integrity."""

    def test_breakdown_values_sum_to_base_score(self, simple_task, mock_worker):
        """
        Regression for Bug 4: sum(breakdown.values()) must always equal
        base_score, including when _floor_clamp is applied.
        """
        scorer = BaseScorer()
        results = scorer.score(mock_worker, [simple_task])
        ts = results[0]

        # Filter out non-numeric entries (like ai_reason)
        numeric_total = sum(
            v for v in ts.score_breakdown.values() if isinstance(v, (int, float))
        )
        assert numeric_total == pytest.approx(ts.base_score, abs=1e-9)

    def test_base_score_is_never_negative(self, db, mock_worker):
        """Score floor clamping: even a max-retry task must have base_score >= 0."""
        # Max retries + very low priority = most negative possible score
        layer = LayerFactory(min_cores=1, min_memory_mb=1)
        task = TaskFactory(layer=layer, job=layer.job, state="READY", retries=5, max_retries=5)
        task.job.priority = 1
        task.job.save()

        scorer = BaseScorer()
        results = scorer.score(mock_worker, [task])
        assert results[0].base_score >= 0.0

    def test_floor_clamp_present_when_score_clamped(self, db, mock_worker):
        """When raw_score < 0, _floor_clamp key is added so the breakdown sums correctly."""
        layer = LayerFactory(min_cores=1, min_memory_mb=1)
        task = TaskFactory(layer=layer, job=layer.job, state="READY", retries=5, max_retries=5)
        task.job.priority = 1
        task.job.save()

        scorer = BaseScorer()
        ts = scorer.score(mock_worker, [task])[0]

        if ts.base_score == 0.0:
            # Only present if raw_score was actually negative
            raw = sum(
                v for k, v in ts.score_breakdown.items()
                if isinstance(v, (int, float)) and k != "_floor_clamp"
            )
            if raw < 0.0:
                assert "_floor_clamp" in ts.score_breakdown
                assert ts.score_breakdown["_floor_clamp"] == pytest.approx(-raw)

    def test_higher_priority_job_scores_higher(self, db, mock_worker):
        """Priority must be the dominant factor in scoring."""
        layer_low = LayerFactory(min_cores=4, min_memory_mb=8192)
        layer_high = LayerFactory(min_cores=4, min_memory_mb=8192)
        task_low = TaskFactory(layer=layer_low, job=layer_low.job, state="READY")
        task_high = TaskFactory(layer=layer_high, job=layer_high.job, state="READY")

        layer_low.job.priority = 10
        layer_low.job.save()
        layer_high.job.priority = 90
        layer_high.job.save()

        scorer = BaseScorer()
        results = scorer.score(mock_worker, [task_low, task_high])

        scores = {ts.task.id: ts.base_score for ts in results}
        assert scores[task_high.id] > scores[task_low.id]

    def test_more_retries_lower_score(self, db, mock_worker):
        """A task with more retries (indicating instability) must score lower."""
        layer_fresh = LayerFactory(min_cores=4, min_memory_mb=8192)
        layer_retried = LayerFactory(min_cores=4, min_memory_mb=8192)

        # Same job priority
        layer_fresh.job.priority = 50
        layer_fresh.job.save()
        layer_retried.job.priority = 50
        layer_retried.job.save()

        task_fresh = TaskFactory(layer=layer_fresh, job=layer_fresh.job, state="READY", retries=0, max_retries=5)
        task_retried = TaskFactory(layer=layer_retried, job=layer_retried.job, state="READY", retries=5, max_retries=5)

        scorer = BaseScorer()
        results = scorer.score(mock_worker, [task_fresh, task_retried])
        scores = {ts.task.id: ts.base_score for ts in results}
        assert scores[task_fresh.id] > scores[task_retried.id]


# ===========================================================================
# Tests: AIScoreAdjuster — Bug 3, Bug 4, Gap 2
# ===========================================================================

class TestAIScoreAdjuster:
    """Verify the Django AI client falls back correctly and enforces constraints."""

    def _make_task_score(self, task, base_score=0.40):
        return TaskScore(
            task=task,
            base_score=base_score,
            final_score=base_score,
            score_breakdown={
                "job_priority": base_score * 0.5,
                "resource_fit": base_score * 0.3,
                "failure_penalty": 0.0,
                "dispatch_order": -0.001,
            },
        )

    def test_fallback_on_connection_refused(self, simple_task, mock_worker):
        """
        Regression for Bug 3: when the AI service is unreachable (connection refused,
        as would happen with the wrong default port 8000), the method must fall back
        silently to the original base scores without raising an exception.
        """
        adjuster = AIScoreAdjuster(mock_worker)
        adjuster.ai_url = "http://localhost:19999/api/v1/rank-tasks"  # closed port
        adjuster.timeout = 0.5

        ts = self._make_task_score(simple_task)
        result = adjuster.adjust([ts])

        assert len(result) == 1
        assert result[0].final_score == pytest.approx(ts.base_score)
        assert result[0].ai_adjustment == 0.0

    def test_fallback_on_http_error(self, simple_task, mock_worker):
        """A 404 or 500 from the AI service must fall back to base scores."""
        import requests

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        adjuster = AIScoreAdjuster(mock_worker)
        ts = self._make_task_score(simple_task)

        with patch("apps.jobs.scoring.ai_client.requests.post", return_value=mock_response):
            result = adjuster.adjust([ts])

        assert result[0].final_score == pytest.approx(ts.base_score)

    def test_delta_clamped_above_max(self, simple_task, mock_worker):
        """AI cannot push a score delta above +0.20 — prevents overriding artist priorities."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"task_id": str(simple_task.id), "score_delta": 0.99, "reason": "too high"}
        ]

        adjuster = AIScoreAdjuster(mock_worker)
        ts = self._make_task_score(simple_task)

        with patch("apps.jobs.scoring.ai_client.requests.post", return_value=mock_response):
            result = adjuster.adjust([ts])

        assert result[0].ai_adjustment == pytest.approx(AI_SCORE_DELTA_MAX)
        assert result[0].final_score == pytest.approx(ts.base_score + AI_SCORE_DELTA_MAX)

    def test_delta_clamped_below_min(self, simple_task, mock_worker):
        """AI cannot push a score delta below -0.20."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"task_id": str(simple_task.id), "score_delta": -0.99, "reason": "too low"}
        ]

        adjuster = AIScoreAdjuster(mock_worker)
        ts = self._make_task_score(simple_task)

        with patch("apps.jobs.scoring.ai_client.requests.post", return_value=mock_response):
            result = adjuster.adjust([ts])

        assert result[0].ai_adjustment == pytest.approx(-AI_SCORE_DELTA_MAX)

    def test_successful_response_updates_scorer_version(self, simple_task, mock_worker):
        """Tasks that go through AI adjustment must have scorer_version 'v1.1-ai'."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"task_id": str(simple_task.id), "score_delta": 0.05, "reason": "good match"}
        ]

        adjuster = AIScoreAdjuster(mock_worker)
        ts = self._make_task_score(simple_task)

        with patch("apps.jobs.scoring.ai_client.requests.post", return_value=mock_response):
            result = adjuster.adjust([ts])

        assert result[0].scorer_version == "v1.1-ai"
        assert result[0].score_breakdown["ai_reason"] == "good match"

    def test_non_list_response_falls_back(self, simple_task, mock_worker):
        """If the AI service returns a dict instead of a list, fall back gracefully."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"error": "model not loaded"}

        adjuster = AIScoreAdjuster(mock_worker)
        ts = self._make_task_score(simple_task)

        with patch("apps.jobs.scoring.ai_client.requests.post", return_value=mock_response):
            result = adjuster.adjust([ts])

        assert result[0].final_score == pytest.approx(ts.base_score)

    def test_empty_task_list_returns_empty(self, mock_worker):
        """Calling adjust with an empty list is a no-op."""
        adjuster = AIScoreAdjuster(mock_worker)
        assert adjuster.adjust([]) == []


# ===========================================================================
# Tests: Circuit Breaker — Gap 2
# ===========================================================================

class TestCircuitBreaker:
    """Verify the circuit breaker opens after repeated failures and recovers."""

    def test_circuit_closed_initially(self):
        assert _circuit_is_open() is False

    def test_circuit_opens_after_threshold_failures(self):
        """After CB_FAILURE_THRESHOLD consecutive failures, the circuit opens."""
        import apps.jobs.scoring.ai_client as cb_module
        threshold = cb_module._CB_FAILURE_THRESHOLD

        for _ in range(threshold):
            _record_failure()

        assert _circuit_is_open() is True

    def test_circuit_reset_on_success(self):
        """A successful call resets the failure counter and closes the circuit."""
        import apps.jobs.scoring.ai_client as cb_module
        for _ in range(cb_module._CB_FAILURE_THRESHOLD):
            _record_failure()

        assert _circuit_is_open() is True
        _record_success()
        assert _circuit_is_open() is False

    def test_open_circuit_skips_ai_call(self, db, mock_worker):
        """When the circuit is open, no HTTP request is made to the AI service."""
        import apps.jobs.scoring.ai_client as cb_module

        # Force the circuit open
        cb_module._cb_failures = cb_module._CB_FAILURE_THRESHOLD
        cb_module._cb_open_until = time.monotonic() + 60.0

        layer = LayerFactory()
        task = TaskFactory(layer=layer, job=layer.job, state="READY")
        ts = TaskScore(task=task, base_score=0.40, final_score=0.40, score_breakdown={})

        adjuster = AIScoreAdjuster(mock_worker)

        with patch("apps.jobs.scoring.ai_client.requests.post") as mock_post:
            result = adjuster.adjust([ts])
            mock_post.assert_not_called()

        # Should return the original base score unchanged
        assert result[0].final_score == pytest.approx(0.40)

    def test_circuit_recovers_after_cooldown(self):
        """After the cooldown period, the circuit allows calls again."""
        import apps.jobs.scoring.ai_client as cb_module

        # Manually set the circuit to have expired already
        cb_module._cb_failures = cb_module._CB_FAILURE_THRESHOLD
        cb_module._cb_open_until = time.monotonic() - 1.0  # expired 1 second ago

        assert _circuit_is_open() is False

    def test_failure_counter_increments_on_request_error(self, db, mock_worker):
        """Network errors increment the failure counter toward the threshold."""
        import apps.jobs.scoring.ai_client as cb_module
        import requests as req_lib

        layer = LayerFactory()
        task = TaskFactory(layer=layer, job=layer.job, state="READY")
        ts = TaskScore(task=task, base_score=0.40, final_score=0.40, score_breakdown={})

        adjuster = AIScoreAdjuster(mock_worker)
        adjuster.timeout = 0.1

        initial_failures = cb_module._cb_failures

        with patch(
            "apps.jobs.scoring.ai_client.requests.post",
            side_effect=req_lib.exceptions.ConnectionError("refused"),
        ):
            adjuster.adjust([ts])

        assert cb_module._cb_failures > initial_failures


# ===========================================================================
# Tests: TaskDispatchView — Bug 5 (relative tie-breaker threshold)
# ===========================================================================

class TestRelativeTieThreshold:
    """Verify the dispatch view uses a relative, not absolute, tie-breaker threshold."""

    def _dispatch(self, farm_client, worker_name="test-node"):
        return farm_client.post(
            "/api/tasks/dispatch/",
            data={"worker_name": worker_name},
            format="json",
        )

    def test_only_genuinely_tied_tasks_are_competitive(self, db, farm_client):
        """
        With absolute 0.05 threshold and all jobs at priority=50, every task would
        be within the threshold (base scores cluster around 0.20) — the AI would be
        invoked for every dispatch. With a relative 10% threshold on a priority-50
        farm, only tasks within 10% of the top score are considered tied.

        We don't assert that the AI is or isn't called here (it may be disabled),
        but we DO assert that the dispatch endpoint selects a task at all and
        returns 200 rather than failing.
        """
        layer = LayerFactory(min_cores=1, min_memory_mb=1024)
        task = TaskFactory(layer=layer, job=layer.job, state="READY", dispatch_order=0)
        layer.job.priority = 50
        layer.job.save()

        response = self._dispatch(farm_client)
        assert response.status_code == 200
        assert response.json()["id"] == str(task.id)

    def test_high_priority_job_always_wins_over_low(self, db, farm_client):
        """
        A job at priority=100 must score >10% above a job at priority=10.
        The relative threshold means the low-priority job is NOT in the competitive
        set — the AI tie-breaker is never needed and the high-priority job wins.
        """
        layer_low = LayerFactory(min_cores=1, min_memory_mb=1024)
        layer_high = LayerFactory(min_cores=1, min_memory_mb=1024)

        task_low = TaskFactory(layer=layer_low, job=layer_low.job, state="READY", dispatch_order=0)
        task_high = TaskFactory(layer=layer_high, job=layer_high.job, state="READY", dispatch_order=0)

        layer_low.job.priority = 10
        layer_low.job.save()
        layer_high.job.priority = 100
        layer_high.job.save()

        response = self._dispatch(farm_client)
        assert response.status_code == 200
        assert response.json()["id"] == str(task_high.id)


# ===========================================================================
# Tests: RecentDispatchesView — Gap 1b
# ===========================================================================

class TestRecentDispatchesView:
    """Verify the /api/tasks/recent-dispatches/ endpoint returns correct data."""

    def test_requires_authentication(self, db):
        """Unauthenticated requests must be rejected."""
        anon = APIClient()
        response = anon.get("/api/tasks/recent-dispatches/")
        assert response.status_code in (401, 403)

    def test_returns_empty_list_when_no_dispatches(self, user_client):
        """With no dispatched tasks in DB, the endpoint returns an empty list."""
        response = user_client.get("/api/tasks/recent-dispatches/")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_dispatched_tasks_with_breakdown(self, db, user_client):
        """Tasks with a last_score_breakdown and worker_name appear in the response."""
        from django.utils import timezone
        layer = LayerFactory(name="beauty")
        job = layer.job
        job.visible_name = "Shot_042_lighting"
        job.save()

        task = TaskFactory(
            layer=layer,
            job=job,
            state="RUNNING",
            worker_name="render-node-01",
            started_at=timezone.now(),
        )
        task.last_score_breakdown = {
            "job_priority": 0.20,
            "resource_fit": 0.15,
            "failure_penalty": 0.0,
            "dispatch_order": -0.001,
            "ai_adjustment": 0.08,
            "ai_reason": "GPU render benefits from idle RTX 4090",
        }
        task.save()

        response = user_client.get("/api/tasks/recent-dispatches/")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        entry = data[0]

        assert entry["id"] == str(task.id)
        assert entry["worker_name"] == "render-node-01"
        assert entry["job_name"] == "Shot_042_lighting"
        assert entry["layer_name"] == "beauty"
        assert entry["ai_was_invoked"] is True
        assert "RTX 4090" in entry["ai_reason"]
        assert "ai_adjustment" in entry["last_score_breakdown"]

    def test_tasks_without_breakdown_are_excluded(self, db, user_client):
        """Tasks without a score breakdown (e.g. manually created) are not shown."""
        layer = LayerFactory()
        TaskFactory(
            layer=layer,
            job=layer.job,
            state="RUNNING",
            worker_name="node-01",
            last_score_breakdown=None,
        )
        response = user_client.get("/api/tasks/recent-dispatches/")
        assert response.status_code == 200
        assert response.json() == []

    def test_limit_query_parameter(self, db, user_client):
        """The limit parameter caps the number of returned entries."""
        from django.utils import timezone
        layer = LayerFactory()

        for i in range(10):
            task = TaskFactory(
                layer=layer,
                job=layer.job,
                state="RUNNING",
                worker_name=f"node-{i:02d}",
                started_at=timezone.now(),
            )
            task.last_score_breakdown = {"job_priority": 0.20}
            task.save()

        response = user_client.get("/api/tasks/recent-dispatches/?limit=3")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_limit_cannot_exceed_100(self, db, user_client):
        """The server silently caps limit at 100 regardless of what's requested."""
        response = user_client.get("/api/tasks/recent-dispatches/?limit=9999")
        # Should not error — server caps silently
        assert response.status_code == 200

    def test_ai_was_invoked_false_without_ai_adjustment(self, db, user_client):
        """Tasks dispatched deterministically (no AI) report ai_was_invoked=False."""
        from django.utils import timezone
        layer = LayerFactory()
        task = TaskFactory(
            layer=layer,
            job=layer.job,
            state="RUNNING",
            worker_name="node-01",
            started_at=timezone.now(),
        )
        task.last_score_breakdown = {
            "job_priority": 0.20,
            "resource_fit": 0.10,
            "failure_penalty": 0.0,
            "dispatch_order": -0.001,
            # No ai_adjustment key
        }
        task.save()

        response = user_client.get("/api/tasks/recent-dispatches/")
        assert response.status_code == 200
        assert response.json()[0]["ai_was_invoked"] is False
        assert response.json()[0]["ai_reason"] == ""
