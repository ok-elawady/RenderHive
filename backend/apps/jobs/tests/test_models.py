import pytest
from django.core.exceptions import ValidationError

from apps.jobs.models import Dependency, DependencyType, JobState

from .factories import TaskFactory, JobFactory, LayerFactory

pytestmark = pytest.mark.django_db


class TestJobModel:
    def test_job_creation_defaults(self):
        job = JobFactory()
        assert job.state == JobState.PENDING
        assert job.priority == 50
        assert job.max_tasks_per_worker == 1
        assert job.is_paused is False
        assert job.total_tasks == 0


class TestDependencyModel:
    def test_clean_task_on_task_valid(self):
        dep_task = TaskFactory()
        parent_task = TaskFactory()
        dependency = Dependency(
            type=DependencyType.TASK_ON_TASK,
            dep_job=dep_task.job,
            parent_job=parent_task.job,
            dep_task=dep_task,
            parent_task=parent_task,
        )
        dependency.clean()  # Should not raise

    def test_clean_task_on_task_missing_fks(self):
        dep_task = TaskFactory()
        dependency = Dependency(
            type=DependencyType.TASK_ON_TASK,
            dep_job=dep_task.job,
            dep_task=dep_task,
            # Missing parent_task
        )
        with pytest.raises(ValidationError, match="requires both dep_task and parent_task"):
            dependency.clean()

    def test_clean_task_on_task_self_dependency(self):
        task = TaskFactory()
        dependency = Dependency(
            type=DependencyType.TASK_ON_TASK,
            dep_job=task.job,
            parent_job=task.job,
            dep_task=task,
            parent_task=task,
        )
        with pytest.raises(ValidationError, match="A task cannot depend on itself"):
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
