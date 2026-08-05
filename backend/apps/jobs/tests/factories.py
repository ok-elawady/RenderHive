import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.jobs.models import Dependency, DependencyType, Task, TaskState, Job, JobState, Layer, LayerType

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.Sequence(lambda n: f"user_{n}@example.com")


class JobFactory(DjangoModelFactory):
    class Meta:
        model = Job

    name = factory.Sequence(lambda n: f"job_{n}_1234567890")
    visible_name = factory.Sequence(lambda n: f"Test Job {n}")
    project = "test_project"
    department = "test_dept"
    user = "test_user"
    state = JobState.PENDING
    priority = 50
    log_directory = "/tmp/logs/"


class LayerFactory(DjangoModelFactory):
    class Meta:
        model = Layer

    job = factory.SubFactory(JobFactory)
    name = factory.Sequence(lambda n: f"layer_{n}")
    layer_type = LayerType.RENDER
    command = "render -s {frame} -e {frame} scene.ma"
    frame_range = "1-10"
    state = JobState.PENDING


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    layer = factory.SubFactory(LayerFactory)
    job = factory.SelfAttribute("layer.job")
    name = factory.Sequence(lambda n: f"task_{n}")
    frame_start = factory.Sequence(lambda n: n)
    frame_end = factory.Sequence(lambda n: n)
    state = TaskState.WAITING


class DependencyFactory(DjangoModelFactory):
    class Meta:
        model = Dependency

    type = DependencyType.TASK_ON_TASK
    dep_job = factory.SelfAttribute("dep_task.job")
    dep_layer = factory.SelfAttribute("dep_task.layer")
    dep_task = factory.SubFactory(TaskFactory)
    parent_job = factory.SelfAttribute("parent_task.job")
    parent_layer = factory.SelfAttribute("parent_task.layer")
    parent_task = factory.SubFactory(TaskFactory)
