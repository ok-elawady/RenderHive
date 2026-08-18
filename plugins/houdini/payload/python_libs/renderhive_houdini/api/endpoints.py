from __future__ import absolute_import

from renderhive_houdini.api.contract import validate_endpoint_config

DEFAULT_ENDPOINTS = {
    "connection_test": "/api/jobs/?page=1",
    "jobs": "/api/jobs/",
    "job_status": "/api/jobs/{job_id}/",
    "job_update": "/api/jobs/{job_id}/",
    "job_pause": "/api/jobs/{job_id}/pause/",
    "job_resume": "/api/jobs/{job_id}/resume/",
    "job_delete": "/api/jobs/{job_id}/",
    "job_layers": "/api/jobs/{job_id}/layers/",
    "job_layer_detail": "/api/jobs/{job_id}/layers/{layer_id}/",
    "job_layer_tasks": "/api/jobs/{job_id}/layers/{layer_id}/tasks/",
    "job_layer_task_detail": "/api/jobs/{job_id}/layers/{layer_id}/tasks/{task_id}/",
    "workers": "/api/workers/",
    "worker_detail": "/api/workers/{worker_id}/",
    "pools": "/api/pools/",
    "pool_detail": "/api/pools/{pool_id}/",
    "pool_workers": "/api/pools/{pool_id}/workers/",
}


def validate_endpoints(endpoints):
    return validate_endpoint_config(endpoints)
