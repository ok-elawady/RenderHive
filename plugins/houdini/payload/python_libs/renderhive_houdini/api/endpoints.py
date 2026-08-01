from __future__ import absolute_import


DEFAULT_ENDPOINTS = {
    "connection_test": "/api/jobs/?page=1",
    "jobs": "/api/jobs/",
    "job_status": "/api/jobs/{job_id}/",
    "workers": "/api/workers/",
    "worker_detail": "/api/workers/{worker_id}/",
    "pools": "/api/pools/",
    "pool_detail": "/api/pools/{pool_id}/",
}


REQUIRED_ENDPOINTS = (
    "connection_test",
    "jobs",
    "workers",
    "pools",
)


def validate_endpoints(endpoints):
    endpoints = endpoints if isinstance(endpoints, dict) else {}
    missing = [name for name in REQUIRED_ENDPOINTS if not str(endpoints.get(name) or "").strip()]
    if missing:
        raise ValueError("Missing API endpoint configuration: {}".format(", ".join(missing)))
    return True
