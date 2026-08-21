"""Central filesystem paths for configuration, state, logs and support data."""

from __future__ import absolute_import

import os


def _root_from_environment(name, fallback):
    value = str(os.environ.get(name) or "").strip()
    if value:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(value)))
    return fallback


def local_appdata_root():
    fallback = os.path.join(os.path.expanduser("~"), ".renderhive")
    return _root_from_environment("LOCALAPPDATA", fallback)


def renderhive_root():
    base = local_appdata_root()
    if os.path.basename(base).lower() == "renderhive":
        return base
    return os.path.join(base, "RenderHive")


def houdini_data_root():
    return os.path.join(renderhive_root(), "Houdini")


def ensure_directory(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)
    return path


def logs_root():
    return ensure_directory(os.path.join(houdini_data_root(), "logs"))


def runtime_logs_dir():
    return ensure_directory(os.path.join(logs_root(), "runtime"))


def submission_logs_dir():
    return ensure_directory(os.path.join(logs_root(), "submissions"))


def reports_dir():
    return ensure_directory(os.path.join(houdini_data_root(), "reports"))


def support_bundles_dir():
    return ensure_directory(os.path.join(houdini_data_root(), "support"))


def state_database_path():
    return os.path.join(houdini_data_root(), "houdini_state.db")


def state_backup_path():
    return os.path.join(houdini_data_root(), "houdini_state.backup.db")


def user_settings_path():
    return os.path.join(houdini_data_root(), "settings.json")


def package_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def payload_root():
    return os.path.abspath(os.path.join(package_root(), "..", ".."))
