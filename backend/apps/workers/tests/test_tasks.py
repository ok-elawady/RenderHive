import datetime

import pytest
from django.utils import timezone

from apps.jobs.models import Job, Layer, Task, TaskState
from apps.telemetry.models import FarmEvent
from apps.workers.models import WorkerNode, WorkerStatus
from apps.workers.tasks import reap_stale_workers_and_tasks

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_hierarchy(db):
    job = Job.objects.create(
        name="proj_reap_job_001",
        project="test_proj",
        department="Lighting",
        user="testartist",
        log_directory="/renders/logs",
    )
    layer = Layer.objects.create(
        job=job,
        name="beauty",
        command="render -f {frame}",
        frame_range="1-10",
    )
    return job, layer


class TestReapStaleWorkersAndTasks:
    def test_reap_stale_worker_marks_offline(self):
        stale_time = timezone.now() - datetime.timedelta(seconds=60)
        worker = WorkerNode.objects.create(
            hostname="stale-node-1",
            status=WorkerStatus.ONLINE,
            last_ping=stale_time,
        )

        result = reap_stale_workers_and_tasks()

        worker.refresh_from_db()
        assert worker.status == WorkerStatus.OFFLINE
        assert result["reaped_workers"] == 1
        assert FarmEvent.objects.filter(event_type="WORKER_OFFLINE", target_id=str(worker.id)).exists()

    def test_active_worker_left_untouched(self):
        recent_time = timezone.now() - datetime.timedelta(seconds=5)
        worker = WorkerNode.objects.create(
            hostname="active-node-1",
            status=WorkerStatus.ONLINE,
            last_ping=recent_time,
        )

        result = reap_stale_workers_and_tasks()

        worker.refresh_from_db()
        assert worker.status == WorkerStatus.ONLINE
        assert result["reaped_workers"] == 0

    def test_orphaned_task_requeued(self, sample_hierarchy):
        job, layer = sample_hierarchy
        stale_time = timezone.now() - datetime.timedelta(seconds=60)
        worker = WorkerNode.objects.create(
            hostname="render-node-1",
            status=WorkerStatus.RENDERING,
            last_ping=stale_time,
        )

        task = Task.objects.create(
            job=job,
            layer=layer,
            name="beauty_0001",
            frame_start=1,
            frame_end=1,
            state=TaskState.RUNNING,
            worker_name=worker.hostname,
            retries=0,
            max_retries=3,
        )

        result = reap_stale_workers_and_tasks()

        task.refresh_from_db()
        worker.refresh_from_db()

        assert worker.status == WorkerStatus.OFFLINE
        assert task.state == TaskState.READY
        assert task.worker_name == ""
        assert task.retries == 1
        assert result["requeued_tasks"] == 1
        assert FarmEvent.objects.filter(event_type="TASK_REQUEUED", target_id=str(task.id)).exists()

    def test_orphaned_task_failed_when_max_retries_exceeded(self, sample_hierarchy):
        job, layer = sample_hierarchy
        stale_time = timezone.now() - datetime.timedelta(seconds=60)
        worker = WorkerNode.objects.create(
            hostname="render-node-2",
            status=WorkerStatus.RENDERING,
            last_ping=stale_time,
        )

        task = Task.objects.create(
            job=job,
            layer=layer,
            name="beauty_0002",
            frame_start=2,
            frame_end=2,
            state=TaskState.RUNNING,
            worker_name=worker.hostname,
            retries=3,
            max_retries=3,
        )

        result = reap_stale_workers_and_tasks()

        task.refresh_from_db()
        worker.refresh_from_db()

        assert worker.status == WorkerStatus.OFFLINE
        assert task.state == TaskState.FAILED
        assert task.exit_status == -1
        assert result["failed_tasks"] == 1
        assert FarmEvent.objects.filter(event_type="TASK_FAILED", target_id=str(task.id)).exists()
