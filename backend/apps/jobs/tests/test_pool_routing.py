"""
Unit and integration tests for worker pool routing.

Covers:
- Job.clean() M2M validation (model layer).
- JobCreateSerializer / JobPatchSerializer pool intersection validation.
- create_job_with_layers() service-layer validation.
- TaskDispatchView pool-based frame routing.
"""

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.jobs.models import TaskState, Job, JobState
from apps.jobs.services import create_job_with_layers
from apps.workers.models import WorkerNode, WorkerPool

from .factories import TaskFactory, JobFactory

pytestmark = pytest.mark.django_db


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def pool_a():
    return WorkerPool.objects.create(name="pool-a")


@pytest.fixture
def pool_b():
    return WorkerPool.objects.create(name="pool-b")


@pytest.fixture
def worker(pool_a):
    """A registered WorkerNode belonging to pool_a."""
    node = WorkerNode.objects.create(hostname="render-node-01")
    node.pools.set([pool_a])
    return node


@pytest.fixture
def farm_client(db):
    """API client authenticated as a farm agent."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    group, _ = Group.objects.get_or_create(name="farm_agents")
    agent = User.objects.create_user(username="farm_service_routing", password="!")
    agent.groups.add(group)
    client = APIClient()
    token = Token.objects.create(user=agent)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


# ── Model: Job.clean() validation ─────────────────────────────────────────────


class TestJobCleanValidation:
    def test_clean_raises_when_pools_overlap(self, pool_a):
        """Job.clean() raises ValidationError when included and excluded pools intersect."""
        job = JobFactory()
        job.included_pools.set([pool_a])
        job.excluded_pools.set([pool_a])

        with pytest.raises(ValidationError, match="A pool cannot be both included and excluded"):
            job.full_clean()

    def test_clean_does_not_query_m2m_before_save(self):
        """Job.clean() must not query M2M on an unsaved instance (would raise ValueError).

        UUIDField populates self.pk at Python instantiation time, so the old
        `if self.pk:` guard was always True. The fix uses `_state.adding`.
        """
        # Construct without saving — _state.adding is True at this point.
        job = Job(
            name="unsaved-job-001",
            project="test",
            department="fx",
            user="artist",
            log_directory="/tmp",
        )
        # clean() should complete without raising ValueError or hitting the DB.
        job.clean()

    def test_clean_passes_with_non_overlapping_pools(self, pool_a, pool_b):
        """Job.clean() does not raise when included and excluded pools are disjoint."""
        job = JobFactory()
        job.included_pools.set([pool_a])
        job.excluded_pools.set([pool_b])

        job.full_clean()  # should not raise


# ── Serializer: JobCreateSerializer validation ────────────────────────────────


class TestJobCreateSerializerPoolValidation:
    BASE_PAYLOAD = {
        "visible_name": "Test Job",
        "project": "proj_x",
        "department": "Lighting",
        "user": "artist",
        "log_directory": "/proj/logs/",
        "layers": [
            {
                "name": "beauty",
                "layer_type": "RENDER",
                "command": "render {frame}",
                "frame_range": "1-5",
            }
        ],
    }

    def test_create_with_overlapping_pools_returns_400(self, farm_client, pool_a):
        """Submitting a job with the same pool in both included and excluded returns 400."""
        payload = {
            **self.BASE_PAYLOAD,
            "included_pools": [str(pool_a.pk)],
            "excluded_pools": [str(pool_a.pk)],
        }
        resp = farm_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 400

    def test_create_with_non_overlapping_pools_succeeds(self, farm_client, pool_a, pool_b):
        """Submitting a job with disjoint included/excluded pools returns 201."""
        payload = {
            **self.BASE_PAYLOAD,
            "included_pools": [str(pool_a.pk)],
            "excluded_pools": [str(pool_b.pk)],
        }
        resp = farm_client.post("/api/jobs/", payload, format="json")
        assert resp.status_code == 201
        job = Job.objects.get()
        assert job.included_pools.filter(pk=pool_a.pk).exists()
        assert job.excluded_pools.filter(pk=pool_b.pk).exists()


# ── Serializer: JobPatchSerializer validation ─────────────────────────────────


class TestJobPatchSerializerPoolValidation:
    def test_patch_that_creates_overlap_returns_400(self, pool_a, pool_b, db):
        """PATCHing pools so they overlap with the existing set is rejected with 400."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="owner_patch", password="pass")
        job = JobFactory(submitted_by=user)
        job.included_pools.set([pool_a])

        client = APIClient()
        token = Token.objects.create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # Trying to add pool_a to excluded while it's already in included
        resp = client.patch(
            f"/api/jobs/{job.pk}/",
            {"excluded_pools": [str(pool_a.pk)]},
            format="json",
        )
        assert resp.status_code == 400


# ── Service: create_job_with_layers() validation ──────────────────────────────


class TestServicePoolValidation:
    def test_service_raises_for_overlapping_pools(self, pool_a):
        """create_job_with_layers() raises ValueError when pools overlap.

        This guards programmatic callers that bypass the DRF serializer layer,
        e.g. management commands, shell, or test helpers.
        """
        data = {
            "visible_name": "Direct Service Call",
            "project": "proj_x",
            "department": "fx",
            "user": "artist",
            "log_directory": "/tmp",
            "included_pools": [pool_a],
            "excluded_pools": [pool_a],
            "layers": [
                {
                    "name": "beauty",
                    "layer_type": "RENDER",
                    "command": "render {frame}",
                    "frame_range": "1-3",
                    "chunk_size": 1,
                    "max_retries": 3,
                }
            ],
        }
        with pytest.raises(ValueError, match="A pool cannot be both included and excluded"):
            create_job_with_layers(data)


# ── TaskDispatchView: pool routing ──────────────────────────────────────────


class TestTaskDispatchPoolRouting:
    DISPATCH_URL = "/api/tasks/dispatch/"

    def test_worker_in_included_pool_gets_frame(self, farm_client, worker, pool_a):
        """A worker belonging to a job's included_pools receives a READY frame."""
        job = JobFactory(is_paused=False, state=JobState.PENDING)
        job.included_pools.set([pool_a])
        TaskFactory(job=job, state=TaskState.READY)

        resp = farm_client.post(self.DISPATCH_URL, {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 200
        assert resp.data["job_id"] == str(job.pk)

    def test_worker_not_in_included_pool_skips_restricted_job(self, farm_client, pool_a, pool_b):
        """A worker NOT in included_pools cannot receive frames from that job."""
        # Worker belongs to pool_b only
        other_worker = WorkerNode.objects.create(hostname="render-node-02")
        other_worker.pools.set([pool_b])

        job = JobFactory(is_paused=False, state=JobState.PENDING)
        job.included_pools.set([pool_a])  # restricted to pool_a
        TaskFactory(job=job, state=TaskState.READY)

        resp = farm_client.post(self.DISPATCH_URL, {"worker_name": "render-node-02"}, format="json")
        assert resp.status_code == 404

    def test_worker_in_excluded_pool_does_not_get_frame(self, farm_client, worker, pool_a):
        """A worker in a job's excluded_pools is skipped even if a READY frame exists."""
        job = JobFactory(is_paused=False, state=JobState.PENDING)
        job.excluded_pools.set([pool_a])
        TaskFactory(job=job, state=TaskState.READY)

        resp = farm_client.post(self.DISPATCH_URL, {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 404

    def test_worker_gets_frame_from_unrestricted_job(self, farm_client, worker):
        """A worker picks up a frame from a job with no pool restrictions."""
        job = JobFactory(is_paused=False, state=JobState.PENDING)
        # No included_pools or excluded_pools set.
        TaskFactory(job=job, state=TaskState.READY)

        resp = farm_client.post(self.DISPATCH_URL, {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 200
        assert resp.data["job_id"] == str(job.pk)

    def test_paused_job_frames_are_not_dispatched(self, farm_client, worker, pool_a):
        """Tasks from a paused job are not dispatched regardless of pool membership."""
        job = JobFactory(is_paused=True, state=JobState.PAUSED)
        job.included_pools.set([pool_a])
        TaskFactory(job=job, state=TaskState.READY)

        resp = farm_client.post(self.DISPATCH_URL, {"worker_name": "render-node-01"}, format="json")
        assert resp.status_code == 404

    def test_unregistered_worker_only_gets_unrestricted_jobs(self, farm_client, pool_a):
        """A worker not in WorkerNode (no ping) can only dispatch unrestricted jobs.

        When worker_pools is [], Q(included_pools__in=[]) is always FALSE in SQL,
        so restricted jobs are automatically excluded. Unrestricted jobs pass the
        Q(included_pools__isnull=True) branch.
        """
        # Restricted job — unregistered worker cannot access
        restricted_job = JobFactory(is_paused=False, state=JobState.PENDING)
        restricted_job.included_pools.set([pool_a])
        TaskFactory(job=restricted_job, state=TaskState.READY)

        # Unrestricted job — unregistered worker CAN access
        open_job = JobFactory(is_paused=False, state=JobState.PENDING)
        TaskFactory(job=open_job, state=TaskState.READY)

        # "ghost-worker" has never pinged — not in WorkerNode
        resp = farm_client.post(self.DISPATCH_URL, {"worker_name": "ghost-worker"}, format="json")
        assert resp.status_code == 200
        assert resp.data["job_id"] == str(open_job.pk)
