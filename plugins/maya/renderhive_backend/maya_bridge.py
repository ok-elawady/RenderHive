from __future__ import absolute_import

import datetime
import json
import os

from .client import BackendClient
from .config import (
    get_config_path,
    load_config,
    save_config,
)
from .errors import BackendConfigurationError
from .payload import build_job_payload


_CLIENT = None
_CLIENT_CONFIG_SIGNATURE = None
_MAYA_API = None


def _config_signature(config):
    return json.dumps(config, sort_keys=True)


def _client(force_reload=False):
    global _CLIENT
    global _CLIENT_CONFIG_SIGNATURE

    config = load_config()
    signature = _config_signature(config)

    if (
        force_reload
        or _CLIENT is None
        or signature != _CLIENT_CONFIG_SIGNATURE
    ):
        _CLIENT = BackendClient(config)
        _CLIENT_CONFIG_SIGNATURE = signature

    return _CLIENT


def get_backend_config():
    return load_config()


def get_backend_config_path():
    return get_config_path()


def save_backend_config(updates):
    config = save_config(updates)
    _client(force_reload=True)
    return config


def backend_health_check():
    config = load_config()
    token = str(config.get("auth", {}).get("token") or "").strip()

    if config.get("auth", {}).get("type") == "token" and not token:
        raise BackendConfigurationError(
            "API token is empty. Paste the token in Tools > Backend Connection."
        )

    return _client(force_reload=True).test_connection()


def get_available_workers():
    # The supplied OpenAPI 0.1.0 document has Jobs, Layers and Frames only.
    # It does not expose an available-worker endpoint. Keep local Pools alive
    # without pretending that historical frame worker_name values are online.
    return []


def get_backend_pools():
    return []


def _submission_log_folder():
    if _MAYA_API is not None:
        getter = getattr(_MAYA_API, "get_original_package_root", None)
        if callable(getter):
            root = getter()
        else:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    folder = os.path.join(root, "logs", "backend_submissions")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def _write_submission_log(local_task, api_payload, response):
    task_uid = str(
        local_task.get("task_uid")
        or local_task.get("task_id")
        or "maya_job"
    )
    safe_uid = "".join(
        character if character.isalnum() or character in ("_", "-") else "_"
        for character in task_uid
    )
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(
        _submission_log_folder(),
        "{}_{}.json".format(safe_uid, stamp)
    )

    payload = {
        "submitted_at": datetime.datetime.utcnow().replace(
            microsecond=0
        ).isoformat() + "Z",
        "local_task": local_task,
        "api_request": api_payload,
        "api_response": response,
    }

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, sort_keys=False)

    return path


def build_backend_job_payload(task):
    return build_job_payload(task, load_config())


def submit_job_to_backend(task):
    config = load_config()

    if not config.get("enabled", False):
        raise BackendConfigurationError(
            "Backend submission is disabled in RenderHive settings."
        )

    token = str(config.get("auth", {}).get("token") or "").strip()
    if config.get("auth", {}).get("type") == "token" and not token:
        raise BackendConfigurationError(
            "API token is empty. Paste it in Tools > Backend Connection."
        )

    api_payload = build_job_payload(task, config)
    response = _client().submit_job(api_payload)

    job_id = (
        response.get("id")
        or response.get("job_id")
        or response.get("uid")
    ) if isinstance(response, dict) else None

    if job_id and task.get("start_suspended"):
        paused = _client().pause_job(job_id)
        if isinstance(response, dict):
            response = dict(response)
            response["pause_response"] = paused
            response["is_paused"] = True

    log_path = _write_submission_log(task, api_payload, response)
    if isinstance(response, dict):
        response = dict(response)
        response["_renderhive_log_path"] = log_path
        response["_renderhive_api_payload"] = api_payload

    return response


def get_backend_job_status(job_id):
    return _client().get_job_status(job_id)


def pause_backend_job(job_id):
    return _client().pause_job(job_id)


def resume_backend_job(job_id):
    return _client().resume_job(job_id)


def delete_backend_job(job_id):
    return _client().delete_job(job_id)


def install(maya_api):
    global _MAYA_API
    _MAYA_API = maya_api

    maya_api.get_backend_config = get_backend_config
    maya_api.get_backend_config_path = get_backend_config_path
    maya_api.save_backend_config = save_backend_config
    maya_api.backend_health_check = backend_health_check
    maya_api.get_available_workers = get_available_workers
    maya_api.list_available_workers = get_available_workers
    maya_api.get_backend_pools = get_backend_pools
    maya_api.build_backend_job_payload = build_backend_job_payload
    maya_api.submit_job_to_backend = submit_job_to_backend
    maya_api.get_backend_job_status = get_backend_job_status
    maya_api.pause_backend_job = pause_backend_job
    maya_api.resume_backend_job = resume_backend_job
    maya_api.delete_backend_job = delete_backend_job

    return maya_api
