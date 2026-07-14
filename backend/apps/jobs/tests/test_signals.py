import pytest

from apps.jobs.models import FrameState

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
