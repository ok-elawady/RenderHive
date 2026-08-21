from __future__ import absolute_import


from .errors import ApiContractError
from .version import API_CONTRACT_VERSION


SUBMITTER_ENDPOINTS = {
    "connection_test": {
        "method": "GET",
        "path": "/api/jobs/",
        "owner": "maya_submitter",
    },
    "jobs": {
        "methods": ("GET", "POST"),
        "path": "/api/jobs/",
        "owner": "maya_submitter",
    },
    "job_status": {
        "method": "GET",
        "path": "/api/jobs/{id}/",
        "owner": "maya_submitter",
    },
    "job_update": {
        "method": "PATCH",
        "path": "/api/jobs/{id}/",
        "owner": "maya_submitter",
    },
    "job_pause": {
        "method": "POST",
        "path": "/api/jobs/{id}/pause/",
        "owner": "maya_submitter",
    },
    "job_resume": {
        "method": "POST",
        "path": "/api/jobs/{id}/resume/",
        "owner": "maya_submitter",
    },
    "job_delete": {
        "method": "DELETE",
        "path": "/api/jobs/{id}/",
        "owner": "maya_submitter",
    },
    "job_layers": {
        "method": "GET",
        "path": "/api/jobs/{job_pk}/layers/",
        "owner": "maya_submitter",
    },
    "job_layer_detail": {
        "method": "GET",
        "path": "/api/jobs/{job_pk}/layers/{id}/",
        "owner": "maya_submitter",
    },
    "job_layer_tasks": {
        "method": "GET",
        "path": "/api/jobs/{job_pk}/layers/{layer_pk}/tasks/",
        "owner": "maya_submitter",
    },
    "job_layer_task_detail": {
        "method": "GET",
        "path": "/api/jobs/{job_pk}/layers/{layer_pk}/tasks/{id}/",
        "owner": "maya_submitter",
    },
    "workers": {
        "method": "GET",
        "path": "/api/workers/",
        "owner": "maya_submitter",
    },
    "worker_detail": {
        "method": "GET",
        "path": "/api/workers/{id}/",
        "owner": "maya_submitter",
    },
    "pools": {
        "method": "GET",
        "path": "/api/pools/",
        "owner": "maya_submitter",
    },
    "pool_detail": {
        "method": "GET",
        "path": "/api/pools/{id}/",
        "owner": "maya_submitter",
    },
}


# These endpoints are deliberately not exposed by the Maya submitter. They are
# listed here so development audits can verify the worker/backend contract
# without accidentally granting task lifecycle ownership to the DCC plugin.
WORKER_OWNED_ENDPOINTS = {
    "/api/workers/ping/": "POST",
    "/api/tasks/dispatch/": "POST",
    "/api/tasks/{id}/start/": "POST",
    "/api/tasks/{id}/succeed/": "POST",
    "/api/tasks/{id}/fail/": "POST",
    "/api/tasks/{id}/skip/": "POST",
    "/api/tasks/{id}/checkpoint/": "POST",
}


REQUIRED_CONFIG_ENDPOINTS = (
    "connection_test",
    "jobs",
    "job_status",
    "job_update",
    "job_pause",
    "job_resume",
    "job_delete",
    "job_layers",
    "job_layer_detail",
    "job_layer_tasks",
    "job_layer_task_detail",
    "workers",
    "worker_detail",
    "pools",
    "pool_detail",
)


_REQUIRED_PLACEHOLDERS = {
    "job_status": ("job_id",),
    "job_update": ("job_id",),
    "job_pause": ("job_id",),
    "job_resume": ("job_id",),
    "job_delete": ("job_id",),
    "worker_detail": ("worker_id",),
    "pool_detail": ("pool_id",),
    "job_layers": ("job_id",),
    "job_layer_detail": ("job_id", "layer_id"),
    "job_layer_tasks": ("job_id", "layer_id"),
    "job_layer_task_detail": ("job_id", "layer_id", "task_id"),
}


def validate_endpoint_config(endpoints):
    if not isinstance(endpoints, dict):
        raise ApiContractError("API endpoints must be a JSON object.")

    missing = [
        name
        for name in REQUIRED_CONFIG_ENDPOINTS
        if not str(endpoints.get(name) or "").strip()
    ]
    if missing:
        raise ApiContractError(
            "Missing required API endpoint configuration: {}".format(
                ", ".join(sorted(missing))
            )
        )

    for name, placeholders in _REQUIRED_PLACEHOLDERS.items():
        path = str(endpoints.get(name) or "")
        if not path:
            continue
        for placeholder in placeholders:
            token = "{" + placeholder + "}"
            if token not in path:
                raise ApiContractError(
                    "Endpoint '{}' must include placeholder {}.".format(
                        name,
                        token,
                    )
                )

    return True


def contract_capabilities(config):
    config = config if isinstance(config, dict) else {}
    contract = config.get("contract") or {}

    return {
        "contract_version": str(
            contract.get("version") or API_CONTRACT_VERSION
        ),
        "job_create_returns_id": bool(
            contract.get("job_create_returns_id", False)
        ),
        "job_pool_targeting": bool(
            contract.get("job_pool_targeting", True)
        ),
        "job_dependencies": bool(
            contract.get("job_dependencies", True)
        ),
    }
