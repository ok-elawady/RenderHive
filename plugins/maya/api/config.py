from __future__ import absolute_import

import copy
import datetime
import json
import os
import shutil

try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

from .contract import contract_capabilities, validate_endpoint_config
from .credentials import (
    CredentialStorageError,
    delete_token,
    get_credential_path,
    load_token,
    save_token,
    storage_mode,
)
from .errors import ApiConfigurationError
from .version import API_CONTRACT_VERSION
from core.runtime_log import get_logger


LOGGER = get_logger("config")
CONFIG_SCHEMA_VERSION = 4

DEFAULT_CONFIG = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "enabled": True,
    "base_url": "http://127.0.0.1:8000",
    "timeout_seconds": 15,
    "verify_ssl": True,
    "network": {
        "get_retry_attempts": 2,
        "retry_backoff_seconds": 0.4,
        "max_retry_delay_seconds": 5.0,
        "max_response_bytes": 10 * 1024 * 1024,
        "allow_cross_origin_pagination": False,
    },
    "auth": {
        "type": "token",
        "token": "",
        "token_storage": "external",
    },
    "endpoints": {
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
    },
    "contract": {
        "version": API_CONTRACT_VERSION,
        "job_create_returns_id": False,
        "job_pool_targeting": True,
        "job_dependencies": True,
    },
    "maya": {
        "render_executable": "Render.exe",
        "frame_token": "{frame}",
        "layer_name": "beauty",
        "submission_log_retention": 200,
    },
}


def _package_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _local_config_root():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return os.path.join(root, "RenderHive")
    return os.path.join(os.path.expanduser("~"), ".renderhive")


def _program_data_root():
    root = str(os.environ.get("PROGRAMDATA") or "").strip()
    if not root:
        return ""
    return os.path.join(root, "RenderHive", "config")


def get_machine_config_path():
    explicit = str(os.environ.get("RENDERHIVE_API_CONFIG") or "").strip()
    if explicit:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(explicit)))

    root = _program_data_root()
    if not root:
        return ""
    return os.path.join(root, "api.json")


def get_managed_config_path():
    machine_path = get_machine_config_path()
    if machine_path and os.path.isfile(machine_path):
        return machine_path
    return get_config_path()


def admin_mode_enabled():
    return _as_bool(os.environ.get("RENDERHIVE_ADMIN_MODE"), False)


def _environment_overrides():
    overrides = {}

    base_url = str(os.environ.get("RENDERHIVE_API_URL") or "").strip()
    if base_url:
        overrides["base_url"] = base_url

    if "RENDERHIVE_API_ENABLED" in os.environ:
        overrides["enabled"] = _as_bool(
            os.environ.get("RENDERHIVE_API_ENABLED"),
            True,
        )

    if "RENDERHIVE_API_VERIFY_SSL" in os.environ:
        overrides["verify_ssl"] = _as_bool(
            os.environ.get("RENDERHIVE_API_VERIFY_SSL"),
            True,
        )

    token = str(os.environ.get("RENDERHIVE_API_TOKEN") or "").strip()
    if token:
        overrides["auth"] = {
            "type": str(
                os.environ.get("RENDERHIVE_API_AUTH_TYPE") or "token"
            ).strip().lower(),
            "token": token,
            "token_storage": "environment",
        }

    return overrides


def _managed_override():
    path = get_machine_config_path()
    if not path or not os.path.isfile(path):
        return {}, ""

    value = _read_existing(path)
    value = copy.deepcopy(value)

    # Machine configuration never owns the user credential. Tokens remain in
    # DPAPI or an environment variable so the shared JSON file stays safe.
    auth = value.get("auth")
    if isinstance(auth, dict):
        auth.pop("token", None)

    return value, path


def get_config_source():
    if any(
        name in os.environ
        for name in (
            "RENDERHIVE_API_CONFIG",
            "RENDERHIVE_API_URL",
            "RENDERHIVE_API_TOKEN",
            "RENDERHIVE_API_ENABLED",
        )
    ):
        return "Environment"

    machine_path = get_machine_config_path()
    if machine_path and os.path.isfile(machine_path):
        return "Managed"

    return "User"


def get_config_path():
    return os.path.join(_local_config_root(), "api_config.json")


def get_config_backup_path():
    return get_config_path() + ".bak"




def get_credential_info():
    return {"path": get_credential_path(), "mode": storage_mode()}


def _legacy_config_paths():
    return [
        os.path.join(_local_config_root(), "backend_config.json"),
        os.path.join(_package_root(), "config", "backend_config.json"),
    ]


def _deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "enabled"):
        return True
    if text in ("0", "false", "no", "off", "disabled", ""):
        return False
    return bool(default)


def _bounded_int(value, default, minimum, maximum):
    try:
        value = int(value)
    except Exception:
        value = int(default)
    return max(int(minimum), min(int(value), int(maximum)))


def _bounded_float(value, default, minimum, maximum):
    try:
        value = float(value)
    except Exception:
        value = float(default)
    return max(float(minimum), min(float(value), float(maximum)))


def _validate_base_url(value):
    base_url = str(value or "").strip().rstrip("/")
    if not base_url:
        raise ApiConfigurationError("API base URL is empty.")

    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ApiConfigurationError(
            "API URL must be a valid http:// or https:// address."
        )
    if parsed.username or parsed.password:
        raise ApiConfigurationError(
            "Do not place credentials inside the API URL. Use token authentication."
        )
    if parsed.fragment:
        raise ApiConfigurationError("API URL cannot contain a fragment.")
    return base_url


def normalize_config(config):
    result = _deep_merge(DEFAULT_CONFIG, config or {})
    result["schema_version"] = CONFIG_SCHEMA_VERSION
    result["enabled"] = _as_bool(result.get("enabled"), False)
    result["base_url"] = _validate_base_url(result.get("base_url"))
    result["timeout_seconds"] = _bounded_int(
        result.get("timeout_seconds", 15), 15, 1, 300
    )
    result["verify_ssl"] = _as_bool(result.get("verify_ssl"), True)

    network = result.get("network")
    if not isinstance(network, dict):
        network = {}
    network = _deep_merge(DEFAULT_CONFIG["network"], network)
    network["get_retry_attempts"] = _bounded_int(
        network.get("get_retry_attempts"), 2, 0, 6
    )
    network["retry_backoff_seconds"] = _bounded_float(
        network.get("retry_backoff_seconds"), 0.4, 0.1, 10.0
    )
    network["max_retry_delay_seconds"] = _bounded_float(
        network.get("max_retry_delay_seconds"), 5.0, 0.1, 60.0
    )
    network["max_response_bytes"] = _bounded_int(
        network.get("max_response_bytes"), 10 * 1024 * 1024, 1024, 100 * 1024 * 1024
    )
    network["allow_cross_origin_pagination"] = _as_bool(
        network.get("allow_cross_origin_pagination"), False
    )
    result["network"] = network

    auth = result.get("auth") if isinstance(result.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or "token").strip().lower()
    if auth_type not in ("token", "x-session-token", "none"):
        raise ApiConfigurationError(
            "Unsupported authentication type: {}".format(auth_type)
        )
    auth["type"] = auth_type
    auth["token"] = str(auth.get("token") or "").strip()
    auth["token_storage"] = str(auth.get("token_storage") or "external").strip()
    result["auth"] = auth

    if not isinstance(result.get("endpoints"), dict):
        result["endpoints"] = copy.deepcopy(DEFAULT_CONFIG["endpoints"])
    result["endpoints"].pop("worker_ping", None)
    result["endpoints"].pop("frame_dispatch", None)
    # Contract 0.2.0 renamed legacy frame resources to task resources.
    result["endpoints"].pop("job_layer_frames", None)
    result["endpoints"].pop("job_layer_frame_detail", None)
    validate_endpoint_config(result["endpoints"])

    if not isinstance(result.get("contract"), dict):
        result["contract"] = copy.deepcopy(DEFAULT_CONFIG["contract"])
    result["contract"] = _deep_merge(
        DEFAULT_CONFIG["contract"],
        result["contract"],
    )
    # This plugin build is pinned to RenderHive API 0.2.0. Do not let stale
    # 0.1.x user configuration silently disable or remap fields that are now
    # part of the official backend contract.
    result["contract"].pop("layer_pool_ids_field", None)
    result["contract"].pop("job_dependencies_field", None)
    result["contract"].pop("job_start_suspended_field", None)
    result["contract"].pop("job_machine_limit_field", None)
    result["contract"]["version"] = API_CONTRACT_VERSION
    result["contract"]["job_create_returns_id"] = False
    result["contract"]["job_pool_targeting"] = True
    result["contract"]["job_dependencies"] = True
    contract_capabilities(result)

    if not isinstance(result.get("maya"), dict):
        result["maya"] = copy.deepcopy(DEFAULT_CONFIG["maya"])
    result["maya"] = _deep_merge(DEFAULT_CONFIG["maya"], result["maya"])
    result["maya"]["submission_log_retention"] = _bounded_int(
        result["maya"].get("submission_log_retention"), 200, 10, 5000
    )
    # Remove the pre-0.2.0 compatibility switch. Pool targeting is a native
    # JobCreate field now; carrying this stale key forward can make a migrated
    # user config behave differently from a clean install.
    result["maya"].pop("use_pool_as_tag", None)
    return result


def _read_existing(path):
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except Exception as error:
        raise ApiConfigurationError("Could not read API config: {}".format(error))
    if not isinstance(value, dict):
        raise ApiConfigurationError("API config must be a JSON object.")
    return value


def _corrupt_backup_path(path):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return "{}.corrupt_{}".format(path, stamp)


def _recover_config(path, error):
    backup = ""
    try:
        if os.path.isfile(path):
            backup = _corrupt_backup_path(path)
            shutil.copy2(path, backup)
    except Exception:
        backup = ""
    LOGGER.error("Recovering invalid API config: %s; backup=%s", error, backup)
    config = normalize_config({})
    _write_config_file(config, preserve_backup=False)
    return config


def _write_config_file(config, preserve_backup=True):
    path = get_config_path()
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)

    disk_config = copy.deepcopy(normalize_config(config))
    auth = disk_config.setdefault("auth", {})
    auth["token"] = ""
    auth["token_storage"] = storage_mode()

    if preserve_backup and os.path.isfile(path):
        try:
            shutil.copy2(path, get_config_backup_path())
        except Exception as error:
            LOGGER.warning("Could not update API config backup: %s", error)

    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(disk_config, handle, indent=4, sort_keys=False)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except Exception:
                pass
        os.replace(temp_path, path)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
    except Exception as error:
        try:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise ApiConfigurationError("Could not save API config: {}".format(error))
    return path


def _inject_stored_token(config):
    result = copy.deepcopy(config)
    auth = result.setdefault("auth", {})
    try:
        stored_token = load_token()
    except CredentialStorageError as error:
        raise ApiConfigurationError(str(error))
    if stored_token:
        auth["token"] = stored_token
    auth["token_storage"] = storage_mode()
    return result


def _migrate_plaintext_token(config):
    result = copy.deepcopy(config)
    auth = result.setdefault("auth", {})
    plaintext = str(auth.get("token") or "").strip()
    if not plaintext:
        return result, False
    try:
        save_token(plaintext)
    except CredentialStorageError as error:
        raise ApiConfigurationError(str(error))
    auth["token"] = ""
    auth["token_storage"] = storage_mode()
    return result, True


def load_config():
    path = get_config_path()

    if not os.path.isfile(path):
        migrated_config = None
        for legacy_path in _legacy_config_paths():
            if os.path.isfile(legacy_path):
                migrated_config = save_config(_read_existing(legacy_path))
                break
        if migrated_config is None:
            migrated_config = save_config({})
        local_config = migrated_config
    else:
        try:
            raw = _read_existing(path)
            raw, migrated = _migrate_plaintext_token(raw)
            local_config = normalize_config(raw)
            if migrated or raw.get("schema_version") != CONFIG_SCHEMA_VERSION:
                _write_config_file(local_config)
        except ApiConfigurationError as error:
            local_config = _recover_config(path, error)

        local_config = _inject_stored_token(local_config)

    try:
        managed, managed_path = _managed_override()
        effective = normalize_config(_deep_merge(local_config, managed))
    except ApiConfigurationError as error:
        LOGGER.error("Managed API config is invalid: %s", error)
        effective = normalize_config(local_config)
        managed_path = ""

    effective = normalize_config(
        _deep_merge(effective, _environment_overrides())
    )

    # Reapply the protected credential after managed config merging. A machine
    # config is intentionally unable to replace or clear a user's DPAPI token.
    env_token = str(os.environ.get("RENDERHIVE_API_TOKEN") or "").strip()
    if env_token:
        effective.setdefault("auth", {})["token"] = env_token
        effective["auth"]["token_storage"] = "environment"
    else:
        try:
            stored_token = load_token()
        except CredentialStorageError as error:
            raise ApiConfigurationError(str(error))
        if stored_token:
            effective.setdefault("auth", {})["token"] = stored_token
            effective["auth"]["token_storage"] = storage_mode()

    effective["_config_source"] = get_config_source()
    effective["_config_path"] = managed_path or path
    return effective


def save_config(updates):
    path = get_config_path()
    raw_current = _read_existing(path) if os.path.isfile(path) else {}
    current = normalize_config(raw_current)
    try:
        stored_token = load_token()
    except CredentialStorageError as error:
        raise ApiConfigurationError(str(error))
    current.setdefault("auth", {})["token"] = stored_token

    updates = updates or {}
    config = normalize_config(_deep_merge(current, updates))
    explicit_auth = updates.get("auth") if isinstance(updates, dict) else None
    token_was_supplied = isinstance(explicit_auth, dict) and "token" in explicit_auth

    if token_was_supplied:
        token = str(config.get("auth", {}).get("token") or "").strip()
        try:
            if token:
                save_token(token)
            else:
                delete_token()
        except CredentialStorageError as error:
            raise ApiConfigurationError(str(error))
    elif stored_token:
        config.setdefault("auth", {})["token"] = stored_token

    config.setdefault("auth", {})["token_storage"] = storage_mode()
    _write_config_file(config)
    return config
