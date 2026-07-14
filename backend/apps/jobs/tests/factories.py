import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.jobs.models import Dependency, DependencyType, Frame, FrameState, Job, JobState, Layer, LayerType

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


class FrameFactory(DjangoModelFactory):
    class Meta:
        model = Frame

    layer = factory.SubFactory(LayerFactory)
    job = factory.SelfAttribute("layer.job")
    name = factory.Sequence(lambda n: f"frame_{n}")
    number = factory.Sequence(lambda n: n)
    state = FrameState.WAITING


class DependencyFactory(DjangoModelFactory):
    class Meta:
        model = Dependency

    type = DependencyType.FRAME_ON_FRAME
    dep_job = factory.SelfAttribute("dep_frame.job")
    dep_layer = factory.SelfAttribute("dep_frame.layer")
    dep_frame = factory.SubFactory(FrameFactory)
    parent_job = factory.SelfAttribute("parent_frame.job")
    parent_layer = factory.SelfAttribute("parent_frame.layer")
    parent_frame = factory.SubFactory(FrameFactory)
