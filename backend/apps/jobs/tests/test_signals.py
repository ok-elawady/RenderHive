import pytest

from apps.jobs.models import FrameState, Job, JobState, Layer

from .factories import DependencyFactory, FrameFactory, LayerFactory

pytestmark = pytest.mark.django_db


class TestFrameSignals:
    def test_frame_creation_increments_parent_counters(self):
        layer = LayerFactory()
        job = layer.job

        FrameFactory.create_batch(3, layer=layer, job=job)

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.total_frames == 3
        assert layer.waiting_frames == 3
        assert job.total_frames == 3
        assert job.waiting_frames == 3

    def test_frame_state_transition_updates_parent_counters(self):
        frame = FrameFactory(state=FrameState.WAITING)
        layer = frame.layer
        job = frame.job

        # Change state
        frame.state = FrameState.RUNNING
        frame.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.waiting_frames == 0
        assert layer.running_frames == 1
        assert job.waiting_frames == 0
        assert job.running_frames == 1

    def test_frame_succeeded_cascades_satisfaction(self):
        parent_frame = FrameFactory(state=FrameState.RUNNING)
        dep_frame = FrameFactory(state=FrameState.WAITING)

        # Create dependency
        dep = DependencyFactory(parent_frame=parent_frame, dep_frame=dep_frame)
        dep_frame.refresh_from_db()
        assert dep_frame.depend_count == 1

        # Parent succeeds
        parent_frame.state = FrameState.SUCCEEDED
        parent_frame.save()

        # Dep should be satisfied
        dep.refresh_from_db()
        assert dep.is_satisfied is True

        # Frame should be ready
        dep_frame.refresh_from_db()
        assert dep_frame.depend_count == 0
        assert dep_frame.state == FrameState.READY

    def test_checkpoint_counter_lifecycle(self):
        """RUNNING → CHECKPOINT → SUCCEEDED keeps running_frames correct throughout.

        Verifies that the CHECKPOINT state is correctly mapped to running_frames
        in the signal, so transitioning through it doesn't corrupt the counters.
        """
        frame = FrameFactory(state=FrameState.RUNNING)
        Layer.objects.filter(pk=frame.layer.pk).update(running_frames=1, total_frames=1)
        Job.objects.filter(pk=frame.job.pk).update(running_frames=1, total_frames=1)

        # RUNNING → CHECKPOINT: running_frames must stay at 1 (worker is still active)
        frame.state = FrameState.CHECKPOINT
        frame.save()
        frame.layer.refresh_from_db()
        frame.job.refresh_from_db()
        assert frame.layer.running_frames == 1
        assert frame.job.running_frames == 1

        # CHECKPOINT → SUCCEEDED: running_frames drops, succeeded_frames rises
        frame.state = FrameState.SUCCEEDED
        frame.save()
        frame.layer.refresh_from_db()
        frame.job.refresh_from_db()
        assert frame.layer.running_frames == 0
        assert frame.layer.succeeded_frames == 1
        assert frame.job.running_frames == 0
        assert frame.job.succeeded_frames == 1


class TestDependencySignals:
    def test_dependency_creation_increments_depend_count(self):
        frame = FrameFactory(state=FrameState.WAITING)
        assert frame.depend_count == 0

        DependencyFactory(dep_frame=frame)

        frame.refresh_from_db()
        assert frame.depend_count == 1

    def test_dependency_satisfaction_unblocks_frame(self):
        dep = DependencyFactory()
        frame = dep.dep_frame

        frame.refresh_from_db()
        assert frame.depend_count == 1
        assert frame.state == FrameState.WAITING

        # Satisfy it
        dep.is_satisfied = True
        dep.save()

        frame.refresh_from_db()
        assert frame.depend_count == 0
        assert frame.state == FrameState.READY

    def test_dependency_deletion_repairs_depend_count(self):
        dep = DependencyFactory()
        frame = dep.dep_frame

        frame.refresh_from_db()
        assert frame.depend_count == 1

        # Delete it
        dep.delete()

        frame.refresh_from_db()
        assert frame.depend_count == 0
        assert frame.state == FrameState.READY


class TestJobAndLayerStateTransitions:
    def test_job_layer_transition_to_running(self):
        frame = FrameFactory(state=FrameState.READY)
        layer = frame.layer
        job = frame.job
        
        # Initial state is PENDING
        assert job.state == JobState.PENDING
        assert layer.state == JobState.PENDING

        # Change state
        frame.state = FrameState.RUNNING
        frame.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.state == JobState.RUNNING
        assert job.state == JobState.RUNNING

    def test_job_layer_transition_to_finished(self):
        # Create a layer with 2 frames
        layer = LayerFactory()
        job = layer.job
        frame1 = FrameFactory(layer=layer, job=job, state=FrameState.RUNNING)
        frame2 = FrameFactory(layer=layer, job=job, state=FrameState.RUNNING)

        # First frame succeeds
        frame1.state = FrameState.SUCCEEDED
        frame1.save()

        job.refresh_from_db()
        # Not finished yet because total_frames is 2 but succeeded is 1
        assert job.state != JobState.FINISHED

        # Second frame succeeds
        frame2.state = FrameState.SUCCEEDED
        frame2.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.state == JobState.FINISHED
        assert job.state == JobState.FINISHED
        assert job.stopped_at is not None

    def test_job_layer_transition_to_failed(self):
        layer = LayerFactory()
        job = layer.job
        frame1 = FrameFactory(layer=layer, job=job, state=FrameState.RUNNING)
        frame2 = FrameFactory(layer=layer, job=job, state=FrameState.READY)

        # One frame fails, but another is ready, so job doesn't fail yet
        frame1.state = FrameState.FAILED
        frame1.save()

        job.refresh_from_db()
        assert job.state != JobState.FAILED

        # The other frame fails, now there are no running/ready frames
        frame2.state = FrameState.FAILED
        frame2.save()

        layer.refresh_from_db()
        job.refresh_from_db()

        assert layer.state == JobState.FAILED
        assert job.state == JobState.FAILED
        assert job.stopped_at is not None

    def test_paused_job_does_not_transition_to_running(self):
        frame = FrameFactory(state=FrameState.READY)
        job = frame.job
        
        # Pause the job
        job.is_paused = True
        job.state = JobState.PAUSED
        job.save()

        # Start the frame
        frame.state = FrameState.RUNNING
        frame.save()

        job.refresh_from_db()
        
        # Job should remain PAUSED, not switch to RUNNING
        assert job.state == JobState.PAUSED
        assert job.is_paused is True
