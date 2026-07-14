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

from apps.jobs.models import Frame, FrameState, Job, JobState, Layer

from .factories import FrameFactory, JobFactory, LayerFactory

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
        assert Frame.objects.count() == 10  # frames 1-10

    def test_job_creation_populates_frame_counters(self, user_client):
        """Job and Layer frame counter caches are populated on submission."""
        user_client.post("/api/jobs/", self.JOB_PAYLOAD, format="json")
        job = Job.objects.get()
        assert job.total_frames == 10
        assert job.waiting_frames == 10

        layer = Layer.objects.get()
        assert layer.total_frames == 10
        assert layer.waiting_frames == 10

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
        """A 1-10 range with chunk_size=5 creates 2 Frame rows."""
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
        assert Frame.objects.count() == 2


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


# ── Frame State Transitions ───────────────────────────────────────────────────


class TestFrameActions:
    def test_farm_agent_can_start_ready_frame(self, farm_client):
        """Farm agent can mark a READY frame as RUNNING."""
        frame = FrameFactory(state=FrameState.READY)
        resp = farm_client.post(f"/api/frames/{frame.pk}/start/", {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.RUNNING
        assert frame.worker_name == "render-node-01"

    def test_start_non_ready_frame_returns_409(self, farm_client):
        """Starting a frame that is not READY returns 409 Conflict."""
        frame = FrameFactory(state=FrameState.WAITING)
        resp = farm_client.post(f"/api/frames/{frame.pk}/start/", {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 409

    def test_farm_agent_can_succeed_running_frame(self, farm_client):
        """Farm agent can mark a RUNNING frame as SUCCEEDED with telemetry."""
        frame = FrameFactory(state=FrameState.RUNNING)
        resp = farm_client.post(
            f"/api/frames/{frame.pk}/succeed/",
            {"exit_status": 0, "max_memory_used_mb": 4096, "cores_used": 4},
            format="json",
        )
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.SUCCEEDED
        assert frame.max_memory_used_mb == 4096

    def test_succeed_updates_parent_counters(self, farm_client):
        """Succeeding a frame updates parent Layer and Job counters."""
        frame = FrameFactory(state=FrameState.RUNNING)
        Layer.objects.filter(pk=frame.layer.pk).update(running_frames=1, total_frames=1)
        Job.objects.filter(pk=frame.job.pk).update(running_frames=1, total_frames=1)

        farm_client.post(f"/api/frames/{frame.pk}/succeed/", {"exit_status": 0, "max_memory_used_mb": 0}, format="json")
        frame.layer.refresh_from_db()
        frame.job.refresh_from_db()
        assert frame.layer.running_frames == 0
        assert frame.layer.succeeded_frames == 1
        assert frame.job.running_frames == 0
        assert frame.job.succeeded_frames == 1

    def test_farm_agent_can_fail_frame_within_retry_budget(self, farm_client):
        """Failing a frame within retry budget sets it back to READY."""
        frame = FrameFactory(state=FrameState.RUNNING, retries=0, max_retries=3)
        resp = farm_client.post(f"/api/frames/{frame.pk}/fail/", {"exit_status": 1}, format="json")
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.READY

    def test_frame_exceeding_retry_budget_becomes_failed(self, farm_client):
        """Failing a frame that has exhausted retries transitions to FAILED."""
        frame = FrameFactory(state=FrameState.RUNNING, retries=2, max_retries=3)
        resp = farm_client.post(f"/api/frames/{frame.pk}/fail/", {"exit_status": 1}, format="json")
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.FAILED

    def test_staff_can_skip_failed_frame(self, staff_client):
        """Staff user can skip a FAILED frame."""
        frame = FrameFactory(state=FrameState.FAILED)
        resp = staff_client.post(f"/api/frames/{frame.pk}/skip/")
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.SKIPPED

    def test_non_staff_cannot_skip_frame(self, user_client):
        """Regular users cannot skip frames."""
        frame = FrameFactory(state=FrameState.FAILED)
        resp = user_client.post(f"/api/frames/{frame.pk}/skip/")
        assert resp.status_code == 403

    def test_regular_user_cannot_call_start(self, user_client):
        """Regular user cannot call the Worker-only start action."""
        frame = FrameFactory(state=FrameState.READY)
        resp = user_client.post(f"/api/frames/{frame.pk}/start/", {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 403

    def test_farm_agent_can_checkpoint_running_frame(self, farm_client):
        """Farm agent can increment the checkpoint counter on a RUNNING frame."""
        frame = FrameFactory(state=FrameState.RUNNING)
        resp = farm_client.post(f"/api/frames/{frame.pk}/checkpoint/")
        assert resp.status_code == 200
        assert resp.data["checkpoint_count"] == 1
        frame.refresh_from_db()
        assert frame.state == FrameState.CHECKPOINT

    def test_farm_agent_can_checkpoint_from_checkpoint_state(self, farm_client):
        """Farm agent can re-checkpoint a frame already in CHECKPOINT state.

        Long renders (e.g. V-Ray) save intermediate resume files multiple times
        during a single frame execution. Each call must succeed, not 409.
        """
        frame = FrameFactory(state=FrameState.CHECKPOINT, checkpoint_count=1)
        resp = farm_client.post(f"/api/frames/{frame.pk}/checkpoint/")
        assert resp.status_code == 200
        assert resp.data["checkpoint_count"] == 2
        frame.refresh_from_db()
        assert frame.state == FrameState.CHECKPOINT

    def test_farm_agent_can_succeed_from_checkpoint_state(self, farm_client):
        """Farm agent can mark a CHECKPOINT frame as SUCCEEDED."""
        frame = FrameFactory(state=FrameState.CHECKPOINT)
        resp = farm_client.post(
            f"/api/frames/{frame.pk}/succeed/",
            {"exit_status": 0, "max_memory_used_mb": 2048},
            format="json",
        )
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.SUCCEEDED
        assert frame.stopped_at is not None

    def test_farm_agent_can_fail_from_checkpoint_state(self, farm_client):
        """Farm agent can report failure on a CHECKPOINT frame (retry path)."""
        frame = FrameFactory(state=FrameState.CHECKPOINT, retries=0, max_retries=3)
        resp = farm_client.post(f"/api/frames/{frame.pk}/fail/", {"exit_status": 1}, format="json")
        assert resp.status_code == 200
        frame.refresh_from_db()
        assert frame.state == FrameState.READY

    def test_skip_non_failed_frame_returns_409(self, staff_client):
        """Trying to skip a frame that is not FAILED returns 409 Conflict."""
        frame = FrameFactory(state=FrameState.RUNNING)
        resp = staff_client.post(f"/api/frames/{frame.pk}/skip/")
        assert resp.status_code == 409

    def test_unauthenticated_cannot_call_start(self, anon_client):
        """Unauthenticated requests to worker-only actions are rejected."""
        frame = FrameFactory(state=FrameState.READY)
        resp = anon_client.post(f"/api/frames/{frame.pk}/start/", {"worker_name": "node-01"}, format="json")
        assert resp.status_code in (401, 403)

    def test_fail_within_retry_budget_does_not_set_stopped_at(self, farm_client):
        """A frame that will be retried (back to READY) must not have stopped_at set.

        stopped_at represents permanent termination. A retried frame is still in
        flight and should not carry a misleading end timestamp.
        """
        frame = FrameFactory(state=FrameState.RUNNING, retries=0, max_retries=3)
        farm_client.post(f"/api/frames/{frame.pk}/fail/", {"exit_status": 1}, format="json")
        frame.refresh_from_db()
        assert frame.state == FrameState.READY
        assert frame.stopped_at is None


# ── Multi-layer Counter Accumulation ─────────────────────────────────────────


class TestJobSubmissionMultiLayer:
    """Verify that job-level frame counters accumulate correctly across layers.

    This exercises the F()-expression fix in services.py. A non-atomic
    read-then-write would silently drop the second layer's count under
    concurrent submissions.
    """

    def test_multi_layer_job_counter_accumulation(self, user_client):
        """Job total_frames sums frame counts across all layers."""
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
        assert job.total_frames == 8   # 5 (beauty) + 3 (shadow)
        assert job.waiting_frames == 8
        assert Frame.objects.count() == 8


