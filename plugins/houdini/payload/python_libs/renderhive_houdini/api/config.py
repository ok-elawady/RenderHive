from __future__ import absolute_import

import copy
import json
import os

try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

from renderhive_houdini.api.contract import contract_capabilities, validate_endpoint_config
from renderhive_houdini.api.credentials import CredentialStorageError, load_token
from renderhive_houdini.api.endpoints import DEFAULT_ENDPOINTS
from renderhive_houdini.api.errors import ApiConfigurationError
from renderhive_houdini.api.version import API_CONTRACT_VERSION
from renderhive_houdini.core.logging_utils import get_logger

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
    "endpoints": copy.deepcopy(DEFAULT_ENDPOINTS),
    "contract": {
        "version": API_CONTRACT_VERSION,
        "job_create_returns_id": False,
        "job_pool_targeting": True,
        "job_dependencies": True,
    },
    "houdini": {
        "hython_executable": "hython",
        "husk_executable": "husk",
        "frame_token": "{frame}",
        "default_layer_name": "beauty",
        "default_max_retries": 2,
        "default_timeout_seconds": None,
        "require_saved_scene": True,
        "submission_log_retention": 200,
    },
}


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


def _local_root():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return os.path.join(root, "RenderHive")
    return os.path.join(os.path.expanduser("~"), ".renderhive")


def user_config_path():
    return os.path.join(_local_root(), "api_config.json")


def managed_config_path():
    explicit = str(os.environ.get("RENDERHIVE_API_CONFIG") or "").strip()
    if explicit:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(explicit)))
    program_data = str(os.environ.get("PROGRAMDATA") or "").strip()
    if not program_data:
        return ""
    return os.path.join(program_data, "RenderHive", "config", "api.json")


def _read_json(path):
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as error:
        raise ApiConfigurationError("Could not read API config '{}': {}".format(path, error))
    if not isinstance(data, dict):
        raise ApiConfigurationError("API config must contain a JSON object: {}".format(path))
    return data


def _validate_base_url(value):
    value = str(value or "").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ApiConfigurationError("API URL must be a valid http:// or https:// address.")
    if parsed.username or parsed.password:
        raise ApiConfigurationError("Credentials are not allowed inside the API URL.")
    if parsed.fragment:
        raise ApiConfigurationError("API URL cannot contain a fragment.")
    return value


def normalize_config(config):
    raw = copy.deepcopy(config or {})

    # Migrate the pre-0.2 Houdini keys without letting them change current API
    # semantics. Pool targeting and dependencies are native JobCreate fields.
    legacy_retry = raw.pop("retry_get_count", None)
    legacy_max_bytes = raw.pop("max_response_bytes", None)
    if legacy_retry is not None or legacy_max_bytes is not None:
        raw.setdefault("network", {})
        if legacy_retry is not None:
            raw["network"].setdefault("get_retry_attempts", legacy_retry)
        if legacy_max_bytes is not None:
            raw["network"].setdefault("max_response_bytes", legacy_max_bytes)

    result = _deep_merge(DEFAULT_CONFIG, raw)
    result["schema_version"] = CONFIG_SCHEMA_VERSION
    result["enabled"] = _as_bool(result.get("enabled"), True)
    result["base_url"] = _validate_base_url(result.get("base_url"))
    result["timeout_seconds"] = _bounded_int(result.get("timeout_seconds"), 15, 1, 300)
    result["verify_ssl"] = _as_bool(result.get("verify_ssl"), True)

    network = _deep_merge(DEFAULT_CONFIG["network"], result.get("network") if isinstance(result.get("network"), dict) else {})
    network["get_retry_attempts"] = _bounded_int(network.get("get_retry_attempts"), 2, 0, 6)
    network["retry_backoff_seconds"] = _bounded_float(network.get("retry_backoff_seconds"), 0.4, 0.1, 10.0)
    network["max_retry_delay_seconds"] = _bounded_float(network.get("max_retry_delay_seconds"), 5.0, 0.1, 60.0)
    network["max_response_bytes"] = _bounded_int(network.get("max_response_bytes"), 10 * 1024 * 1024, 1024, 100 * 1024 * 1024)
    network["allow_cross_origin_pagination"] = _as_bool(network.get("allow_cross_origin_pagination"), False)
    result["network"] = network

    auth = result.get("auth") if isinstance(result.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or "token").strip().lower()
    if auth_type not in ("token", "x-session-token", "none"):
        raise ApiConfigurationError("Unsupported authentication type: {}".format(auth_type))
    auth["type"] = auth_type
    auth["token"] = str(auth.get("token") or "").strip()
    auth["token_storage"] = str(auth.get("token_storage") or "external").strip()
    result["auth"] = auth

    endpoints = result.get("endpoints") if isinstance(result.get("endpoints"), dict) else {}
    # Drop legacy/unowned routes and merge the official 0.2.0 submitter routes.
    for stale in ("worker_ping", "frame_dispatch", "job_layer_frames", "job_layer_frame_detail"):
        endpoints.pop(stale, None)
    endpoints = _deep_merge(DEFAULT_ENDPOINTS, endpoints)
    result["endpoints"] = endpoints
    validate_endpoint_config(endpoints)

    contract = result.get("contract") if isinstance(result.get("contract"), dict) else {}
    for stale in (
        "layer_pool_ids_field", "layer_included_pools_field", "layer_excluded_pools_field",
        "job_dependencies_field", "job_start_suspended_field", "job_machine_limit_field",
    ):
        contract.pop(stale, None)
    contract = _deep_merge(DEFAULT_CONFIG["contract"], contract)
    contract["version"] = API_CONTRACT_VERSION
    contract["job_create_returns_id"] = False
    contract["job_pool_targeting"] = True
    contract["job_dependencies"] = True
    result["contract"] = contract
    contract_capabilities(result)

    houdini = _deep_merge(DEFAULT_CONFIG["houdini"], result.get("houdini") if isinstance(result.get("houdini"), dict) else {})
    # Pre-0.2 pool-tag routing and fixed single layer names are no longer part
    # of the production contract. Each selected render source becomes a layer.
    houdini.pop("use_pool_as_tag", None)
    if "layer_name" in houdini and not houdini.get("default_layer_name"):
        houdini["default_layer_name"] = houdini.get("layer_name")
    houdini.pop("layer_name", None)
    houdini["submission_log_retention"] = _bounded_int(houdini.get("submission_log_retention"), 200, 10, 5000)
    result["houdini"] = houdini
    return result


def _environment_overrides():
    result = {}
    url = str(os.environ.get("RENDERHIVE_API_URL") or "").strip()
    if url:
        result["base_url"] = url
    if "RENDERHIVE_API_ENABLED" in os.environ:
        result["enabled"] = _as_bool(os.environ.get("RENDERHIVE_API_ENABLED"), True)
    if "RENDERHIVE_API_VERIFY_SSL" in os.environ:
        result["verify_ssl"] = _as_bool(os.environ.get("RENDERHIVE_API_VERIFY_SSL"), True)
    token = str(os.environ.get("RENDERHIVE_API_TOKEN") or "").strip()
    if token:
        result["auth"] = {
            "type": str(os.environ.get("RENDERHIVE_API_AUTH_TYPE") or "token").strip().lower(),
            "token": token,
            "token_storage": "environment",
        }
    return result


def config_source():
    if any(name in os.environ for name in ("RENDERHIVE_API_CONFIG", "RENDERHIVE_API_URL", "RENDERHIVE_API_TOKEN", "RENDERHIVE_API_ENABLED")):
        return "Environment"
    managed = managed_config_path()
    if managed and os.path.isfile(managed):
        return "Managed"
    if os.path.isfile(user_config_path()):
        return "User"
    return "Built-in Default"


def load_config():
    config = copy.deepcopy(DEFAULT_CONFIG)
    user_path = user_config_path()
    managed_path = managed_config_path()

    if os.path.isfile(user_path):
        config = _deep_merge(config, _read_json(user_path))
    if managed_path and os.path.isfile(managed_path):
        managed = copy.deepcopy(_read_json(managed_path))
        if isinstance(managed.get("auth"), dict):
            managed["auth"].pop("token", None)
        config = _deep_merge(config, managed)
    config = _deep_merge(config, _environment_overrides())

    env_token = str(os.environ.get("RENDERHIVE_API_TOKEN") or "").strip()
    if not env_token:
        try:
            stored = load_token()
        except CredentialStorageError as error:
            raise ApiConfigurationError(str(error))
        if stored:
            config.setdefault("auth", {})["token"] = stored
            config["auth"]["token_storage"] = "dpapi" if os.name == "nt" else "file"

    config = normalize_config(config)
    config["_config_source"] = config_source()
    config["_config_path"] = managed_path if managed_path and os.path.isfile(managed_path) else user_path
    return config
