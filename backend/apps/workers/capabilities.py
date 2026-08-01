"""Worker capability matching for multi-DCC task dispatch.

The module intentionally keeps compatibility data in the existing
``WorkerNode.system_info`` JSON and ``tags`` fields. No database migration is
required. New workers report structured capabilities, while legacy workers can
still be matched through tags and scene/command inference.
"""

from __future__ import annotations

import os
import re
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: Any) -> str:
    text = _text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    aliases = {
        "karma-xpu": "karma-xpu",
        "karma-cpu": "karma-cpu",
        "arnold-renderer": "arnold",
        "redshift-renderer": "redshift",
        "renderman-ris": "renderman",
    }
    return aliases.get(text, text)


def _version_tuple(value: Any) -> tuple[int, int, int]:
    parts = [int(part) for part in re.findall(r"\d+", _text(value))[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def versions_compatible(dcc: str, requested: str, available_versions: list[str]) -> bool:
    """Return whether an installed version can execute the requested task.

    Maya compatibility is matched by release year. Houdini compatibility is
    matched by major.minor, allowing a different production build.
    """

    requested = _text(requested)
    if not requested:
        return bool(available_versions)

    requested_tuple = _version_tuple(requested)
    for available in available_versions:
        available_tuple = _version_tuple(available)
        if available_tuple == requested_tuple:
            return True
        if dcc == "maya" and available_tuple[0] == requested_tuple[0]:
            return True
        if dcc == "houdini" and available_tuple[:2] == requested_tuple[:2]:
            return True
    return False


def _infer_dcc(scene_info: dict[str, Any], env: dict[str, Any], tags: list[str], command: str, scene_path: str) -> str:
    explicit = _text(scene_info.get("dcc") or env.get("RENDERHIVE_DCC")).lower()
    if explicit in {"maya", "houdini"}:
        return explicit

    lowered_tags = {_text(tag).lower() for tag in tags}
    if "dcc:houdini" in lowered_tags or "houdini" in lowered_tags:
        return "houdini"
    if "dcc:maya" in lowered_tags or "maya" in lowered_tags:
        return "maya"

    extension = os.path.splitext(_text(scene_path).lower())[1]
    if extension in {".hip", ".hiplc", ".hipnc"}:
        return "houdini"
    if extension in {".ma", ".mb"}:
        return "maya"

    haystack = f"{command} {scene_path}".lower()
    if any(token in haystack for token in ("hython", "husk", "hbatch", "renderhive_houdini")):
        return "houdini"
    if any(token in haystack for token in ("render.exe", "mayapy", "maya")):
        return "maya"
    return ""


def extract_layer_requirements(layer: Any) -> dict[str, Any]:
    """Extract normalized execution requirements from a Layer-like object."""

    scene_info = _as_dict(getattr(layer, "scene_info", None))
    env = _as_dict(getattr(layer, "env", None))
    execution = _as_dict(scene_info.get("execution"))
    tags = [_text(tag) for tag in _as_list(getattr(layer, "tags", None)) if _text(tag)]
    command = _text(getattr(layer, "command", ""))
    scene_path = _text(getattr(layer, "scene_path", ""))

    dcc = _infer_dcc(scene_info, env, tags, command, scene_path)
    version = _text(
        scene_info.get("dcc_version")
        or (scene_info.get("houdini_version") if dcc == "houdini" else scene_info.get("maya_version"))
        or env.get("RENDERHIVE_HOUDINI_VERSION")
        or env.get("RENDERHIVE_MAYA_VERSION")
    )
    execution_mode = _text(
        scene_info.get("execution_mode")
        or execution.get("mode")
        or execution.get("worker_mode")
    ).lower()
    renderer = _text(scene_info.get("renderer") or execution.get("renderer"))

    return {
        "dcc": dcc,
        "dcc_version": version,
        "execution_mode": execution_mode,
        "renderer": renderer,
        "scene_info": scene_info,
    }


def _worker_capabilities(worker: Any) -> tuple[dict[str, Any], set[str]]:
    system_info = _as_dict(getattr(worker, "system_info", None))
    capabilities = _as_dict(system_info.get("capabilities"))
    tags = {_text(tag).lower() for tag in _as_list(getattr(worker, "tags", None)) if _text(tag)}
    return capabilities, tags


def _available_versions(dcc: str, capabilities: dict[str, Any], tags: set[str]) -> list[str]:
    dcc_caps = _as_dict(capabilities.get(dcc))
    versions = [_text(value) for value in _as_list(dcc_caps.get("versions")) if _text(value)]
    if versions:
        return versions

    prefix = f"{dcc}:"
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        suffix = tag[len(prefix):]
        if re.match(r"^\d", suffix):
            versions.append(suffix)
    return sorted(set(versions))


def _dcc_available(dcc: str, capabilities: dict[str, Any], tags: set[str]) -> bool:
    dcc_caps = _as_dict(capabilities.get(dcc))
    if dcc_caps:
        if dcc_caps.get("available") is False:
            return False
        if dcc_caps.get("available") is True or _as_list(dcc_caps.get("versions")):
            return True
    return f"dcc:{dcc}" in tags or any(tag.startswith(f"{dcc}:") for tag in tags)


def _execution_mode_available(dcc: str, requested_mode: str, capabilities: dict[str, Any], tags: set[str]) -> bool:
    if dcc != "houdini" or not requested_mode:
        return True

    required = ""
    if "husk" in requested_mode:
        required = "husk"
    elif any(token in requested_mode for token in ("hython", "rop", "hbatch")):
        required = "hython"
    if not required:
        return True

    dcc_caps = _as_dict(capabilities.get("houdini"))
    modes = {_text(value).lower() for value in _as_list(dcc_caps.get("execution_modes")) if _text(value)}
    if modes:
        return required in modes
    return f"houdini:{required}" in tags


def _renderer_available(dcc: str, renderer: str, capabilities: dict[str, Any], tags: set[str]) -> bool:
    """Check renderer compatibility only when the worker advertises renderers.

    Worker 1.1.x does not yet enumerate renderer plugins. In that case the
    scheduler does not reject the task and the adapter remains the final safety
    check. Future workers can report ``capabilities.<dcc>.renderers`` or
    ``renderer:<name>`` tags for strict filtering.
    """

    requested = _slug(renderer)
    if not requested:
        return True

    dcc_caps = _as_dict(capabilities.get(dcc))
    advertised = {_slug(value) for value in _as_list(dcc_caps.get("renderers")) if _slug(value)}
    tagged = {
        _slug(tag.split(":", 1)[1])
        for tag in tags
        if tag.startswith("renderer:") and ":" in tag
    }
    tagged.update(
        _slug(tag.split(":", 2)[2])
        for tag in tags
        if tag.startswith(f"{dcc}:renderer:") and tag.count(":") >= 2
    )
    known = advertised | tagged
    if not known:
        return True
    return requested in known


def worker_supports_layer(worker: Any, layer: Any) -> tuple[bool, str]:
    """Return ``(compatible, reason)`` for a worker/layer pair."""

    requirements = extract_layer_requirements(layer)
    dcc = requirements["dcc"]

    # Preserve legacy dispatch for old jobs that carry no DCC metadata.
    if not dcc:
        return True, "legacy task without explicit DCC requirements"

    if worker is None:
        return False, f"unregistered worker cannot claim explicit {dcc} tasks"

    capabilities, tags = _worker_capabilities(worker)
    if not _dcc_available(dcc, capabilities, tags):
        return False, f"worker does not advertise {dcc}"

    versions = _available_versions(dcc, capabilities, tags)
    requested_version = requirements["dcc_version"]
    if requested_version and not versions_compatible(dcc, requested_version, versions):
        available = ", ".join(versions) or "none"
        return False, f"{dcc} {requested_version} requested; worker has {available}"

    if not _execution_mode_available(dcc, requirements["execution_mode"], capabilities, tags):
        return False, f"worker lacks execution mode {requirements['execution_mode']}"

    if not _renderer_available(dcc, requirements["renderer"], capabilities, tags):
        return False, f"worker lacks renderer {requirements['renderer']}"

    return True, "compatible"
