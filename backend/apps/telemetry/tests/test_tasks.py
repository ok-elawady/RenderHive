import datetime

import pytest
from django.utils import timezone

from apps.jobs.models import Job, Layer, Task
from apps.telemetry.models import DispatchTrace, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot
from apps.telemetry.services import record_worker_metrics
from apps.telemetry.tasks import prune_old_telemetry

pytestmark = pytest.mark.django_db


class TestPruneOldTelemetryTask:
    def test_prune_task_deletes_expired_records(self, db):
        job = Job.objects.create(
            name="proj_prune_job",
            project="test_proj",
            department="Lighting",
            user="testartist",
            log_directory="/renders/logs",
        )
        layer = Layer.objects.create(job=job, name="beauty", command="render", frame_range="1-5")
        task = Task.objects.create(job=job, layer=layer, name="beauty_0001", frame_start=1, frame_end=1)

        # Create expired and recent records
        expired_date = timezone.now() - datetime.timedelta(days=45)

        log = TaskExecutionLog.objects.create(task=task, job=job, worker_hostname="node-01")
        TaskExecutionLog.objects.filter(id=log.id).update(created_at=expired_date)

        event = FarmEvent.objects.create(event_type="JOB_STARTED", message="Job started")
        FarmEvent.objects.filter(id=event.id).update(created_at=expired_date)

        dispatch = DispatchTrace.objects.create(task=task, job=job, worker_hostname="node-01")
        DispatchTrace.objects.filter(id=dispatch.id).update(dispatched_at=expired_date)

        snapshot = record_worker_metrics(worker_hostname="node-01", cpu_percent=50.0, force=True)
        assert snapshot is not None
        WorkerMetricSnapshot.objects.filter(id=snapshot.id).update(recorded_at=expired_date)

        # Recent snapshot
        recent_snapshot = record_worker_metrics(worker_hostname="node-02", cpu_percent=60.0, force=True)

        result = prune_old_telemetry(days=30)

        assert result["deleted_task_logs"] == 1
        assert result["deleted_events"] == 1
        assert result["deleted_dispatches"] == 1
        assert result["deleted_metric_snapshots"] == 1

        assert TaskExecutionLog.objects.count() == 0
        assert FarmEvent.objects.count() == 0
        assert DispatchTrace.objects.count() == 0
        assert WorkerMetricSnapshot.objects.filter(id=recent_snapshot.id).exists()
