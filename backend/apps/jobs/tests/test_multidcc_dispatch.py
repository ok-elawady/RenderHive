import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.jobs.models import Job, JobState, Layer, Task, TaskState
from apps.workers.models import WorkerNode, WorkerPool, WorkerStatus

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def farm_client(db):
    group, _ = Group.objects.get_or_create(name="farm_agents")
    user = User.objects.create_user(username="farm_multidcc", password="!")
    user.groups.add(group)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def artist_client(db):
    user = User.objects.create_user(username="artist_multidcc", password="!")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def _job_and_task(layer_kwargs):
    job = Job.objects.create(
        visible_name="Multi DCC",
        project="show",
        department="lighting",
        user="artist",
        priority=50,
        log_directory="P:/show/logs",
    )
    layer = Layer.objects.create(
        job=job,
        name="beauty",
        command="hython -m renderhive_houdini.worker.render_rop --frame {frame}",
        frame_range="1-10",
        **layer_kwargs,
    )
    task = Task.objects.create(
        layer=layer,
        job=job,
        name="beauty_0001",
        frame_start=1,
        frame_end=1,
        state=TaskState.READY,
    )
    return job, layer, task


def test_dispatch_returns_complete_houdini_payload(farm_client):
    worker = WorkerNode.objects.create(
        hostname="houdini-node",
        status=WorkerStatus.ONLINE,
        cores=16,
        memory_mb=32768,
        gpu_models=["RTX 4090"],
        tags=[
            "dcc:houdini",
            "houdini:20.5.278",
            "houdini:hython",
            "houdini:husk",
        ],
        system_info={
            "capabilities": {
                "houdini": {
                    "available": True,
                    "versions": ["20.5.278"],
                    "execution_modes": ["hython", "husk"],
                }
            }
        },
    )
    assert worker.pk

    _job, _layer, task = _job_and_task(
        {
            "scene_path": "P:/show/shot/lighting.hip",
            "scene_info": {
                "dcc": "houdini",
                "houdini_version": "20.5.278",
                "renderer": "Karma XPU",
                "render_node": "/stage/usdrender_rop1",
                "camera": "/cameras/cam1",
                "project_path": "P:/show",
                "output_path": "P:/show/render/beauty.$F4.exr",
                "execution": {
                    "mode": "husk",
                    "usd_output_path": "P:/show/render/__render__.usd",
                },
            },
            "env": {
                "JOB": "P:/show",
                "RENDERHIVE_DCC": "houdini",
                "RENDERHIVE_HOUDINI_VERSION": "20.5.278",
            },
            "min_gpus": 1,
        }
    )

    response = farm_client.post(
        "/api/tasks/dispatch/",
        {"worker_name": "houdini-node"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["id"] == str(task.id)
    assert response.data["dcc"] == "houdini"
    assert response.data["dcc_version"] == "20.5.278"
    assert response.data["renderer"] == "Karma XPU"
    assert response.data["render_node"] == "/stage/usdrender_rop1"
    assert response.data["execution_mode"] == "husk"
    assert response.data["scene_info"]["output_path"].endswith("beauty.$F4.exr")


def test_maya_only_worker_cannot_claim_houdini_task(farm_client):
    WorkerNode.objects.create(
        hostname="maya-node",
        cores=16,
        memory_mb=32768,
        tags=["dcc:maya", "maya:2023"],
        system_info={
            "capabilities": {
                "maya": {
                    "available": True,
                    "versions": ["2023"],
                }
            }
        },
    )
    _job_and_task(
        {
            "scene_path": "P:/show/shot/lighting.hip",
            "scene_info": {
                "dcc": "houdini",
                "houdini_version": "20.5.278",
                "render_node": "/out/karma1",
                "execution": {"mode": "hython"},
            },
        }
    )

    response = farm_client.post(
        "/api/tasks/dispatch/",
        {"worker_name": "maya-node"},
        format="json",
    )
    assert response.status_code == 404


def test_houdini_plugin_pool_targeting_and_legacy_limit_alias(artist_client):
    pool = WorkerPool.objects.create(name="Houdini")
    payload = {
        "visible_name": "shot010",
        "project": "show",
        "department": "lighting",
        "user": "artist",
        "priority": 50,
        "log_directory": "P:/show/render/_renderhive_logs",
        "max_frames_per_worker": 2,
        "layers": [
            {
                "name": "beauty",
                "layer_type": "RENDER",
                "command": "hython -m renderhive_houdini.worker.render_rop --frame {frame}",
                "frame_range": "1-2",
                "scene_path": "P:/show/shot/lighting.hip",
                "scene_info": {
                    "dcc": "houdini",
                    "houdini_version": "20.5.278",
                    "render_node": "/out/karma1",
                    "execution": {"mode": "hython"},
                    "worker_targeting": {
                        "strategy": "selected_only",
                        "selected_pool_ids": [str(pool.id)],
                        "effective_pool_ids": [str(pool.id)],
                    },
                    "start_suspended": True,
                },
            }
        ],
    }

    response = artist_client.post("/api/jobs/", payload, format="json")
    assert response.status_code == 201, response.data

    job = Job.objects.get()
    assert job.max_tasks_per_worker == 2
    assert list(job.included_pools.values_list("id", flat=True)) == [pool.id]
    assert job.is_paused is True
    assert job.state == JobState.PAUSED
