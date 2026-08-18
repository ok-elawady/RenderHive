import datetime
import pytest
from django.utils import timezone

from apps.jobs.models import Job, JobState, Layer, Task, TaskState
from apps.jobs.tasks import reconcile_queue_state
from apps.telemetry.models import FarmEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_hierarchy(db):
    job = Job.objects.create(
        name="proj_reconcile_job_001",
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
        timeout_seconds=300,
    )
    return job, layer


class TestReconcileQueueState:
    def test_reconcile_fixes_drifted_counters_and_state_to_pending(self, sample_hierarchy):
        job, layer = sample_hierarchy
        # Create 2 ready tasks
        task1 = Task.objects.create(job=job, layer=layer, name="frame_1", frame_start=1, frame_end=1, state=TaskState.READY)
        task2 = Task.objects.create(job=job, layer=layer, name="frame_2", frame_start=2, frame_end=2, state=TaskState.READY)

        # Intentionally drift the cached counters and state on the job/layer
        Job.objects.filter(pk=job.pk).update(state=JobState.RUNNING, running_tasks=5, ready_tasks=0)
        Layer.objects.filter(pk=layer.pk).update(state=JobState.RUNNING, running_tasks=5, ready_tasks=0)

        result = reconcile_queue_state()

        job.refresh_from_db()
        layer.refresh_from_db()

        assert job.state == JobState.PENDING
        assert job.running_tasks == 0
        assert job.ready_tasks == 2
        assert layer.state == JobState.PENDING
        assert layer.running_tasks == 0
        assert layer.ready_tasks == 2
        assert result["reconciled_jobs"] == 1
        assert result["reconciled_layers"] == 1

    def test_reconcile_sets_state_to_running_when_active_tasks_exist(self, sample_hierarchy):
        job, layer = sample_hierarchy
        Task.objects.create(job=job, layer=layer, name="frame_1", frame_start=1, frame_end=1, state=TaskState.RUNNING, started_at=timezone.now())
        Task.objects.create(job=job, layer=layer, name="frame_2", frame_start=2, frame_end=2, state=TaskState.READY)

        # Intentionally drift state to PENDING
        Job.objects.filter(pk=job.pk).update(state=JobState.PENDING, running_tasks=0)
        Layer.objects.filter(pk=layer.pk).update(state=JobState.PENDING, running_tasks=0)

        result = reconcile_queue_state()

        job.refresh_from_db()
        layer.refresh_from_db()

        assert job.state == JobState.RUNNING
        assert job.running_tasks == 1
        assert job.ready_tasks == 1
        assert layer.state == JobState.RUNNING

    def test_reconcile_sets_state_to_finished_when_all_succeeded(self, sample_hierarchy):
        job, layer = sample_hierarchy
        Task.objects.create(job=job, layer=layer, name="frame_1", frame_start=1, frame_end=1, state=TaskState.SUCCEEDED)
        Task.objects.create(job=job, layer=layer, name="frame_2", frame_start=2, frame_end=2, state=TaskState.SKIPPED)

        # Intentionally drift state
        Job.objects.filter(pk=job.pk).update(state=JobState.RUNNING)
        Layer.objects.filter(pk=layer.pk).update(state=JobState.RUNNING)

        reconcile_queue_state()

        job.refresh_from_db()
        layer.refresh_from_db()

        assert job.state == JobState.FINISHED
        assert job.stopped_at is not None
        assert layer.state == JobState.FINISHED

    def test_reconcile_sets_state_to_failed_when_no_active_and_failures_exist(self, sample_hierarchy):
        job, layer = sample_hierarchy
        Task.objects.create(job=job, layer=layer, name="frame_1", frame_start=1, frame_end=1, state=TaskState.FAILED)
        Task.objects.create(job=job, layer=layer, name="frame_2", frame_start=2, frame_end=2, state=TaskState.SUCCEEDED)

        # Intentionally set state to RUNNING
        Job.objects.filter(pk=job.pk).update(state=JobState.RUNNING)
        Layer.objects.filter(pk=layer.pk).update(state=JobState.RUNNING)

        reconcile_queue_state()

        job.refresh_from_db()
        layer.refresh_from_db()

        assert job.state == JobState.FAILED
        assert job.stopped_at is not None
        assert layer.state == JobState.FAILED

    def test_reconcile_times_out_and_requeues_hung_task(self, sample_hierarchy):
        job, layer = sample_hierarchy
        layer.timeout_seconds = 60
        layer.save()

        stale_started_at = timezone.now() - datetime.timedelta(seconds=120)
        task = Task.objects.create(
            job=job,
            layer=layer,
            name="frame_hung",
            frame_start=1,
            frame_end=1,
            state=TaskState.RUNNING,
            worker_name="worker-01",
            started_at=stale_started_at,
            retries=0,
            max_retries=3,
        )

        result = reconcile_queue_state()

        task.refresh_from_db()
        assert task.state == TaskState.READY
        assert task.worker_name == ""
        assert task.retries == 1
        assert result["timed_out_tasks_requeued"] == 1
        assert FarmEvent.objects.filter(event_type="TASK_TIMEOUT", target_id=str(task.id)).exists()

    def test_reconcile_fails_hung_task_when_retries_exhausted(self, sample_hierarchy):
        job, layer = sample_hierarchy
        layer.timeout_seconds = 60
        layer.save()

        stale_started_at = timezone.now() - datetime.timedelta(seconds=120)
        task = Task.objects.create(
            job=job,
            layer=layer,
            name="frame_hung_max",
            frame_start=1,
            frame_end=1,
            state=TaskState.RUNNING,
            worker_name="worker-01",
            started_at=stale_started_at,
            retries=3,
            max_retries=3,
        )

        result = reconcile_queue_state()

        task.refresh_from_db()
        assert task.state == TaskState.FAILED
        assert task.exit_status == 124
        assert result["timed_out_tasks_failed"] == 1
        assert FarmEvent.objects.filter(event_type="TASK_FAILED", target_id=str(task.id)).exists()
