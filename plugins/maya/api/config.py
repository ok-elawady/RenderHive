from __future__ import absolute_import

import copy
import json
import os

from .errors import ApiConfigurationError


DEFAULT_CONFIG = {
    "enabled": False,
    "base_url": "http://127.0.0.1:8000",
    "timeout_seconds": 15,
    "verify_ssl": True,
    "auth": {
        "type": "token",
        "token": ""
    },
    "endpoints": {
        "connection_test": "/api/jobs/?page=1",
        "jobs": "/api/jobs/",
        "job_status": "/api/jobs/{job_id}/",
        "job_pause": "/api/jobs/{job_id}/pause/",
        "job_resume": "/api/jobs/{job_id}/resume/",
        "job_delete": "/api/jobs/{job_id}/"
    },
    "maya": {
        "render_executable": "Render.exe",
        "frame_token": "{frame}",
        "layer_name": "beauty",
        "use_pool_as_tag": True
    }
}


def _package_root():
    return os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )


def _local_config_root():
    root = os.environ.get("LOCALAPPDATA")

    if root:
        return os.path.join(root, "RenderHive")

    return os.path.join(
        os.path.expanduser("~"),
        ".renderhive"
    )


def get_config_path():
    return os.path.join(
        _local_config_root(),
        "api_config.json"
    )


def get_template_path():
    return os.path.join(
        _package_root(),
        "config",
        "api_config.template.json"
    )


def _legacy_config_paths():
    return [
        os.path.join(
            _local_config_root(),
            "backend_config.json"
        ),
        os.path.join(
            _package_root(),
            "config",
            "backend_config.json"
        ),
    ]


def _deep_merge(base, override):
    result = copy.deepcopy(base)

    for key, value in (override or {}).items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = _deep_merge(
                result[key],
                value
            )
        else:
            result[key] = copy.deepcopy(value)

    return result


def normalize_config(config):
    result = _deep_merge(
        DEFAULT_CONFIG,
        config or {}
    )

    result["enabled"] = bool(
        result.get("enabled", False)
    )

    base_url = str(
        result.get("base_url") or ""
    ).strip().rstrip("/")

    if not base_url:
        raise ApiConfigurationError(
            "API base URL is empty."
        )

    if not (
        base_url.startswith("http://")
        or base_url.startswith("https://")
    ):
        raise ApiConfigurationError(
            "API URL must start with http:// or https://"
        )

    result["base_url"] = base_url

    try:
        timeout = int(
            result.get("timeout_seconds", 15)
        )
    except Exception:
        timeout = 15

    result["timeout_seconds"] = max(1, timeout)

    auth = result.get("auth")
    if not isinstance(auth, dict):
        auth = {}

    auth_type = str(
        auth.get("type") or "token"
    ).strip().lower()

    if auth_type not in (
        "token",
        "x-session-token",
        "none",
    ):
        raise ApiConfigurationError(
            "Unsupported authentication type: {}".format(
                auth_type
            )
        )

    auth["type"] = auth_type
    auth["token"] = str(
        auth.get("token") or ""
    ).strip()
    result["auth"] = auth

    if not isinstance(
        result.get("endpoints"),
        dict
    ):
        result["endpoints"] = copy.deepcopy(
            DEFAULT_CONFIG["endpoints"]
        )

    if not isinstance(
        result.get("maya"),
        dict
    ):
        result["maya"] = copy.deepcopy(
            DEFAULT_CONFIG["maya"]
        )

    return result


def _read_existing(path):
    if not os.path.isfile(path):
        return {}

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as handle:
            value = json.load(handle)
    except Exception as error:
        raise ApiConfigurationError(
            "Could not read API config: {}".format(
                error
            )
        )

    if not isinstance(value, dict):
        raise ApiConfigurationError(
            "API config must be a JSON object."
        )

    return value


def load_config():
    path = get_config_path()

    if not os.path.isfile(path):
        # Preserve settings and token from versions that used
        # backend_config.json, then migrate to api_config.json.
        for legacy_path in _legacy_config_paths():
            if os.path.isfile(legacy_path):
                return save_config(
                    _read_existing(legacy_path)
                )

        return save_config({})

    return normalize_config(
        _read_existing(path)
    )


def save_config(updates):
    path = get_config_path()
    current = copy.deepcopy(
        DEFAULT_CONFIG
    )

    if os.path.isfile(path):
        current = _deep_merge(
            current,
            _read_existing(path)
        )

    config = normalize_config(
        _deep_merge(
            current,
            updates or {}
        )
    )

    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)

    temp_path = path + ".tmp"

    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as handle:
        json.dump(
            config,
            handle,
            indent=4,
            sort_keys=False
        )

    if os.path.isfile(path):
        os.remove(path)

    os.rename(
        temp_path,
        path
    )

    return config
