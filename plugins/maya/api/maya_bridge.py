from __future__ import absolute_import

import datetime
import hashlib
import json
import os

from .client import RenderHiveApiClient
from .config import (
    admin_mode_enabled,
    get_config_source,
    get_credential_info,
    get_managed_config_path,
    load_config,
    save_config,
)
from .contract import contract_capabilities
from .errors import (
    ApiConfigurationError,
)
from .payload import build_job_request
from core.diagnostics import create_support_bundle, production_health_report
from core.runtime_log import get_logger, runtime_log_folder
from api.version import PLUGIN_VERSION


_CLIENT = None
_CLIENT_CONFIG_SIGNATURE = None
_MAYA_API = None
LOGGER = get_logger("maya_bridge")


def _config_signature(config):
    signature_config = json.loads(
        json.dumps(config)
    )
    # Token changes must invalidate the cached client, but never serialize the
    # secret into diagnostics. A boolean marker is enough for cache identity
    # together with the remaining auth settings.
    auth = signature_config.setdefault("auth", {})
    token = str(auth.get("token") or "")
    auth["token"] = (
        hashlib.sha256(token.encode("utf-8")).hexdigest()
        if token
        else ""
    )
    return json.dumps(
        signature_config,
        sort_keys=True,
    )


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
        _CLIENT = RenderHiveApiClient(config)
        _CLIENT_CONFIG_SIGNATURE = signature

    return _CLIENT


def get_api_config():
    return load_config()


def get_api_config_path():
    return get_managed_config_path()


def get_api_config_source():
    return get_config_source()


def api_admin_mode_enabled():
    return admin_mode_enabled()


def get_api_credential_info():
    return get_credential_info()


def get_api_contract_capabilities():
    return contract_capabilities(load_config())


def save_api_config(updates):
    config = save_config(updates)
    _client(force_reload=True)
    return config


def _validate_auth_config(config):
    auth = config.get("auth", {})
    auth_type = str(auth.get("type") or "token").lower()
    token = str(auth.get("token") or "").strip()

    if auth_type in ("token", "x-session-token") and not token:
        raise ApiConfigurationError(
            "Backend credentials are not configured. Contact the RenderHive administrator."
        )


def test_api_connection():
    config = load_config()
    _validate_auth_config(config)
    return _client(force_reload=True).test_connection()


def get_available_workers():
    config = load_config()

    if not config.get("enabled", False):
        return []

    _validate_auth_config(config)
    return _client().list_workers()


def get_api_pools():
    config = load_config()
    if not config.get("enabled", False):
        return []

    _validate_auth_config(config)
    return _client().list_pools()


def get_worker_targeting_snapshot():
    config = load_config()
    if not config.get("enabled", False):
        return {"workers": [], "pools": []}

    _validate_auth_config(config)
    client = _client()
    return {
        "workers": client.list_workers(),
        "pools": client.list_pools(),
    }


def get_api_jobs():
    config = load_config()
    if not config.get("enabled", False):
        return []
    _validate_auth_config(config)
    return _client().list_all_jobs()


def get_api_worker(worker_id):
    return _client().get_worker(worker_id)


def get_api_pool(pool_id):
    return _client().get_pool(pool_id)


def _local_data_root():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return os.path.join(root, "RenderHive")
    return os.path.join(os.path.expanduser("~"), ".renderhive")


def _submission_log_folder():
    folder = os.path.join(
        _local_data_root(),
        "logs",
        "api_submissions",
    )

    if not os.path.isdir(folder):
        os.makedirs(folder)

    return folder


def _prune_submission_logs(folder, retention):
    try:
        retention = max(10, int(retention))
    except Exception:
        retention = 200

    try:
        files = []
        for filename in os.listdir(folder):
            if not filename.lower().endswith(".json"):
                continue
            path = os.path.join(folder, filename)
            if os.path.isfile(path):
                files.append((os.path.getmtime(path), path))

        files.sort(reverse=True)
        for _, path in files[retention:]:
            try:
                os.remove(path)
            except Exception:
                pass
    except Exception:
        pass


def _safe_json_value(value):
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _sanitize_log_value(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in ("token", "authorization", "x-session-token", "password", "secret"):
                result[key] = "***REDACTED***" if item else ""
            else:
                result[key] = _sanitize_log_value(item)
        return result
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_log_value(item) for item in value]
    return value


def _write_submission_log(
    local_task,
    api_request,
    response,
    error=None,
):
    task_uid = str(
        local_task.get("task_uid")
        or local_task.get("task_id")
        or "maya_job"
    )

    safe_uid = "".join(
        character
        if character.isalnum()
        or character in ("_", "-")
        else "_"
        for character in task_uid
    )

    stamp = datetime.datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    folder = _submission_log_folder()
    path = os.path.join(
        folder,
        "{}_{}.json".format(safe_uid, stamp),
    )

    payload = {
        "submitted_at": datetime.datetime.now(datetime.timezone.utc).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z"),
        "plugin_version": PLUGIN_VERSION,
        "success": error is None,
        "local_task": _sanitize_log_value(local_task),
        "api_request": _sanitize_log_value(api_request),
        "api_response": _sanitize_log_value(response),
        "error": (
            {
                "type": error.__class__.__name__,
                "message": str(error),
                "status_code": getattr(error, "status_code", None),
                "request_id": getattr(error, "request_id", ""),
            }
            if error is not None
            else None
        ),
    }

    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=4,
            sort_keys=False,
            default=_safe_json_value,
        )
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except Exception:
            pass

    os.replace(temp_path, path)

    config = load_config()
    retention = config.get("maya", {}).get(
        "submission_log_retention",
        200,
    )
    _prune_submission_logs(folder, retention)
    return path


def get_submission_log_folder():
    return _submission_log_folder()


def get_runtime_log_folder():
    return runtime_log_folder()


def create_diagnostics_bundle():
    return create_support_bundle()


def get_production_health_report():
    return production_health_report()


def build_api_job_request(task):
    return build_job_request(task, load_config())


def submit_job_to_api(task):
    config = load_config()

    if not config.get("enabled", False):
        raise ApiConfigurationError(
            "RenderHive API submission is disabled."
        )

    _validate_auth_config(config)
    api_request = build_job_request(task, config)
    response = None

    try:
        response = _client().submit_job(api_request)

        job_id = (
            response.get("id")
            or response.get("job_id")
            or response.get("uid")
        ) if isinstance(response, dict) else None

        log_path = _write_submission_log(
            task,
            api_request,
            response,
        )

        if isinstance(response, dict):
            response = dict(response)
            response["_renderhive_log_path"] = log_path
            response["_renderhive_api_request"] = api_request

        return response

    except Exception as error:
        try:
            log_path = _write_submission_log(
                task,
                api_request,
                response,
                error=error,
            )
            setattr(error, "renderhive_log_path", log_path)
        except Exception:
            pass
        raise


def get_api_job_status(job_id):
    return _client().get_job_status(job_id)


def update_api_job(
    job_id,
    visible_name=None,
    priority=None,
    max_tasks_per_worker=None,
):
    return _client().update_job(
        job_id,
        visible_name=visible_name,
        priority=priority,
        max_tasks_per_worker=max_tasks_per_worker,
    )


def pause_api_job(job_id):
    return _client().pause_job(job_id)


def resume_api_job(job_id):
    return _client().resume_job(job_id)


def delete_api_job(job_id):
    return _client().delete_job(job_id)


def get_api_job_layers(job_id):
    return _client().list_job_layers(job_id)


def get_api_job_layer(job_id, layer_id):
    return _client().get_job_layer(job_id, layer_id)


def get_api_layer_tasks(job_id, layer_id):
    return _client().list_layer_tasks(job_id, layer_id)


def get_api_layer_task(job_id, layer_id, task_id):
    return _client().get_layer_task(job_id, layer_id, task_id)






def install(maya_api):
    global _MAYA_API
    _MAYA_API = maya_api

    maya_api.get_api_config = get_api_config
    maya_api.get_api_config_path = get_api_config_path
    maya_api.get_api_config_source = get_api_config_source
    maya_api.api_admin_mode_enabled = api_admin_mode_enabled
    maya_api.get_api_credential_info = get_api_credential_info
    maya_api.get_api_contract_capabilities = get_api_contract_capabilities
    maya_api.save_api_config = save_api_config
    maya_api.test_api_connection = test_api_connection
    maya_api.get_available_workers = get_available_workers
    maya_api.list_available_workers = get_available_workers
    maya_api.get_api_pools = get_api_pools
    maya_api.get_worker_targeting_snapshot = get_worker_targeting_snapshot
    maya_api.get_api_jobs = get_api_jobs
    maya_api.get_api_worker = get_api_worker
    maya_api.get_api_pool = get_api_pool
    maya_api.build_api_job_request = build_api_job_request
    maya_api.submit_job_to_api = submit_job_to_api
    maya_api.get_api_job_status = get_api_job_status
    maya_api.update_api_job = update_api_job
    maya_api.pause_api_job = pause_api_job
    maya_api.resume_api_job = resume_api_job
    maya_api.delete_api_job = delete_api_job
    maya_api.get_api_job_layers = get_api_job_layers
    maya_api.get_api_job_layer = get_api_job_layer
    maya_api.get_api_layer_tasks = get_api_layer_tasks
    maya_api.get_api_layer_task = get_api_layer_task
    maya_api.get_submission_log_folder = get_submission_log_folder
    maya_api.get_runtime_log_folder = get_runtime_log_folder
    maya_api.create_diagnostics_bundle = create_diagnostics_bundle
    maya_api.get_production_health_report = get_production_health_report

    # Pool creation and membership remain backend/admin responsibilities. The
    # Maya submitter intentionally exposes read-only pool and worker APIs only.
    return maya_api
