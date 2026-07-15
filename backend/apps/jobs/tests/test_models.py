import pytest
from django.core.exceptions import ValidationError

from apps.jobs.models import Dependency, DependencyType, JobState

from .factories import FrameFactory, JobFactory, LayerFactory

pytestmark = pytest.mark.django_db


class TestJobModel:
    def test_job_creation_defaults(self):
        job = JobFactory()
        assert job.state == JobState.PENDING
        assert job.priority == 50
        assert job.max_frames_per_worker == 1
        assert job.is_paused is False
        assert job.total_frames == 0


class TestDependencyModel:
    def test_clean_frame_on_frame_valid(self):
        dep_frame = FrameFactory()
        parent_frame = FrameFactory()
        dependency = Dependency(
            type=DependencyType.FRAME_ON_FRAME,
            dep_job=dep_frame.job,
            parent_job=parent_frame.job,
            dep_frame=dep_frame,
            parent_frame=parent_frame,
        )
        dependency.clean()  # Should not raise

    def test_clean_frame_on_frame_missing_fks(self):
        dep_frame = FrameFactory()
        dependency = Dependency(
            type=DependencyType.FRAME_ON_FRAME,
            dep_job=dep_frame.job,
            dep_frame=dep_frame,
            # Missing parent_frame
        )
        with pytest.raises(ValidationError, match="requires both dep_frame and parent_frame"):
            dependency.clean()

    def test_clean_frame_on_frame_self_dependency(self):
        frame = FrameFactory()
        dependency = Dependency(
            type=DependencyType.FRAME_ON_FRAME,
            dep_job=frame.job,
            parent_job=frame.job,
            dep_frame=frame,
            parent_frame=frame,
        )
        with pytest.raises(ValidationError, match="A frame cannot depend on itself"):
            dependency.clean()

    def test_clean_layer_on_layer_missing_fks(self):
        dep_layer = LayerFactory()
        dependency = Dependency(
            type=DependencyType.LAYER_ON_LAYER,
            dep_job=dep_layer.job,
            dep_layer=dep_layer,
            # Missing parent_layer
        )
        with pytest.raises(ValidationError, match="requires both dep_layer and parent_layer"):
            dependency.clean()

    def test_clean_job_on_job_missing_fks(self):
        dep_job = JobFactory()
        dependency = Dependency(
            type=DependencyType.JOB_ON_JOB,
            dep_job=dep_job,
            # Missing parent_job
        )
        with pytest.raises(ValidationError, match="requires both dep_job and parent_job"):
            dependency.clean()
