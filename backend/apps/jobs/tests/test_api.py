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

from apps.jobs.models import Job, JobState, Layer, Task, TaskState

from .factories import JobFactory, LayerFactory, TaskFactory

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


# ── Dependency API Tests ───────────────────────────────────────────────────────


class TestDependencyAPI:
    """Tests for the /api/dependencies/ endpoints."""

    def _two_job_setup(self):
        """Return two distinct jobs for dependency tests."""
        from .factories import JobFactory
        parent = JobFactory()
        blocked = JobFactory()
        return parent, blocked

    def test_authenticated_user_can_list_dependencies(self, user_client):
        resp = user_client.get("/api/dependencies/")
        assert resp.status_code == 200

    def test_anon_cannot_list_dependencies(self, anon_client):
        resp = anon_client.get("/api/dependencies/")
        assert resp.status_code == 403

    def test_create_job_on_job_dependency(self, user_client):
        from .factories import JobFactory
        parent = JobFactory()
        blocked = JobFactory()
        payload = {
            "type": "JOB_ON_JOB",
            "dep_job": str(blocked.id),
            "parent_job": str(parent.id),
        }
        resp = user_client.post("/api/dependencies/", payload, format="json")
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "JOB_ON_JOB"
        assert data["is_satisfied"] is False

    def test_create_task_on_task_dependency(self, user_client):
        from .factories import TaskFactory
        parent_task = TaskFactory(state="READY")
        dep_task = TaskFactory(state="WAITING")
        payload = {
            "type": "TASK_ON_TASK",
            "dep_job": str(dep_task.job.id),
            "dep_layer": str(dep_task.layer.id),
            "dep_task": str(dep_task.id),
            "parent_job": str(parent_task.job.id),
            "parent_layer": str(parent_task.layer.id),
            "parent_task": str(parent_task.id),
        }
        resp = user_client.post("/api/dependencies/", payload, format="json")
        assert resp.status_code == 201
        dep_task.refresh_from_db()
        assert dep_task.depend_count == 1

    def test_self_dependency_rejected(self, user_client):
        from .factories import TaskFactory
        task = TaskFactory()
        payload = {
            "type": "TASK_ON_TASK",
            "dep_job": str(task.job.id),
            "dep_layer": str(task.layer.id),
            "dep_task": str(task.id),
            "parent_job": str(task.job.id),
            "parent_layer": str(task.layer.id),
            "parent_task": str(task.id),
        }
        resp = user_client.post("/api/dependencies/", payload, format="json")
        assert resp.status_code == 400

    def test_cycle_detection_rejects_circular_dependency(self, user_client):
        """A→B then B→A should be rejected as a cycle."""
        from .factories import TaskFactory
        task_a = TaskFactory(state="READY")
        task_b = TaskFactory(state="WAITING")
        # A → B (B waits on A)
        payload_ab = {
            "type": "TASK_ON_TASK",
            "dep_job": str(task_b.job.id),
            "dep_layer": str(task_b.layer.id),
            "dep_task": str(task_b.id),
            "parent_job": str(task_a.job.id),
            "parent_layer": str(task_a.layer.id),
            "parent_task": str(task_a.id),
        }
        resp = user_client.post("/api/dependencies/", payload_ab, format="json")
        assert resp.status_code == 201

        # B → A (A waits on B) — would close a cycle
        payload_ba = {
            "type": "TASK_ON_TASK",
            "dep_job": str(task_a.job.id),
            "dep_layer": str(task_a.layer.id),
            "dep_task": str(task_a.id),
            "parent_job": str(task_b.job.id),
            "parent_layer": str(task_b.layer.id),
            "parent_task": str(task_b.id),
        }
        resp = user_client.post("/api/dependencies/", payload_ba, format="json")
        assert resp.status_code == 400
        assert "cycle" in resp.json()["non_field_errors"][0].lower()

    def test_only_staff_can_delete_dependency(self, user_client, staff_client):
        from .factories import DependencyFactory
        dep = DependencyFactory()
        dep_url = f"/api/dependencies/{dep.id}/"
        # Regular user: forbidden
        resp = user_client.delete(dep_url)
        assert resp.status_code == 403
        # Staff user: allowed
        resp = staff_client.delete(dep_url)
        assert resp.status_code == 204

    def test_delete_repairs_depend_count(self, staff_client):
        from .factories import DependencyFactory
        dep = DependencyFactory()
        task = dep.dep_task
        task.refresh_from_db()
        assert task.depend_count == 1
        staff_client.delete(f"/api/dependencies/{dep.id}/")
        task.refresh_from_db()
        assert task.depend_count == 0
        assert task.state == "READY"

    def test_job_scoped_dependency_list(self, user_client):
        from .factories import DependencyFactory
        dep = DependencyFactory()
        job_id = dep.dep_job.id
        resp = user_client.get(f"/api/jobs/{job_id}/dependencies/")
        assert resp.status_code == 200
        results = resp.json()["results"] if "results" in resp.json() else resp.json()
        assert any(str(d["id"]) == str(dep.id) for d in results)


# ── Job Submission With Dependencies ──────────────────────────────────────────


class TestJobSubmissionWithDependencies:
    """Tests for layer-level deps declared at job submission time."""

    BASE_PAYLOAD = {
        "visible_name": "Multi-layer Dep Job",
        "project": "test_project",
        "department": "lighting",
        "user": "artist",
        "priority": 50,
        "log_directory": "/mnt/logs/",
        "layers": [
            {
                "name": "beauty",
                "layer_type": "RENDER",
                "command": "render scene.ma",
                "frame_range": "1-3",
            },
            {
                "name": "composite",
                "layer_type": "POST",
                "command": "comp.nk",
                "frame_range": "1-3",
            },
        ],
    }

    def test_submit_job_with_layer_dependency(self, user_client):
        payload = {
            **self.BASE_PAYLOAD,
            "layers": [
                {
                    "name": "beauty",
                    "layer_type": "RENDER",
                    "command": "render scene.ma",
                    "frame_range": "1-3",
                },
                {
                    "name": "composite",
                    "layer_type": "POST",
                    "command": "comp.nk",
                    "frame_range": "1-3",
                    "execution_mode": "WAIT_LAYER",
                    "depends_on_layer": "beauty",
                    "dependency_type": "LAYER_ON_LAYER"
                },
            ]
        }
        resp = user_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 201, resp.json()

        from apps.jobs.models import Dependency, DependencyType, Layer, Task, TaskState
        dep = Dependency.objects.get(type=DependencyType.LAYER_ON_LAYER)
        assert not dep.is_satisfied

        # composite tasks should be WAITING
        composite_layer = Layer.objects.get(name="composite")
        assert Task.objects.filter(layer=composite_layer, state=TaskState.WAITING).count() == 3
        # beauty tasks should be READY
        beauty_layer = Layer.objects.get(name="beauty")
        assert Task.objects.filter(layer=beauty_layer, state=TaskState.READY).count() == 3

    def test_depend_tasks_counter_set_correctly(self, user_client):
        payload = {
            **self.BASE_PAYLOAD,
            "layers": [
                {
                    "name": "beauty",
                    "layer_type": "RENDER",
                    "command": "render scene.ma",
                    "frame_range": "1-3",
                },
                {
                    "name": "composite",
                    "layer_type": "POST",
                    "command": "comp.nk",
                    "frame_range": "1-3",
                    "execution_mode": "WAIT_LAYER",
                    "depends_on_layer": "beauty",
                },
            ]
        }
        resp = user_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 201

        from apps.jobs.models import Job
        job = Job.objects.get()
        assert job.depend_tasks == 3  # 3 composite frames blocked
        assert job.waiting_tasks == 3
        assert job.ready_tasks == 3

    def test_unknown_layer_name_rejected(self, user_client):
        payload = {
            **self.BASE_PAYLOAD,
            "layers": [
                {
                    "name": "beauty",
                    "layer_type": "RENDER",
                    "command": "render scene.ma",
                    "frame_range": "1-3",
                },
                {
                    "name": "composite",
                    "layer_type": "POST",
                    "command": "comp.nk",
                    "frame_range": "1-3",
                    "execution_mode": "WAIT_LAYER",
                    "depends_on_layer": "nonexistent",
                },
            ]
        }
        resp = user_client.post("/api/jobs/", payload, format="json")
        # Transaction is rolled back — no partial data
        assert resp.status_code in (400, 500)

    def test_self_layer_dependency_rejected_at_submission(self, user_client):
        payload = {
            **self.BASE_PAYLOAD,
            "dependencies": [
                {"dep_layer_name": "beauty", "parent_layer_name": "beauty"}
            ],
        }
        resp = user_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 400

    def test_submit_without_dependencies_still_works(self, user_client):
        """Existing tests should not regress — no dependencies key is fine."""
        resp = user_client.post("/api/jobs/", self.BASE_PAYLOAD, format="json")
        assert resp.status_code == 201

        from apps.jobs.models import Task, TaskState
        assert Task.objects.filter(state=TaskState.READY).count() == 6


# ── Signal Tests: LAYER_ON_LAYER and JOB_ON_JOB ──────────────────────────────


class TestLayerAndJobDependencySignals:
    """Tests that LAYER_ON_LAYER and JOB_ON_JOB signals fire correctly."""

    def test_layer_on_layer_satisfied_when_parent_finishes(self):
        from apps.jobs.models import Dependency, DependencyType, JobState, Layer, TaskState

        from .factories import JobFactory, LayerFactory, TaskFactory

        job = JobFactory()
        parent_layer = LayerFactory(job=job)
        dep_layer = LayerFactory(job=job)

        parent_task = TaskFactory(layer=parent_layer, job=job, state=TaskState.RUNNING)
        dep_task = TaskFactory(layer=dep_layer, job=job, state=TaskState.WAITING)

        dep = Dependency.objects.create(
            type=DependencyType.LAYER_ON_LAYER,
            dep_job=job,
            dep_layer=dep_layer,
            parent_job=job,
            parent_layer=parent_layer,
        )
        dep_task.depend_count = 1
        dep_task.save(update_fields=["depend_count", "updated_at"])

        # Mark parent layer FINISHED by succeeding its task and manually pushing layer state
        parent_task.state = TaskState.SUCCEEDED
        parent_task.save()

        # Now push parent layer to FINISHED (triggers layer_pre_save signal)
        Layer.objects.filter(pk=parent_layer.pk).update(
            total_tasks=1,
            succeeded_tasks=1,
        )
        parent_layer.refresh_from_db()
        parent_layer.state = JobState.FINISHED
        parent_layer.save(update_fields=["state"])

        dep.refresh_from_db()
        assert dep.is_satisfied is True
        dep_task.refresh_from_db()
        assert dep_task.depend_count == 0
        assert dep_task.state == TaskState.READY

    def test_job_on_job_satisfied_when_parent_finishes(self):
        from apps.jobs.models import Dependency, DependencyType, JobState, TaskState

        from .factories import JobFactory, TaskFactory

        parent_job = JobFactory()
        dep_job = JobFactory()
        dep_task = TaskFactory(job=dep_job, state=TaskState.WAITING)

        dep = Dependency.objects.create(
            type=DependencyType.JOB_ON_JOB,
            dep_job=dep_job,
            parent_job=parent_job,
        )
        dep_task.depend_count = 1
        dep_task.save(update_fields=["depend_count", "updated_at"])

        # Transition parent job to FINISHED — triggers job_pre_save signal
        parent_job.state = JobState.FINISHED
        parent_job.save(update_fields=["state"])

        dep.refresh_from_db()
        assert dep.is_satisfied is True
        dep_task.refresh_from_db()
        assert dep_task.depend_count == 0
        assert dep_task.state == TaskState.READY

    def test_depend_tasks_counter_increments_on_creation(self):
        from apps.jobs.models import Dependency, DependencyType, TaskState

        from .factories import JobFactory, LayerFactory, TaskFactory

        job = JobFactory()
        layer = LayerFactory(job=job)
        task = TaskFactory(layer=layer, job=job, state=TaskState.WAITING)

        job.refresh_from_db()
        layer.refresh_from_db()
        assert job.depend_tasks == 0

        dep = Dependency.objects.create(
            type=DependencyType.TASK_ON_TASK,
            dep_job=job,
            dep_layer=layer,
            dep_task=task,
            parent_job=job,
            parent_layer=layer,
            parent_task=TaskFactory(job=job, layer=layer, state=TaskState.READY),
        )

        job.refresh_from_db()
        layer.refresh_from_db()
        assert job.depend_tasks == 1
        assert layer.depend_tasks == 1
