import pytest
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from apps.jobs.models import Job, Layer, Task
from apps.telemetry.models import EventSeverity, TaskExecutionLog, WorkerMetricSnapshot
from apps.telemetry.services import (
    MAX_LOG_SIZE_BYTES,
    record_dispatch_trace,
    record_event,
    record_task_log,
    record_worker_metrics,
    truncate_log_output,
)
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_user(db):
    user = User.objects.create_user(username="testartist", password="password123")
    return user


@pytest.fixture
def farm_agent_user(db):
    from django.contrib.auth.models import Group

    farm_group, _ = Group.objects.get_or_create(name="farm_agents")
    user = User.objects.create_user(username="farmworker", password="password123")
    user.groups.add(farm_group)
    return user


@pytest.fixture
def auth_client(auth_user):
    client = APIClient()
    client.force_authenticate(user=auth_user)
    return client


@pytest.fixture
def farm_client(farm_agent_user):
    client = APIClient()
    client.force_authenticate(user=farm_agent_user)
    return client


@pytest.fixture
def sample_job(db, auth_user):
    job = Job.objects.create(
        name="test_proj_test_job_001",
        visible_name="Test Job",
        project="test_proj",
        department="Lighting",
        user=auth_user.username,
        submitted_by=auth_user,
        priority=50,
        log_directory="/renders/logs",
    )
    layer = Layer.objects.create(
        job=job,
        name="beauty",
        command="Render -r arnold",
        frame_range="1-10",
    )
    task = Task.objects.create(
        layer=layer,
        job=job,
        name="beauty_0001",
        frame_start=1,
        frame_end=1,
        state="READY",
    )
    return job, layer, task


@pytest.mark.django_db
class TestTaskExecutionLogs:
    def test_record_task_log_and_cascade_delete(self, sample_job):
        job, layer, task = sample_job
        log = record_task_log(
            task=task,
            worker_hostname="node-01",
            exit_status=0,
            log_output="Render completed successfully.\nFrame 1 done.",
            duration_seconds=12.5,
            peak_memory_mb=2048,
            output_image_path="/renders/beauty.0001.exr",
        )

        assert log is not None
        assert log.attempt_number == 1
        assert log.worker_hostname == "node-01"
        assert log.exit_status == 0
        assert log.output_image_path == "/renders/beauty.0001.exr"
        assert TaskExecutionLog.objects.filter(task=task).count() == 1

        # Test CASCADE delete when Job is destroyed
        job.delete()
        assert TaskExecutionLog.objects.filter(pk=log.pk).count() == 0

    def test_log_truncation_safeguard(self):
        huge_text = "A" * (MAX_LOG_SIZE_BYTES + 500_000)
        truncated = truncate_log_output(huge_text, max_bytes=MAX_LOG_SIZE_BYTES)

        assert len(truncated) < len(huge_text)
        assert "[RENDERHIVE LOG TRUNCATED: Output exceeded 2MB maximum limit]" in truncated

    def test_task_log_api_endpoints(self, farm_client, auth_client, sample_job):
        job, layer, task = sample_job

        # POST /api/telemetry/tasks/{id}/logs/ via farm client
        post_response = farm_client.post(
            f"/api/telemetry/tasks/{task.id}/logs/",
            {
                "exit_status": 1,
                "log_output": "Error: Texture missing: /tex/wood.tx\nFatal error in render.",
                "error_tail": "Fatal error in render.",
                "duration_seconds": 5.2,
                "peak_memory_mb": 1500,
                "worker_hostname": "node-02",
            },
            format="json",
        )
        assert post_response.status_code == status.HTTP_201_CREATED
        log_id = post_response.data["id"]

        # GET /api/telemetry/tasks/{id}/logs/ (slim list)
        list_response = auth_client.get(f"/api/telemetry/tasks/{task.id}/logs/")
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.data["results"]) == 1
        # List serializer omits heavy log_output
        assert "log_output" not in list_response.data["results"][0]

        # GET /api/telemetry/tasks/{id}/logs/latest/ (full detail)
        latest_response = auth_client.get(f"/api/telemetry/tasks/{task.id}/logs/latest/")
        assert latest_response.status_code == status.HTTP_200_OK
        assert latest_response.data["log_output"] == "Error: Texture missing: /tex/wood.tx\nFatal error in render."
        assert latest_response.data["error_tail"] == "Fatal error in render."

        # GET /api/telemetry/logs/{pk}/ (detail view)
        detail_response = auth_client.get(f"/api/telemetry/logs/{log_id}/")
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["id"] == log_id


@pytest.mark.django_db
class TestDispatchTraces:
    def test_record_and_list_dispatch_traces(self, auth_client, sample_job):
        job, layer, task = sample_job
        trace = record_dispatch_trace(
            task=task,
            job=job,
            worker_hostname="node-03",
            candidate_count=5,
            ai_invoked=True,
            ai_latency_ms=120.5,
            ai_reason="Node-03 has pre-cached textures.",
            score_breakdown={"priority": 50, "ai_adjustment": 10},
        )
        assert trace is not None
        assert trace.ai_invoked is True

        response = auth_client.get("/api/telemetry/dispatches/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1
        item = response.data["results"][0]
        assert item["worker_hostname"] == "node-03"
        assert item["ai_reason"] == "Node-03 has pre-cached textures."


@pytest.mark.django_db
class TestFarmEvents:
    def test_record_and_query_farm_events(self, auth_client, sample_job):
        job, _, task = sample_job

        # Record via service
        event = record_event(
            event_type="TASK_SKIPPED",
            message="Supervisor skipped beauty_0001",
            actor_username="admin",
            target_type="task",
            target_id=str(task.id),
            severity=EventSeverity.WARNING,
        )
        assert event is not None

        # POST /api/telemetry/events/ via REST API
        post_response = auth_client.post(
            "/api/telemetry/events/",
            {
                "event_type": "NODE_DRAINED",
                "message": "Node 04 drained for GPU replacement",
                "severity": "INFO",
                "target_type": "worker",
                "target_id": "node-04",
            },
            format="json",
        )
        assert post_response.status_code == status.HTTP_201_CREATED

        # GET /api/telemetry/events/
        get_response = auth_client.get("/api/telemetry/events/")
        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.data["results"]) >= 2


@pytest.mark.django_db
class TestClusterTelemetryHistory:
    def test_cluster_history_aggregation(self, auth_client):
        # Insert test samples
        for i in range(5):
            record_worker_metrics(
                worker_hostname=f"node-0{i}",
                cpu_percent=45.0 + i * 5,
                memory_used_mb=4000 + i * 500,
                vram_percent=60.0 + i * 2,
                active_tasks=1,
            )

        response = auth_client.get("/api/telemetry/cluster/history/?range=1h")
        assert response.status_code == status.HTTP_200_OK
        assert "points" in response.data
        assert "cpu_load" in response.data
        assert "vram_usage" in response.data
        assert "peak_cpu" in response.data
        assert "peak_vram" in response.data
        assert "total_snapshots" in response.data
        assert len(response.data["points"]) > 0

    def test_cluster_history_filtering(self, auth_client):
        from apps.workers.models import WorkerNode, WorkerPool

        pool = WorkerPool.objects.create(name="GPU Farm")
        w1 = WorkerNode.objects.create(hostname="worker-gpu-01")
        w1.pools.add(pool)

        record_worker_metrics(
            worker_hostname="worker-gpu-01",
            cpu_percent=75.0,
            vram_percent=85.0,
            force=True,
        )
        record_worker_metrics(
            worker_hostname="worker-cpu-01",
            cpu_percent=25.0,
            vram_percent=10.0,
            force=True,
        )

        # Filter by worker
        resp_worker = auth_client.get("/api/telemetry/cluster/history/?range=1h&worker=worker-gpu-01")
        assert resp_worker.status_code == status.HTTP_200_OK
        assert resp_worker.data["total_snapshots"] >= 1

        # Filter by pool
        resp_pool = auth_client.get(f"/api/telemetry/cluster/history/?range=1h&pool={pool.name}")
        assert resp_pool.status_code == status.HTTP_200_OK
        assert resp_pool.data["total_snapshots"] >= 1


@pytest.mark.django_db
class TestWorkerMetricThrottling:
    def test_worker_metrics_throttled_within_interval(self):
        from django.core.cache import cache

        cache.clear()
        # First call succeeds and creates a record
        s1 = record_worker_metrics(worker_hostname="node-throttled", cpu_percent=50.0)
        assert s1 is not None
        assert WorkerMetricSnapshot.objects.filter(worker_hostname="node-throttled").count() == 1

        # Second rapid call is throttled and returns None
        s2 = record_worker_metrics(worker_hostname="node-throttled", cpu_percent=55.0)
        assert s2 is None
        assert WorkerMetricSnapshot.objects.filter(worker_hostname="node-throttled").count() == 1

        # Different hostname is not throttled
        s3 = record_worker_metrics(worker_hostname="node-different", cpu_percent=40.0)
        assert s3 is not None
        assert WorkerMetricSnapshot.objects.filter(worker_hostname="node-different").count() == 1

        # Force override bypasses throttle
        s4 = record_worker_metrics(worker_hostname="node-throttled", cpu_percent=60.0, force=True)
        assert s4 is not None
        assert WorkerMetricSnapshot.objects.filter(worker_hostname="node-throttled").count() == 2


@pytest.mark.django_db
class TestPruneManagementCommand:
    def test_prune_telemetry(self, sample_job):
        from django.core.cache import cache

        cache.clear()
        job, layer, task = sample_job
        record_task_log(task=task, worker_hostname="node-01", exit_status=0, log_output="Done")
        record_worker_metrics(worker_hostname="node-01", cpu_percent=50.0, force=True)

        # Dry run with days=0 (all records eligible)
        call_command("prune_telemetry", "--days=0", "--dry-run")
        assert TaskExecutionLog.objects.count() == 1
        assert WorkerMetricSnapshot.objects.count() == 1

        # Real prune
        call_command("prune_telemetry", "--days=0")
        assert TaskExecutionLog.objects.count() == 0
        assert WorkerMetricSnapshot.objects.count() == 0

