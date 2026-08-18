import pytest

from apps.jobs.models import Job, JobState, Layer, TaskState

from .factories import DependencyFactory, LayerFactory, TaskFactory

pytestmark = pytest.mark.django_db


class TestTaskSignals:
    def test_frame_creation_increments_parent_counters(self):
        layer = LayerFactory()
        job = layer.job

        TaskFactory.create_batch(3, layer=layer, job=job)

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.total_tasks == 3
        assert layer.waiting_tasks == 3
        assert job.total_tasks == 3
        assert job.waiting_tasks == 3

    def test_frame_state_transition_updates_parent_counters(self):
        task = TaskFactory(state=TaskState.WAITING)
        layer = task.layer
        job = task.job

        # Change state
        task.state = TaskState.RUNNING
        task.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.waiting_tasks == 0
        assert layer.running_tasks == 1
        assert job.waiting_tasks == 0
        assert job.running_tasks == 1

    def test_frame_succeeded_cascades_satisfaction(self):
        parent_task = TaskFactory(state=TaskState.RUNNING)
        dep_task = TaskFactory(state=TaskState.WAITING)

        # Create dependency
        dep = DependencyFactory(parent_task=parent_task, dep_task=dep_task)
        dep_task.refresh_from_db()
        assert dep_task.depend_count == 1

        # Parent succeeds
        parent_task.state = TaskState.SUCCEEDED
        parent_task.save()

        # Dep should be satisfied
        dep.refresh_from_db()
        assert dep.is_satisfied is True

        # Task should be ready
        dep_task.refresh_from_db()
        assert dep_task.depend_count == 0
        assert dep_task.state == TaskState.READY

    def test_checkpoint_counter_lifecycle(self):
        """RUNNING → CHECKPOINT → SUCCEEDED keeps running_tasks correct throughout.

        Verifies that the CHECKPOINT state is correctly mapped to running_tasks
        in the signal, so transitioning through it doesn't corrupt the counters.
        """
        task = TaskFactory(state=TaskState.RUNNING)
        Layer.objects.filter(pk=task.layer.pk).update(running_tasks=1, total_tasks=1)
        Job.objects.filter(pk=task.job.pk).update(running_tasks=1, total_tasks=1)

        # RUNNING → CHECKPOINT: running_tasks must stay at 1 (worker is still active)
        task.state = TaskState.CHECKPOINT
        task.save()
        task.layer.refresh_from_db()
        task.job.refresh_from_db()
        assert task.layer.running_tasks == 1
        assert task.job.running_tasks == 1

        # CHECKPOINT → SUCCEEDED: running_tasks drops, succeeded_tasks rises
        task.state = TaskState.SUCCEEDED
        task.save()
        task.layer.refresh_from_db()
        task.job.refresh_from_db()
        assert task.layer.running_tasks == 0
        assert task.layer.succeeded_tasks == 1
        assert task.job.running_tasks == 0
        assert task.job.succeeded_tasks == 1


class TestDependencySignals:
    def test_dependency_creation_increments_depend_count(self):
        task = TaskFactory(state=TaskState.WAITING)
        assert task.depend_count == 0

        DependencyFactory(dep_task=task)

        task.refresh_from_db()
        assert task.depend_count == 1

    def test_dependency_satisfaction_unblocks_frame(self):
        dep = DependencyFactory()
        task = dep.dep_task

        task.refresh_from_db()
        assert task.depend_count == 1
        assert task.state == TaskState.WAITING

        # Satisfy it
        dep.is_satisfied = True
        dep.save()

        task.refresh_from_db()
        assert task.depend_count == 0
        assert task.state == TaskState.READY

    def test_dependency_deletion_repairs_depend_count(self):
        dep = DependencyFactory()
        task = dep.dep_task

        task.refresh_from_db()
        assert task.depend_count == 1

        # Delete it
        dep.delete()

        task.refresh_from_db()
        assert task.depend_count == 0
        assert task.state == TaskState.READY


class TestJobAndLayerStateTransitions:
    def test_job_layer_transition_to_running(self):
        task = TaskFactory(state=TaskState.READY)
        layer = task.layer
        job = task.job

        # Initial state is PENDING
        assert job.state == JobState.PENDING
        assert layer.state == JobState.PENDING

        # Change state
        task.state = TaskState.RUNNING
        task.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.state == JobState.RUNNING
        assert job.state == JobState.RUNNING

    def test_job_layer_transition_to_finished(self):
        # Create a layer with 2 frames
        layer = LayerFactory()
        job = layer.job
        task1 = TaskFactory(layer=layer, job=job, state=TaskState.RUNNING)
        task2 = TaskFactory(layer=layer, job=job, state=TaskState.RUNNING)

        # First frame succeeds
        task1.state = TaskState.SUCCEEDED
        task1.save()

        job.refresh_from_db()
        # Not finished yet because total_tasks is 2 but succeeded is 1
        assert job.state != JobState.FINISHED

        # Second frame succeeds
        task2.state = TaskState.SUCCEEDED
        task2.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.state == JobState.FINISHED
        assert job.state == JobState.FINISHED
        assert job.stopped_at is not None

    def test_job_layer_transition_to_failed(self):
        layer = LayerFactory()
        job = layer.job
        task1 = TaskFactory(layer=layer, job=job, state=TaskState.RUNNING)
        task2 = TaskFactory(layer=layer, job=job, state=TaskState.READY)

        # One frame fails, but another is ready, so job doesn't fail yet
        task1.state = TaskState.FAILED
        task1.save()

        job.refresh_from_db()
        assert job.state != JobState.FAILED

        # The other frame fails, now there are no running/ready frames
        task2.state = TaskState.FAILED
        task2.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.state == JobState.FAILED
        assert job.state == JobState.FAILED
        assert job.stopped_at is not None

    def test_paused_job_does_not_transition_to_running(self):
        task = TaskFactory(state=TaskState.READY)
        job = task.job

        # Pause the job
        job.is_paused = True
        job.state = JobState.PAUSED
        job.save()

        # Start the frame
        task.state = TaskState.RUNNING
        task.save()

        job.refresh_from_db()

        # Job should remain PAUSED, not switch to RUNNING
        assert job.state == JobState.PAUSED

    def test_job_layer_transition_to_pending_when_no_active_workers(self):
        layer = LayerFactory()
        job = layer.job
        task1 = TaskFactory(layer=layer, job=job, state=TaskState.READY)
        task2 = TaskFactory(layer=layer, job=job, state=TaskState.READY)

        # Worker starts task1
        task1.state = TaskState.RUNNING
        task1.save()

        job.refresh_from_db()
        layer.refresh_from_db()
        assert job.state == JobState.RUNNING
        assert layer.state == JobState.RUNNING

        # Worker finishes task1; now running_tasks == 0 and task2 is READY in queue
        task1.state = TaskState.SUCCEEDED
        task1.save()

        job.refresh_from_db()
        layer.refresh_from_db()
        assert job.state == JobState.PENDING
        assert layer.state == JobState.PENDING
