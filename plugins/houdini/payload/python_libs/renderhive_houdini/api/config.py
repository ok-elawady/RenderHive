from __future__ import absolute_import

import copy
import json
import os

try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

from renderhive_houdini.api.credentials import CredentialStorageError, load_token
from renderhive_houdini.api.endpoints import DEFAULT_ENDPOINTS, validate_endpoints
from renderhive_houdini.api.errors import ApiConfigurationError


DEFAULT_CONFIG = {
    "enabled": True,
    "base_url": "http://127.0.0.1:8000",
    "timeout_seconds": 15,
    "verify_ssl": True,
    "auth": {
        "type": "token",
        "token": "",
    },
    "endpoints": copy.deepcopy(DEFAULT_ENDPOINTS),
    "contract": {
        "layer_pool_ids_field": "",
        "job_start_suspended_field": "",
        "job_machine_limit_field": "",
    },
    "houdini": {
        "hython_executable": "hython",
        "frame_token": "{frame}",
        "layer_name": "beauty",
        "use_pool_as_tag": True,
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
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "enabled"):
        return True
    if text in ("0", "false", "no", "off", "disabled", ""):
        return False
    return bool(default)


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
    return value


def normalize_config(config):
    result = _deep_merge(DEFAULT_CONFIG, config or {})
    result["enabled"] = _as_bool(result.get("enabled"), True)
    result["base_url"] = _validate_base_url(result.get("base_url"))
    try:
        result["timeout_seconds"] = max(1, min(int(result.get("timeout_seconds", 15)), 300))
    except Exception:
        result["timeout_seconds"] = 15
    result["verify_ssl"] = _as_bool(result.get("verify_ssl"), True)
    auth = result.get("auth") if isinstance(result.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or "token").strip().lower()
    if auth_type not in ("token", "x-session-token", "none"):
        raise ApiConfigurationError("Unsupported API authentication type: {}".format(auth_type))
    auth["type"] = auth_type
    auth["token"] = str(auth.get("token") or "").strip()
    result["auth"] = auth
    validate_endpoints(result.get("endpoints"))
    return result


def _environment_overrides():
    result = {}
    url = str(os.environ.get("RENDERHIVE_API_URL") or "").strip()
    if url:
        result["base_url"] = url
    token = str(os.environ.get("RENDERHIVE_API_TOKEN") or "").strip()
    if token:
        result["auth"] = {
            "type": str(os.environ.get("RENDERHIVE_API_AUTH_TYPE") or "token").strip().lower(),
            "token": token,
        }
    if "RENDERHIVE_API_ENABLED" in os.environ:
        result["enabled"] = _as_bool(os.environ.get("RENDERHIVE_API_ENABLED"), True)
    return result


def config_source():
    if any(name in os.environ for name in ("RENDERHIVE_API_CONFIG", "RENDERHIVE_API_URL", "RENDERHIVE_API_TOKEN")):
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
        managed = _read_json(managed_path)
        if isinstance(managed.get("auth"), dict):
            managed = copy.deepcopy(managed)
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

    config = normalize_config(config)
    config["_config_source"] = config_source()
    config["_config_path"] = managed_path if managed_path and os.path.isfile(managed_path) else user_path
    return config
