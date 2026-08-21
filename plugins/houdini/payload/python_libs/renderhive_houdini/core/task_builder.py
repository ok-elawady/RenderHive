"""Canonical Houdini task and RenderHive API 0.2.0 payload builder."""

from __future__ import absolute_import

import datetime
import getpass
import ntpath
import os
import re
import uuid

from renderhive_houdini.api.contract import contract_capabilities


class PayloadError(RuntimeError):
    pass


def _text(value, maximum=None, default=""):
    text = str(value if value is not None else default).strip()
    if maximum is not None:
        text = text[:maximum]
    return text


def _integer(value, default=0, minimum=None, maximum=None):
    try:
        result = int(round(float(value)))
    except Exception:
        result = int(default)
    if minimum is not None:
        result = max(int(minimum), result)
    if maximum is not None:
        result = min(int(maximum), result)
    return result


def _number(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _absolute_path(value):
    value = _text(value)
    if not value:
        return ""
    if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("\\\\", "//")):
        return ntpath.normpath(value)
    return os.path.abspath(value)


def _quote(value):
    return '"{}"'.format(str(value or "").replace('"', '\\"'))


def _safe_layer_name(value, fallback="render"):
    value = _text(value, maximum=256, default=fallback) or fallback
    value = value.strip("/\\")
    value = re.sub(r"[<>:\"/\\|?*]+", "_", value)
    value = re.sub(r"\s+", "_", value).strip(" ._")
    return value or fallback


def _unique_uuid_strings(values, field_name):
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        try:
            text = str(uuid.UUID(text))
        except Exception:
            raise PayloadError("{} contains an invalid UUID: {}".format(field_name, text))
        if text not in result:
            result.append(text)
    return result


def build_frame_range(start, end, step):
    start_value = _number(start, 1.0)
    end_value = _number(end, start_value)
    step_value = _number(step, 1.0)
    if step_value <= 0:
        raise PayloadError("Frame step must be greater than zero.")
    if end_value < start_value:
        raise PayloadError("Frame end cannot be lower than frame start.")

    def fmt(value):
        return str(int(value)) if abs(value - int(value)) < 1e-9 else ("{:.6f}".format(value).rstrip("0").rstrip("."))

    if abs(start_value - end_value) < 1e-9:
        return fmt(start_value)
    if abs(step_value - 1.0) < 1e-9:
        return "{}-{}".format(fmt(start_value), fmt(end_value))
    return "{}-{}x{}".format(fmt(start_value), fmt(end_value), fmt(step_value))


def _node_to_source(node_info):
    if node_info is None:
        raise PayloadError("Select at least one render source before submitting.")
    return {
        "path": _text(getattr(node_info, "path", ""), maximum=2048),
        "name": _text(getattr(node_info, "name", ""), maximum=256),
        "type_name": _text(getattr(node_info, "type_name", ""), maximum=128),
        "type_label": _text(getattr(node_info, "type_label", ""), maximum=256),
        "category": _text(getattr(node_info, "category", ""), maximum=64),
        "renderer": _text(getattr(node_info, "renderer", ""), maximum=128),
        "execution_mode": _text(getattr(node_info, "execution_mode", "hython"), maximum=32, default="hython") or "hython",
        "frame_start": _number(getattr(node_info, "frame_start", 1.0), 1.0),
        "frame_end": _number(getattr(node_info, "frame_end", 1.0), 1.0),
        "frame_step": _number(getattr(node_info, "frame_step", 1.0), 1.0),
        "camera": _text(getattr(node_info, "camera", ""), maximum=2048),
        "output_path": _absolute_path(getattr(node_info, "output_path", "")),
        "resolution": {
            "width": _integer(getattr(node_info, "resolution_width", 0), 0, minimum=0),
            "height": _integer(getattr(node_info, "resolution_height", 0), 0, minimum=0),
        },
        "usd_output_path": _text(getattr(node_info, "usd_output_path", ""), maximum=2048),
        "camera_override": bool(getattr(node_info, "camera_override", False)),
        "renderer_override": bool(getattr(node_info, "renderer_override", False)),
        "output_override": bool(getattr(node_info, "output_override", False)),
        "resolution_override": bool(getattr(node_info, "resolution_override", False)),
        "is_bypassed": bool(getattr(node_info, "is_bypassed", False)),
        "is_renderable": bool(getattr(node_info, "is_renderable", True)),
    }


def build_task(
    context,
    node_info,
    job_name,
    project_name,
    priority=50,
    department="",
    comment="",
    chunk_size=1,
    concurrent_tasks=1,
    pool_targeting=None,
    retry_count=2,
    timeout_seconds=None,
    min_cores=0,
    min_memory_mb=0,
    min_gpus=0,
    dependencies=None,
    render_nodes=None,
):
    if context is None:
        raise PayloadError("Scene context is required.")

    raw_nodes = list(render_nodes or [])
    if not raw_nodes and node_info is not None:
        raw_nodes = [node_info]
    if not raw_nodes:
        raise PayloadError("Select at least one render source before submitting.")

    sources = []
    seen_paths = set()
    for node in raw_nodes:
        source = _node_to_source(node)
        if not source["path"]:
            raise PayloadError("A selected render source has no Houdini node path.")
        if source["path"] in seen_paths:
            continue
        seen_paths.add(source["path"])
        sources.append(source)
    if not sources:
        raise PayloadError("No valid render sources are selected.")

    project_path = _absolute_path(context.project_path or context.job_directory or context.hip_directory)
    scene_path = _absolute_path(context.hip_path)
    if not scene_path:
        raise PayloadError("Save the HIP file before submitting.")
    if not project_path:
        raise PayloadError("A project path is required.")

    task_uid = "RH-HOU-{}-{}".format(
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
        uuid.uuid4().hex[:8].upper(),
    )
    targeting = dict(pool_targeting or {})
    first = sources[0]

    return {
        "schema_version": "2.1",
        "task_uid": task_uid,
        "created_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dcc": "houdini",
        "dcc_version": _text(context.houdini_version, maximum=64),
        "job_name": _text(job_name or context.scene_name or "Houdini Job", maximum=255),
        "project_name": _text(project_name or context.project_name or "Houdini Project", maximum=64),
        "department": _text(department, maximum=64),
        "comment": _text(comment),
        "priority": _integer(priority, 50, minimum=1, maximum=100),
        "user": _text(getpass.getuser(), maximum=64, default="houdini_user") or "houdini_user",
        "concurrent_tasks": _integer(concurrent_tasks, 1, minimum=0),
        "scene_path": scene_path,
        "project_path": project_path,
        "render_sources": sources,
        # First-source aliases are retained for diagnostics and older helper callers.
        "renderer": first.get("renderer", ""),
        "render_node": first.get("path", ""),
        "camera": first.get("camera", ""),
        "output_path": first.get("output_path", ""),
        "resolution": dict(first.get("resolution") or {}),
        "execution": {
            "mode": first.get("execution_mode", "hython"),
            "worker_mode": "hython_rop",
            "usd_output_path": first.get("usd_output_path", ""),
            "camera_override": bool(first.get("camera_override")),
            "renderer_override": bool(first.get("renderer_override")),
            "output_override": bool(first.get("output_override")),
            "resolution_override": bool(first.get("resolution_override")),
        },
        "frames": {
            "start": first.get("frame_start", 1),
            "end": first.get("frame_end", 1),
            "step": first.get("frame_step", 1),
            "chunk_size": _integer(chunk_size, 1, minimum=1),
        },
        "requirements": {
            "min_cores": _integer(min_cores, 0, minimum=0),
            "min_memory_mb": _integer(min_memory_mb, 0, minimum=0),
            "min_gpus": _integer(min_gpus, 0, minimum=0),
        },
        "failure_policy": {
            "max_retries": _integer(retry_count, 2, minimum=0, maximum=20),
            "timeout_seconds": None if timeout_seconds in (None, "", 0) else _integer(timeout_seconds, 0, minimum=1),
        },
        "job_dependencies": list(dependencies or []),
        "farm": targeting,
    }


def _source_for_command(task, source=None):
    if isinstance(source, dict):
        return dict(source)
    sources = task.get("render_sources") if isinstance(task, dict) else None
    if isinstance(sources, list) and sources:
        return dict(sources[0])
    return {
        "path": task.get("render_node", ""),
        "renderer": task.get("renderer", ""),
        "camera": task.get("camera", ""),
        "output_path": task.get("output_path", ""),
        "resolution": task.get("resolution") or {},
        "execution_mode": ((task.get("execution") or {}).get("mode") if isinstance(task.get("execution"), dict) else "hython") or "hython",
        "camera_override": bool((task.get("execution") or {}).get("camera_override")) if isinstance(task.get("execution"), dict) else False,
        "renderer_override": bool((task.get("execution") or {}).get("renderer_override")) if isinstance(task.get("execution"), dict) else False,
        "output_override": bool((task.get("execution") or {}).get("output_override")) if isinstance(task.get("execution"), dict) else False,
        "resolution_override": bool((task.get("execution") or {}).get("resolution_override")) if isinstance(task.get("execution"), dict) else False,
    }


def build_worker_command(task, config, source=None):
    houdini = config.get("houdini", {}) if isinstance(config, dict) else {}
    executable = _text(houdini.get("hython_executable"), default="hython") or "hython"
    frame_token = _text(houdini.get("frame_token"), default="{frame}") or "{frame}"
    scene_path = _absolute_path(task.get("scene_path"))
    source = _source_for_command(task, source)
    render_node = _text(source.get("path"))
    if not scene_path:
        raise PayloadError("A saved HIP file is required.")
    if not render_node:
        raise PayloadError("A render node is required.")

    command = [
        _quote(executable), "-m", "renderhive_houdini.worker.render_rop",
        "--scene", _quote(scene_path),
        "--node", _quote(render_node),
        "--frame", str(frame_token),
    ]
    if source.get("camera_override") and source.get("camera"):
        command.extend(["--camera", _quote(source.get("camera"))])
    if source.get("renderer_override") and source.get("renderer"):
        command.extend(["--renderer", _quote(source.get("renderer"))])
    if source.get("output_override") and source.get("output_path"):
        command.extend(["--output", _quote(source.get("output_path"))])
    if source.get("resolution_override"):
        resolution = source.get("resolution") or {}
        command.extend([
            "--width", str(_integer(resolution.get("width"), 0, minimum=0)),
            "--height", str(_integer(resolution.get("height"), 0, minimum=0)),
        ])
    return " ".join(command)


def _pool_submission_fields(task, config):
    capabilities = contract_capabilities(config)
    if not capabilities.get("job_pool_targeting", False):
        return {}
    farm = task.get("farm") or {}
    strategy = str(farm.get("strategy") or "all").strip().lower()
    selected = _unique_uuid_strings(farm.get("selected_pool_ids") or farm.get("effective_pool_ids") or [], "selected_pool_ids")
    excluded = _unique_uuid_strings(farm.get("excluded_pool_ids") or [], "excluded_pool_ids")
    overlap = sorted(set(selected).intersection(excluded))
    if overlap:
        raise PayloadError("Pools cannot be both included and excluded: {}".format(", ".join(overlap)))
    if strategy in ("selected", "selected_only", "selected pools only"):
        if not selected:
            raise PayloadError("Selected Pools Only requires at least one backend pool.")
        return {"included_pools": selected, "excluded_pools": []}
    if strategy in ("all_except", "all_except_selected", "all except selected"):
        return {"included_pools": [], "excluded_pools": excluded or selected}
    return {"included_pools": [], "excluded_pools": []}


def _dependency_specs(task, config):
    if not contract_capabilities(config).get("job_dependencies", False):
        return []
    result = []
    for value in task.get("job_dependencies") or []:
        if isinstance(value, dict):
            parent_job = str(value.get("parent_job") or "").strip()
            dep_type = str(value.get("type") or "JOB_ON_JOB").strip() or "JOB_ON_JOB"
            parent_layer = value.get("parent_layer")
            dep_layer = value.get("dep_layer")
        else:
            parent_job = str(value or "").strip()
            dep_type = "JOB_ON_JOB"
            parent_layer = None
            dep_layer = None
        if not parent_job:
            continue
        try:
            parent_job = str(uuid.UUID(parent_job))
        except Exception:
            raise PayloadError("Job dependency contains an invalid UUID: {}".format(parent_job))
        item = {"type": dep_type, "parent_job": parent_job}
        if parent_layer not in (None, ""):
            item["parent_layer"] = _text(parent_layer, maximum=256)
        if dep_layer not in (None, ""):
            item["dep_layer"] = _text(dep_layer, maximum=256)
        if item not in result:
            result.append(item)
    return result


def _compatibility_tags(task, source):
    tags = ["dcc:houdini"]
    version = _text(task.get("dcc_version"), maximum=32)
    if version:
        parts = re.findall(r"\d+", version)
        series = ".".join(parts[:2]) if parts else version
        tags.append("houdini:{}".format(series))
    mode = _text(source.get("execution_mode"), maximum=24).lower()
    if mode:
        tags.append("houdini:{}".format(mode))
    renderer = _text(source.get("renderer"), maximum=48).lower()
    renderer = re.sub(r"[^a-z0-9]+", "-", renderer).strip("-")
    if renderer:
        tags.append("renderer:{}".format(renderer))
    return list(dict.fromkeys(tag for tag in tags if tag))


def _worker_targeting_info(task, config):
    farm = task.get("farm") or {}
    capabilities = contract_capabilities(config)
    return {
        "strategy": farm.get("strategy", "all"),
        "selected_pool_ids": list(farm.get("selected_pool_ids") or []),
        "selected_pool_names": list(farm.get("selected_pool_names") or []),
        "excluded_pool_ids": list(farm.get("excluded_pool_ids") or []),
        "excluded_pool_names": list(farm.get("excluded_pool_names") or []),
        "effective_pool_ids": list(farm.get("effective_pool_ids") or []),
        "effective_pool_names": list(farm.get("effective_pool_names") or []),
        "eligible_worker_count": int(farm.get("eligible_worker_count") or 0),
        "enforcement": "job_pool_fields" if capabilities.get("job_pool_targeting") else "metadata_only",
        "api_field": "included_pools/excluded_pools" if capabilities.get("job_pool_targeting") else "",
    }


def _scene_info(task, source, config):
    req = task.get("requirements") or {}
    failure = task.get("failure_policy") or {}
    return {
        "schema_version": task.get("schema_version", "2.1"),
        "api_contract_version": contract_capabilities(config).get("contract_version"),
        "task_uid": task.get("task_uid", ""),
        "dcc": "houdini",
        "houdini_version": task.get("dcc_version", ""),
        "renderer": source.get("renderer", ""),
        "render_node": source.get("path", ""),
        "render_node_type": source.get("type_name", ""),
        "camera": source.get("camera", ""),
        "project_path": task.get("project_path", ""),
        "output_path": source.get("output_path", ""),
        "resolution": source.get("resolution") or {},
        "execution": {
            "mode": source.get("execution_mode", "hython"),
            "worker_mode": "hython_rop",
            "render_node": source.get("path", ""),
            "usd_output_path": source.get("usd_output_path", ""),
            "camera_override": bool(source.get("camera_override")),
            "renderer_override": bool(source.get("renderer_override")),
            "output_override": bool(source.get("output_override")),
            "resolution_override": bool(source.get("resolution_override")),
        },
        "worker_targeting": _worker_targeting_info(task, config),
        "resource_requirements": {
            "minimum_cores": _integer(req.get("min_cores"), 0, minimum=0),
            "minimum_ram_mb": _integer(req.get("min_memory_mb"), 0, minimum=0),
            "minimum_gpus": _integer(req.get("min_gpus"), 0, minimum=0),
        },
        "failure_policy": failure,
        "job_dependencies": list(task.get("job_dependencies") or []),
        "comment": task.get("comment", ""),
    }


def _layer_specs(task):
    sources = task.get("render_sources")
    if not isinstance(sources, list) or not sources:
        sources = [_source_for_command(task)]
    result = []
    seen_names = set()
    for index, source in enumerate(sources):
        source = dict(source or {})
        path = _text(source.get("path"))
        if not path:
            raise PayloadError("A selected render source has no Houdini node path.")
        base = source.get("name") or path.rsplit("/", 1)[-1] or "render_{}".format(index + 1)
        layer_name = _safe_layer_name(base, fallback="render_{}".format(index + 1))
        if layer_name in seen_names:
            layer_name = _safe_layer_name(path, fallback="render_{}".format(index + 1))
        suffix = 2
        candidate = layer_name
        while candidate in seen_names:
            candidate = "{}_{}".format(layer_name, suffix); suffix += 1
        layer_name = candidate
        seen_names.add(layer_name)
        source["backend_layer_name"] = layer_name
        result.append(source)
    return result


def _build_layer_payload(task, source, config):
    frames = {
        "start": source.get("frame_start", (task.get("frames") or {}).get("start", 1)),
        "end": source.get("frame_end", (task.get("frames") or {}).get("end", 1)),
        "step": source.get("frame_step", (task.get("frames") or {}).get("step", 1)),
    }
    req = task.get("requirements") or {}
    failure = task.get("failure_policy") or {}
    scene_path = _absolute_path(task.get("scene_path"))
    project_path = _absolute_path(task.get("project_path"))
    min_gpus = _integer(req.get("min_gpus"), 0, minimum=0)
    if "xpu" in str(source.get("renderer") or "").lower():
        min_gpus = max(min_gpus, 1)
    payload = {
        "name": source.get("backend_layer_name") or _safe_layer_name(source.get("name") or source.get("path")),
        "layer_type": "RENDER",
        "command": build_worker_command(task, config, source=source),
        "frame_range": build_frame_range(frames["start"], frames["end"], frames["step"]),
        "chunk_size": _integer((task.get("frames") or {}).get("chunk_size"), 1, minimum=1),
        "min_cores": _integer(req.get("min_cores"), 0, minimum=0),
        "min_memory_mb": _integer(req.get("min_memory_mb"), 0, minimum=0),
        "min_gpus": min_gpus,
        "tags": _compatibility_tags(task, source),
        "scene_path": scene_path,
        "scene_info": _scene_info(task, source, config),
        "env": {
            "HIP": os.path.dirname(scene_path),
            "JOB": project_path,
            "RENDERHIVE_DCC": "houdini",
            "RENDERHIVE_HOUDINI_VERSION": str(task.get("dcc_version") or ""),
            "RENDERHIVE_HOUDINI_RENDER_NODE": str(source.get("path") or ""),
        },
        "max_retries": _integer(failure.get("max_retries"), 2, minimum=0, maximum=20),
    }
    timeout_seconds = failure.get("timeout_seconds")
    if timeout_seconds not in (None, ""):
        payload["timeout_seconds"] = _integer(timeout_seconds, 0, minimum=0)
    return payload


def build_api_request(task, config):
    if not isinstance(task, dict):
        raise PayloadError("RenderHive task must be a dictionary.")
    scene_path = _absolute_path(task.get("scene_path"))
    project_path = _absolute_path(task.get("project_path"))
    if not scene_path:
        raise PayloadError("Save the HIP file before submitting.")
    if not project_path:
        raise PayloadError("A project path is required.")

    sources = _layer_specs(task)
    for source in sources:
        if not _absolute_path(source.get("output_path")):
            raise PayloadError("Render source '{}' has no final image output path.".format(source.get("path") or source.get("name") or "unknown"))
    layers = [_build_layer_payload(task, source, config) for source in sources]

    first_output = _absolute_path(sources[0].get("output_path"))
    log_root = first_output if os.path.isdir(first_output) else os.path.dirname(first_output)
    log_directory = _absolute_path(os.path.join(log_root or os.path.join(project_path, "render"), "_renderhive_logs"))

    payload = {
        "visible_name": _text(task.get("job_name"), maximum=255),
        "project": _text(task.get("project_name"), maximum=64),
        "department": _text(task.get("department"), maximum=64),
        "user": _text(task.get("user"), maximum=64, default="houdini_user") or "houdini_user",
        "priority": _integer(task.get("priority"), 50, minimum=1, maximum=100),
        "log_directory": log_directory,
        "max_tasks_per_worker": _integer(task.get("concurrent_tasks"), 1, minimum=0),
        "layers": layers,
    }
    payload.update(_pool_submission_fields(task, config))
    if contract_capabilities(config).get("job_dependencies", False):
        payload["dependencies"] = _dependency_specs(task, config)
    validate_job_request(payload)
    return payload


def validate_job_request(payload):
    errors = []
    if not isinstance(payload, dict):
        raise PayloadError("Job request must be a dictionary.")
    for field in ("project", "user", "log_directory", "layers"):
        if not payload.get(field):
            errors.append("Missing required JobCreate field: {}".format(field))
    try:
        priority = int(payload.get("priority", 50))
        if not 1 <= priority <= 100:
            errors.append("Job priority must be between 1 and 100.")
    except Exception:
        errors.append("Job priority must be an integer.")
    if "max_frames_per_worker" in payload:
        errors.append("Use API 0.2.0 max_tasks_per_worker, not max_frames_per_worker.")
    layers = payload.get("layers") or []
    names = set()
    if not isinstance(layers, list) or not layers:
        errors.append("JobCreate.layers must contain at least one layer.")
    else:
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                errors.append("Layer {} must be a dictionary.".format(index)); continue
            name = str(layer.get("name") or "").strip()
            if name in names:
                errors.append("Layer name must be unique within a Job: {}".format(name))
            names.add(name)
            for field in ("name", "command", "frame_range", "scene_path"):
                if not layer.get(field):
                    errors.append("Layer {} is missing required field: {}".format(index, field))
    included = set(payload.get("included_pools") or [])
    excluded = set(payload.get("excluded_pools") or [])
    overlap = sorted(included.intersection(excluded))
    if overlap:
        errors.append("Pools cannot be both included and excluded: {}".format(", ".join(overlap)))
    deps = payload.get("dependencies") or []
    if not isinstance(deps, list):
        errors.append("JobCreate.dependencies must be a list.")
    else:
        for index, dep in enumerate(deps):
            if not isinstance(dep, dict) or not dep.get("parent_job"):
                errors.append("Dependency {} must include parent_job.".format(index))
    for forbidden in ("start_suspended", "machine_limit"):
        if forbidden in payload:
            errors.append("Unsupported JobCreate field present: {}".format(forbidden))
    if errors:
        raise PayloadError("\n".join(errors))
    return True


# Backward-compatible preview helper for lightweight callers/tests.
def build_preview(context, node_info, job_name, priority=50, chunk_size=1, department=""):
    return build_task(
        context,
        node_info,
        job_name=job_name,
        project_name=context.project_name or "Houdini Project",
        priority=priority,
        chunk_size=chunk_size,
        department=department,
    )
