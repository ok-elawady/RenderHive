from __future__ import absolute_import

import re

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
    "job_layer_frames": {
        "method": "GET",
        "path": "/api/jobs/{job_pk}/layers/{layer_pk}/frames/",
        "owner": "maya_submitter",
    },
    "job_layer_frame_detail": {
        "method": "GET",
        "path": "/api/jobs/{job_pk}/layers/{layer_pk}/frames/{id}/",
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


WORKER_OWNED_ENDPOINTS = {
    "/api/workers/ping/",
    "/api/frames/dispatch/",
    "/api/frames/{id}/start/",
    "/api/frames/{id}/succeed/",
    "/api/frames/{id}/fail/",
    "/api/frames/{id}/skip/",
    "/api/frames/{id}/checkpoint/",
}


REQUIRED_CONFIG_ENDPOINTS = (
    "connection_test",
    "jobs",
    "job_status",
    "job_update",
    "job_pause",
    "job_resume",
    "job_delete",
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
    "job_layer_frames": ("job_id", "layer_id"),
    "job_layer_frame_detail": ("job_id", "layer_id", "frame_id"),
}


_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_extension_field(value, setting_name):
    value = str(value or "").strip()
    if value and not _FIELD_NAME.match(value):
        raise ApiContractError(
            "{} must be a valid JSON field name.".format(setting_name)
        )
    return value


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
        "layer_pool_ids_field": validate_extension_field(
            contract.get("layer_pool_ids_field", ""),
            "contract.layer_pool_ids_field",
        ),
        "job_start_suspended_field": validate_extension_field(
            contract.get("job_start_suspended_field", ""),
            "contract.job_start_suspended_field",
        ),
        "job_machine_limit_field": validate_extension_field(
            contract.get("job_machine_limit_field", ""),
            "contract.job_machine_limit_field",
        ),
        "job_dependencies_field": validate_extension_field(
            contract.get("job_dependencies_field", ""),
            "contract.job_dependencies_field",
        ),
    }
