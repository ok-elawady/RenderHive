"""Support-bundle creation with credential redaction."""

from __future__ import absolute_import

import datetime
import json
import os
import platform
import shutil
import tempfile
import zipfile

from renderhive_houdini.core.logging_utils import redact
from renderhive_houdini.core.paths import runtime_logs_dir, submission_logs_dir, support_bundles_dir, state_database_path
from renderhive_houdini.version import __version__


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(redact(data), handle, indent=2, sort_keys=True, default=str)


def _copy_recent_logs(source, destination, limit=5):
    if not os.path.isdir(source):
        return []
    files = [os.path.join(source, name) for name in os.listdir(source) if os.path.isfile(os.path.join(source, name))]
    files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    copied = []
    if not os.path.isdir(destination):
        os.makedirs(destination)
    for path in files[:limit]:
        target = os.path.join(destination, os.path.basename(path))
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def create_support_bundle(config=None, scene_context=None, validation_results=None, production_check=None, extra=None):
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output = os.path.join(support_bundles_dir(), "RenderHive_Houdini_Support_{}.zip".format(stamp))
    temp_root = tempfile.mkdtemp(prefix="renderhive_houdini_support_")
    try:
        _write_json(os.path.join(temp_root, "summary.json"), {
            "plugin_version": __version__,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "scene": getattr(scene_context, "__dict__", {}) if scene_context else {},
            "validation": [item.as_dict() if hasattr(item, "as_dict") else item for item in (validation_results or [])],
            "production_check": production_check or {},
            "extra": extra or {},
            "state_database_exists": os.path.isfile(state_database_path()),
        })
        _write_json(os.path.join(temp_root, "api_config_redacted.json"), config or {})
        _copy_recent_logs(runtime_logs_dir(), os.path.join(temp_root, "runtime_logs"), 6)
        _copy_recent_logs(submission_logs_dir(), os.path.join(temp_root, "submission_logs"), 6)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, _dirs, files in os.walk(temp_root):
                for name in files:
                    path = os.path.join(root, name)
                    archive.write(path, os.path.relpath(path, temp_root))
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return output
