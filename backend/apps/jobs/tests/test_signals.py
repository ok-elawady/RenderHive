import pytest

from apps.jobs.models import FrameState, Job, Layer

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
