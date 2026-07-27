"""
API tests for the jobs app.

Tests cover the full HTTP lifecycle: authentication, job submission (nested),
filtering, state transition actions, and permission boundaries.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.jobs.models import Task, TaskState, Job, JobState, Layer

from .factories import TaskFactory, JobFactory, LayerFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    """A standard authenticated human user (artist)."""
    return User.objects.create_user(username="artist", password="pass")


@pytest.fixture
def staff_user(db):
    """A staff user (supervisor)."""
    return User.objects.create_user(username="supervisor", password="pass", is_staff=True)


@pytest.fixture
def farm_agent_user(db):
    """A farm_service user in the farm_agents group (Worker / DCC plugin)."""
    group, _ = Group.objects.get_or_create(name="farm_agents")
    agent = User.objects.create_user(username="farm_service", password="!")
    agent.groups.add(group)
    return agent


@pytest.fixture
def user_client(user):
    """API client authenticated as a regular artist."""
    client = APIClient()
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def staff_client(staff_user):
    """API client authenticated as a staff supervisor."""
    client = APIClient()
    token = Token.objects.create(user=staff_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def farm_client(farm_agent_user):
    """API client authenticated as the farm_service agent."""
    client = APIClient()
    token = Token.objects.create(user=farm_agent_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()


# ── Job Submission (POST /api/jobs/) ──────────────────────────────────────────


class TestJobSubmission:
    JOB_PAYLOAD = {
        "visible_name": "Beauty Pass v3",
        "project": "proj_x_ep03",
        "department": "Lighting",
        "user": "artist",
        "priority": 75,
        "log_directory": "/proj/logs/",
        "layers": [
            {
                "name": "beauty",
                "layer_type": "RENDER",
                "command": "render -s {frame} -e {frame} scene.ma",
                "frame_range": "1-10",
                "chunk_size": 1,
                "min_cores": 4,
                "min_memory_mb": 8192,
            }
        ],
    }

    def test_authenticated_user_can_submit_job(self, user_client):
        """A regular authenticated user can submit a job."""
        resp = user_client.post("/api/jobs/", self.JOB_PAYLOAD, format="json")
        assert resp.status_code == 201
        assert Job.objects.count() == 1
        assert Layer.objects.count() == 1
        assert Task.objects.count() == 10  # frames 1-10

    def test_job_creation_populates_frame_counters(self, user_client):
        """Job and Layer frame counter caches are populated on submission."""
        user_client.post("/api/jobs/", self.JOB_PAYLOAD, format="json")
        job = Job.objects.get()
        assert job.total_tasks == 10
        assert job.ready_tasks == 10

        layer = Layer.objects.get()
        assert layer.total_tasks == 10
        assert layer.ready_tasks == 10

    def test_submitted_by_populated_for_web_submission(self, user_client, user):
        """submitted_by is set to the session user for web submissions."""
        user_client.post("/api/jobs/", self.JOB_PAYLOAD, format="json")
        job = Job.objects.get()
        assert job.submitted_by == user

    def test_farm_agent_can_submit_job(self, farm_client):
        """DCC plugin (farm agent) can submit a job."""
        resp = farm_client.post("/api/jobs/", self.JOB_PAYLOAD, format="json")
        assert resp.status_code == 201

    def test_unauthenticated_cannot_submit_job(self, anon_client):
        """Unauthenticated clients are rejected (401 or 403 depending on auth scheme)."""
        resp = anon_client.post("/api/jobs/", self.JOB_PAYLOAD, format="json")
        assert resp.status_code in (401, 403)

    def test_job_without_layers_is_rejected(self, user_client):
        """A job payload with an empty layers list is rejected with 400."""
        payload = {**self.JOB_PAYLOAD, "layers": []}
        resp = user_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 400

    def test_invalid_frame_range_is_rejected(self, user_client):
        """An unparseable frame range returns a 400."""
        payload = {
            **self.JOB_PAYLOAD,
            "layers": [
                {
                    **self.JOB_PAYLOAD["layers"][0],
                    "frame_range": "not-valid",
                }
            ],
        }
        resp = user_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 400

    def test_chunked_frame_range_creates_correct_frame_count(self, user_client):
        """A 1-10 range with chunk_size=5 creates 2 Task rows."""
        payload = {
            **self.JOB_PAYLOAD,
            "layers": [
                {
                    **self.JOB_PAYLOAD["layers"][0],
                    "frame_range": "1-10",
                    "chunk_size": 5,
                }
            ],
        }
        user_client.post("/api/jobs/", payload, format="json")
        assert Task.objects.count() == 2


# ── Job List & Detail (GET /api/jobs/) ────────────────────────────────────────


class TestJobListAndDetail:
    def test_list_returns_all_jobs(self, user_client):
        """GET /api/jobs/ returns all jobs."""
        JobFactory.create_batch(3)
        resp = user_client.get("/api/jobs/")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 3

    def test_filter_by_state(self, user_client):
        """?state= filter returns only matching jobs."""
        JobFactory(state=JobState.RUNNING)
        JobFactory(state=JobState.PENDING)
        resp = user_client.get("/api/jobs/?state=RUNNING")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["state"] == "RUNNING"

    def test_filter_by_project(self, user_client):
        """?project= filter returns only matching jobs."""
        JobFactory(project="proj_a")
        JobFactory(project="proj_b")
        resp = user_client.get("/api/jobs/?project=proj_a")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1

    def test_search_parameter(self, user_client):
        """?search= filters jobs across multiple text fields."""
        JobFactory(visible_name="Unique Beauty Render")
        JobFactory(project="unique_proj_x")
        JobFactory(department="Compositing")

        # Search by visible_name
        resp = user_client.get("/api/jobs/?search=Beauty")
        assert len(resp.data["results"]) == 1

        # Search by project
        resp = user_client.get("/api/jobs/?search=unique_proj")
        assert len(resp.data["results"]) == 1

    def test_retrieve_includes_nested_layers(self, user_client):
        """GET /api/jobs/{id}/ includes nested layers array."""
        layer = LayerFactory()
        resp = user_client.get(f"/api/jobs/{layer.job.pk}/")
        assert resp.status_code == 200
        assert len(resp.data["layers"]) == 1

    def test_unauthenticated_cannot_list(self, anon_client):
        """Unauthenticated requests to list endpoint are rejected (401 or 403)."""
        resp = anon_client.get("/api/jobs/")
        assert resp.status_code in (401, 403)


# ── Job Patch & Permissions ───────────────────────────────────────────────────


class TestJobMutations:
    def test_owner_can_patch_priority(self, user_client, user):
        """Job submitter can update priority."""
        job = JobFactory(submitted_by=user)
        resp = user_client.patch(f"/api/jobs/{job.pk}/", {"priority": 90}, format="json")
        assert resp.status_code == 200
        job.refresh_from_db()
        assert job.priority == 90

    def test_non_owner_cannot_patch(self, user_client):
        """A different user cannot patch another user's job."""
        job = JobFactory()  # no submitted_by set
        resp = user_client.patch(f"/api/jobs/{job.pk}/", {"priority": 99}, format="json")
        assert resp.status_code == 403

    def test_staff_can_patch_any_job(self, staff_client):
        """Staff users can patch any job."""
        job = JobFactory()
        resp = staff_client.patch(f"/api/jobs/{job.pk}/", {"priority": 10}, format="json")
        assert resp.status_code == 200

    def test_state_is_not_patchable(self, user_client, user):
        """State cannot be changed via PATCH (not in JobPatchSerializer)."""
        job = JobFactory(submitted_by=user, state=JobState.PENDING)
        resp = user_client.patch(f"/api/jobs/{job.pk}/", {"state": "RUNNING"}, format="json")
        # Request succeeds but state is unchanged
        assert resp.status_code == 200
        job.refresh_from_db()
        assert job.state == JobState.PENDING


# ── Job Pause / Resume ────────────────────────────────────────────────────────


class TestJobPauseResume:
    def test_owner_can_pause_and_resume(self, user_client, user):
        """Job submitter can pause and resume their job."""
        job = JobFactory(submitted_by=user)
        resp = user_client.post(f"/api/jobs/{job.pk}/pause/")
        assert resp.status_code == 200
        job.refresh_from_db()
        assert job.is_paused is True

        resp = user_client.post(f"/api/jobs/{job.pk}/resume/")
        assert resp.status_code == 200
        job.refresh_from_db()
        assert job.is_paused is False


# ── Task State Transitions ───────────────────────────────────────────────────


class TestTaskActions:
    def test_farm_agent_can_start_ready_task(self, farm_client):
        """Farm agent can mark a READY frame as RUNNING."""
        task = TaskFactory(state=TaskState.READY)
        resp = farm_client.post(f"/api/tasks/{task.pk}/start/", {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.RUNNING
        assert task.worker_name == "render-node-01"

    def test_start_non_ready_task_returns_409(self, farm_client):
        """Starting a frame that is not READY returns 409 Conflict."""
        task = TaskFactory(state=TaskState.WAITING)
        resp = farm_client.post(f"/api/tasks/{task.pk}/start/", {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 409

    def test_farm_agent_can_succeed_running_task(self, farm_client):
        """Farm agent can mark a RUNNING frame as SUCCEEDED with telemetry."""
        task = TaskFactory(state=TaskState.RUNNING)
        resp = farm_client.post(
            f"/api/tasks/{task.pk}/succeed/",
            {"exit_status": 0, "max_memory_used_mb": 4096, "cores_used": 4},
            format="json",
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.SUCCEEDED
        assert task.max_memory_used_mb == 4096

    def test_succeed_updates_parent_counters(self, farm_client):
        """Succeeding a frame updates parent Layer and Job counters."""
        task = TaskFactory(state=TaskState.RUNNING)
        Layer.objects.filter(pk=task.layer.pk).update(running_tasks=1, total_tasks=1)
        Job.objects.filter(pk=task.job.pk).update(running_tasks=1, total_tasks=1)

        farm_client.post(f"/api/tasks/{task.pk}/succeed/", {"exit_status": 0, "max_memory_used_mb": 0}, format="json")
        task.layer.refresh_from_db()
        task.job.refresh_from_db()
        assert task.layer.running_tasks == 0
        assert task.layer.succeeded_tasks == 1
        assert task.job.running_tasks == 0
        assert task.job.succeeded_tasks == 1

    def test_farm_agent_can_fail_frame_within_retry_budget(self, farm_client):
        """Failing a frame within retry budget sets it back to READY."""
        task = TaskFactory(state=TaskState.RUNNING, retries=0, max_retries=3)
        resp = farm_client.post(f"/api/tasks/{task.pk}/fail/", {"exit_status": 1}, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.READY

    def test_frame_exceeding_retry_budget_becomes_failed(self, farm_client):
        """Failing a frame that has exhausted retries transitions to FAILED."""
        task = TaskFactory(state=TaskState.RUNNING, retries=2, max_retries=3)
        resp = farm_client.post(f"/api/tasks/{task.pk}/fail/", {"exit_status": 1}, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.FAILED

    def test_staff_can_skip_failed_frame(self, staff_client):
        """Staff user can skip a FAILED frame."""
        task = TaskFactory(state=TaskState.FAILED)
        resp = staff_client.post(f"/api/tasks/{task.pk}/skip/")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.SKIPPED

    def test_non_staff_cannot_skip_frame(self, user_client):
        """Regular users cannot skip frames."""
        task = TaskFactory(state=TaskState.FAILED)
        resp = user_client.post(f"/api/tasks/{task.pk}/skip/")
        assert resp.status_code == 403

    def test_regular_user_cannot_call_start(self, user_client):
        """Regular user cannot call the Worker-only start action."""
        task = TaskFactory(state=TaskState.READY)
        resp = user_client.post(f"/api/tasks/{task.pk}/start/", {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 403

    def test_farm_agent_can_checkpoint_running_task(self, farm_client):
        """Farm agent can increment the checkpoint counter on a RUNNING frame."""
        task = TaskFactory(state=TaskState.RUNNING)
        resp = farm_client.post(f"/api/tasks/{task.pk}/checkpoint/")
        assert resp.status_code == 200
        assert resp.data["checkpoint_count"] == 1
        task.refresh_from_db()
        assert task.state == TaskState.CHECKPOINT

    def test_farm_agent_can_checkpoint_from_checkpoint_state(self, farm_client):
        """Farm agent can re-checkpoint a frame already in CHECKPOINT state.

        Long renders (e.g. V-Ray) save intermediate resume files multiple times
        during a single frame execution. Each call must succeed, not 409.
        """
        task = TaskFactory(state=TaskState.CHECKPOINT, checkpoint_count=1)
        resp = farm_client.post(f"/api/tasks/{task.pk}/checkpoint/")
        assert resp.status_code == 200
        assert resp.data["checkpoint_count"] == 2
        task.refresh_from_db()
        assert task.state == TaskState.CHECKPOINT

    def test_farm_agent_can_succeed_from_checkpoint_state(self, farm_client):
        """Farm agent can mark a CHECKPOINT frame as SUCCEEDED."""
        task = TaskFactory(state=TaskState.CHECKPOINT)
        resp = farm_client.post(
            f"/api/tasks/{task.pk}/succeed/",
            {"exit_status": 0, "max_memory_used_mb": 2048},
            format="json",
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.SUCCEEDED
        assert task.stopped_at is not None

    def test_farm_agent_can_fail_from_checkpoint_state(self, farm_client):
        """Farm agent can report failure on a CHECKPOINT frame (retry path)."""
        task = TaskFactory(state=TaskState.CHECKPOINT, retries=0, max_retries=3)
        resp = farm_client.post(f"/api/tasks/{task.pk}/fail/", {"exit_status": 1}, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == TaskState.READY

    def test_skip_non_failed_frame_returns_409(self, staff_client):
        """Trying to skip a frame that is not FAILED returns 409 Conflict."""
        task = TaskFactory(state=TaskState.RUNNING)
        resp = staff_client.post(f"/api/tasks/{task.pk}/skip/")
        assert resp.status_code == 409

    def test_unauthenticated_cannot_call_start(self, anon_client):
        """Unauthenticated requests to worker-only actions are rejected."""
        task = TaskFactory(state=TaskState.READY)
        resp = anon_client.post(f"/api/tasks/{task.pk}/start/", {"worker_name": "node-01"}, format="json")
        assert resp.status_code in (401, 403)

    def test_fail_within_retry_budget_does_not_set_stopped_at(self, farm_client):
        """A frame that will be retried (back to READY) must not have stopped_at set.

        stopped_at represents permanent termination. A retried frame is still in
        flight and should not carry a misleading end timestamp.
        """
        task = TaskFactory(state=TaskState.RUNNING, retries=0, max_retries=3)
        farm_client.post(f"/api/tasks/{task.pk}/fail/", {"exit_status": 1}, format="json")
        task.refresh_from_db()
        assert task.state == TaskState.READY
        assert task.stopped_at is None


# ── Multi-layer Counter Accumulation ─────────────────────────────────────────


class TestJobSubmissionMultiLayer:
    """Verify that job-level frame counters accumulate correctly across layers.

    This exercises the F()-expression fix in services.py. A non-atomic
    read-then-write would silently drop the second layer's count under
    concurrent submissions.
    """

    def test_multi_layer_job_counter_accumulation(self, user_client):
        """Job total_tasks sums frame counts across all layers."""
        payload = {
            "visible_name": "Multi-layer Job",
            "project": "proj_x",
            "department": "Lighting",
            "user": "artist",
            "log_directory": "/proj/logs/",
            "layers": [
                {
                    "name": "beauty",
                    "layer_type": "RENDER",
                    "command": "render scene.ma",
                    "frame_range": "1-5",
                },
                {
                    "name": "shadow",
                    "layer_type": "RENDER",
                    "command": "render scene.ma",
                    "frame_range": "1-3",
                },
            ],
        }
        resp = user_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 201
        job = Job.objects.get()
        assert job.total_tasks == 8  # 5 (beauty) + 3 (shadow)
        assert job.ready_tasks == 8
        assert Task.objects.count() == 8
