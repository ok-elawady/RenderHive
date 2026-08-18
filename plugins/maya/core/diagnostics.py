from __future__ import absolute_import

import datetime
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import zipfile

from api.config import get_config_path, get_credential_info, load_config
from api.version import API_CONTRACT_VERSION, PLUGIN_VERSION
from core.runtime_log import local_data_root, runtime_log_folder, redact_text, get_logger
from core.state_store import StateStore


LOGGER = get_logger("diagnostics")


def _redact(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in ("token", "authorization", "x-session-token", "password", "secret"):
                result[key] = "***REDACTED***" if item else ""
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list): return [_redact(item) for item in value]
    if isinstance(value, tuple): return [_redact(item) for item in value]
    if isinstance(value, str): return redact_text(value)
    return value


def _maya_info():
    result = {"available": False}
    try:
        import maya.cmds as cmds
        result.update({
            "available": True,
            "version": str(cmds.about(version=True)),
            "api_version": str(cmds.about(apiVersion=True)),
            "batch": bool(cmds.about(batch=True)),
            "scene_saved": bool(cmds.file(query=True, sceneName=True)),
        })
    except Exception as error:
        result["error"] = str(error)
    return result


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk: break
            digest.update(chunk)
    return digest.hexdigest()


def production_health_report():
    checks = []
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    required = [
        "renderhive_maya_submitter.py",
        os.path.join("api", "client.py"),
        os.path.join("api", "payload.py"),
        os.path.join("ui", "qt_submitter_window.py"),
        os.path.join("validation", "validator.py"),
    ]
    missing = [item for item in required if not os.path.isfile(os.path.join(package_root, item))]
    checks.append({"name": "package_files", "ok": not missing, "detail": missing or "ok"})

    try:
        config = load_config()
        checks.append({"name": "api_config", "ok": True, "detail": {"enabled": config.get("enabled"), "base_url": config.get("base_url"), "verify_ssl": config.get("verify_ssl")}})
    except Exception as error:
        config = {}
        checks.append({"name": "api_config", "ok": False, "detail": str(error)})

    try:
        state = StateStore()
        state_report = state.health_report()
        checks.append({"name": "state_database", "ok": state_report.get("quick_check") == "ok", "detail": state_report})
    except Exception as error:
        checks.append({"name": "state_database", "ok": False, "detail": str(error)})

    credential = get_credential_info()
    checks.append({"name": "credential_storage", "ok": bool(credential.get("mode")), "detail": {"mode": credential.get("mode"), "file_exists": os.path.isfile(credential.get("path", ""))}})
    checks.append({"name": "maya_runtime", "ok": True, "detail": _maya_info()})
    return {
        "plugin_version": PLUGIN_VERSION,
        "api_contract_version": API_CONTRACT_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ok": all(item.get("ok") for item in checks),
        "checks": checks,
    }


def _copy_recent_files(source, destination, limit=10):
    if not os.path.isdir(source): return []
    files = [os.path.join(source, name) for name in os.listdir(source) if os.path.isfile(os.path.join(source, name))]
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    copied = []
    if not os.path.isdir(destination): os.makedirs(destination)
    for path in files[:int(limit)]:
        target = os.path.join(destination, os.path.basename(path))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as src:
                data = redact_text(src.read())
            with open(target, "w", encoding="utf-8") as dst: dst.write(data)
            copied.append(target)
        except Exception:
            pass
    return copied


def create_support_bundle(output_dir=None):
    root = local_data_root()
    output_dir = output_dir or os.path.join(root, "diagnostics")
    if not os.path.isdir(output_dir): os.makedirs(output_dir)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    final_path = os.path.join(output_dir, "RenderHive_Maya_Support_{}_v{}.zip".format(stamp, PLUGIN_VERSION.replace('.', '_')))
    temp_root = tempfile.mkdtemp(prefix="renderhive_diag_")
    try:
        report = production_health_report()
        config = _redact(load_config())
        credential = get_credential_info()
        manifest = {
            "plugin_version": PLUGIN_VERSION,
            "api_contract_version": API_CONTRACT_VERSION,
            "generated_at": report.get("generated_at"),
            "platform": platform.platform(),
            "python": sys.version,
            "maya": _maya_info(),
            "config_path": get_config_path(),
            "credential": {"mode": credential.get("mode"), "file_exists": os.path.isfile(credential.get("path", ""))},
            "health": report,
        }
        for name, value in (("manifest.json", manifest), ("api_config_redacted.json", config)):
            with open(os.path.join(temp_root, name), "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=4, default=str)

        _copy_recent_files(runtime_log_folder(), os.path.join(temp_root, "runtime_logs"), 8)
        _copy_recent_files(os.path.join(root, "logs", "api_submissions"), os.path.join(temp_root, "submission_logs"), 5)

        package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        release_manifest = os.path.join(package_root, "release_manifest.json")
        if os.path.isfile(release_manifest): shutil.copy2(release_manifest, os.path.join(temp_root, "release_manifest.json"))

        with zipfile.ZipFile(final_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for folder, _, files in os.walk(temp_root):
                for filename in files:
                    path = os.path.join(folder, filename)
                    archive.write(path, os.path.relpath(path, temp_root))
        LOGGER.info("Created support bundle: %s", final_path)
        return final_path
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
