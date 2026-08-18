import datetime

import pytest
from django.utils import timezone

from apps.jobs.models import Job, Layer, Task
from apps.telemetry.models import DispatchTrace, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot
from apps.telemetry.services import record_worker_metrics
from apps.telemetry.tasks import prune_old_telemetry, snapshot_online_worker_metrics
from apps.workers.models import WorkerNode, WorkerStatus

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


class TestSnapshotOnlineWorkerMetricsTask:
    def test_snapshot_captures_online_workers(self, db):
        w1 = WorkerNode.objects.create(
            hostname="node-gpu-01",
            status=WorkerStatus.ONLINE,
            system_info={"cpu_percent": 45.0, "vram_percent": 80.0, "memory_used_mb": 4096, "total_memory_mb": 16384},
        )
        w2 = WorkerNode.objects.create(
            hostname="node-cpu-02",
            status=WorkerStatus.RENDERING,
            system_info={"cpu_percent": 95.0, "memory_used_mb": 8192, "total_memory_mb": 16384},
        )
        w3 = WorkerNode.objects.create(
            hostname="node-offline-03",
            status=WorkerStatus.OFFLINE,
            system_info={"cpu_percent": 0.0},
        )

        result = snapshot_online_worker_metrics()

        assert result["online_workers"] == 2
        assert result["recorded_snapshots"] == 2

        s1 = WorkerMetricSnapshot.objects.get(worker_hostname=w1.hostname)
        assert s1.cpu_percent == 45.0
        assert s1.vram_percent == 80.0
        assert s1.active_tasks == 0

        s2 = WorkerMetricSnapshot.objects.get(worker_hostname=w2.hostname)
        assert s2.cpu_percent == 95.0
        assert s2.vram_percent == 0.0  # CPU node correctly reports 0.0 VRAM, not memory_percent
        assert s2.active_tasks == 1  # RENDERING worker has 1 active task

        assert not WorkerMetricSnapshot.objects.filter(worker_hostname=w3.hostname).exists()
