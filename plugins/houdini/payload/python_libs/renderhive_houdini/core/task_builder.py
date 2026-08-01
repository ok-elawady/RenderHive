"""Build backend-ready Houdini jobs using the current RenderHive API contract."""

from __future__ import absolute_import

import getpass
import ntpath
import os
import re


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


def _absolute_path(value):
    value = _text(value)
    if not value:
        return ""
    if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("\\\\", "//")):
        return ntpath.normpath(value)
    return os.path.abspath(value)


def _quote(value):
    return '"{}"'.format(str(value or "").replace('"', '\\"'))


def build_frame_range(start, end, step):
    start = _integer(start, 1)
    end = _integer(end, start)
    step = _integer(step, 1, minimum=1)
    if end < start:
        raise PayloadError("Frame end cannot be lower than frame start.")
    if start == end:
        return str(start)
    if step == 1:
        return "{}-{}".format(start, end)
    return "{}-{}x{}".format(start, end, step)


def build_worker_command(task, config):
    houdini = config.get("houdini", {})
    executable = _text(houdini.get("hython_executable"), default="hython") or "hython"
    frame_token = _text(houdini.get("frame_token"), default="{frame}") or "{frame}"
    scene_path = _absolute_path(task.get("scene_path"))
    render_node = _text(task.get("render_node"))
    if not scene_path:
        raise PayloadError("A saved HIP file is required.")
    if not render_node:
        raise PayloadError("A render node is required.")
    command = [
        _quote(executable),
        "-m",
        "renderhive_houdini.worker.render_rop",
        "--scene",
        _quote(scene_path),
        "--node",
        _quote(render_node),
        "--frame",
        str(frame_token),
    ]
    execution = task.get("execution") or {}
    if execution.get("camera_override") and task.get("camera"):
        command.extend(["--camera", _quote(task.get("camera"))])
    if execution.get("renderer_override") and task.get("renderer"):
        command.extend(["--renderer", _quote(task.get("renderer"))])
    if execution.get("output_override") and task.get("output_path"):
        command.extend(["--output", _quote(task.get("output_path"))])
    if execution.get("resolution_override"):
        resolution = task.get("resolution") or {}
        command.extend([
            "--width", str(_integer(resolution.get("width"), 0, minimum=0)),
            "--height", str(_integer(resolution.get("height"), 0, minimum=0)),
        ])
    return " ".join(command)


def build_task(
    context,
    node_info,
    job_name,
    project_name,
    priority=50,
    department="",
    comment="",
    chunk_size=1,
    machine_limit=0,
    concurrent_tasks=1,
    start_suspended=False,
    pool_targeting=None,
):
    if context is None:
        raise PayloadError("Scene context is required.")
    if node_info is None:
        raise PayloadError("Select a render node before submitting.")

    targeting = dict(pool_targeting or {})
    project_path = _absolute_path(context.project_path or context.job_directory or context.hip_directory)
    output_path = _absolute_path(node_info.output_path)

    return {
        "dcc": "houdini",
        "dcc_version": context.houdini_version,
        "job_name": _text(job_name or context.scene_name or "Houdini Job", maximum=255),
        "project_name": _text(project_name or context.project_name or "Houdini Project", maximum=64),
        "department": _text(department, maximum=64),
        "comment": _text(comment),
        "priority": _integer(priority, 50, minimum=1, maximum=100),
        "user": _text(getpass.getuser(), maximum=64, default="houdini_user") or "houdini_user",
        "start_suspended": bool(start_suspended),
        "machine_limit": _integer(machine_limit, 0, minimum=0),
        "max_frames_per_worker": _integer(concurrent_tasks, 1, minimum=0),
        "scene_path": _absolute_path(context.hip_path),
        "project_path": project_path,
        "renderer": _text(node_info.renderer),
        "render_node": _text(node_info.path),
        "camera": _text(node_info.camera),
        "output_path": output_path,
        "resolution": {
            "width": _integer(node_info.resolution_width, 0, minimum=0),
            "height": _integer(node_info.resolution_height, 0, minimum=0),
        },
        "frames": {
            "start": _integer(node_info.frame_start, 1),
            "end": _integer(node_info.frame_end, 1),
            "step": _integer(node_info.frame_step, 1, minimum=1),
            "chunk_size": _integer(chunk_size, 1, minimum=1),
        },
        "execution": {
            "mode": _text(node_info.execution_mode or "hython"),
            "worker_mode": "hython_rop",
            "render_node": _text(node_info.path),
            "usd_output_path": _text(getattr(node_info, "usd_output_path", "")),
            "camera_override": bool(getattr(node_info, "camera_override", False)),
            "renderer_override": bool(getattr(node_info, "renderer_override", False)),
            "output_override": bool(getattr(node_info, "output_override", False)),
            "resolution_override": bool(getattr(node_info, "resolution_override", False)),
        },
        "farm": targeting,
    }


def _contract_field(config, name):
    contract = config.get("contract") if isinstance(config.get("contract"), dict) else {}
    value = str(contract.get(name) or "").strip()
    if value and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise PayloadError("Invalid contract field name: {}".format(name))
    return value


def build_api_request(task, config):
    if not isinstance(task, dict):
        raise PayloadError("RenderHive task must be a dictionary.")

    scene_path = _absolute_path(task.get("scene_path"))
    project_path = _absolute_path(task.get("project_path"))
    output_path = _absolute_path(task.get("output_path"))
    if not scene_path:
        raise PayloadError("Save the HIP file before submitting.")
    if not project_path:
        raise PayloadError("A project path is required.")
    if not output_path:
        raise PayloadError("The selected render node has no output path.")

    frames = task.get("frames") or {}
    frame_range = build_frame_range(frames.get("start"), frames.get("end"), frames.get("step"))
    farm = task.get("farm") or {}
    effective_pool_names = list(farm.get("effective_pool_names") or [])
    effective_pool_ids = list(farm.get("effective_pool_ids") or [])

    tags = []
    if bool(config.get("houdini", {}).get("use_pool_as_tag", True)):
        for pool_name in effective_pool_names:
            clean = _text(pool_name, maximum=64)
            if clean and clean not in tags:
                tags.append(clean)
    renderer_tag = _text(task.get("renderer"), maximum=64).lower().replace(" ", "-")
    if renderer_tag and renderer_tag not in tags:
        tags.append(renderer_tag)
    if "houdini" not in tags:
        tags.append("houdini")

    log_directory = os.path.join(output_path if os.path.isdir(output_path) else os.path.dirname(output_path), "_renderhive_logs")
    if not log_directory:
        log_directory = os.path.join(project_path, "render", "_renderhive_logs")

    scene_info = {
        "schema_version": "1.0",
        "dcc": "houdini",
        "houdini_version": task.get("dcc_version", ""),
        "renderer": task.get("renderer", ""),
        "render_node": task.get("render_node", ""),
        "camera": task.get("camera", ""),
        "project_path": project_path,
        "output_path": output_path,
        "resolution": task.get("resolution") or {},
        "execution": task.get("execution") or {},
        "worker_targeting": {
            "strategy": farm.get("strategy", "all"),
            "selected_pool_ids": list(farm.get("selected_pool_ids") or []),
            "selected_pool_names": list(farm.get("selected_pool_names") or []),
            "excluded_pool_ids": list(farm.get("excluded_pool_ids") or []),
            "excluded_pool_names": list(farm.get("excluded_pool_names") or []),
            "effective_pool_ids": effective_pool_ids,
            "effective_pool_names": effective_pool_names,
            "eligible_worker_count": int(farm.get("eligible_worker_count") or 0),
            "machine_limit": int(task.get("machine_limit") or 0),
        },
        "comment": task.get("comment", ""),
        "start_suspended": bool(task.get("start_suspended", False)),
    }

    layer = {
        "name": _text(config.get("houdini", {}).get("layer_name"), maximum=256, default="beauty") or "beauty",
        "layer_type": "RENDER",
        "command": build_worker_command(task, config),
        "frame_range": frame_range,
        "chunk_size": _integer(frames.get("chunk_size"), 1, minimum=1),
        "min_cores": 0,
        "min_memory_mb": 0,
        "min_gpus": 1 if "xpu" in str(task.get("renderer") or "").lower() else 0,
        "tags": tags,
        "scene_path": scene_path,
        "scene_info": scene_info,
        "env": {
            "HIP": os.path.dirname(scene_path),
            "JOB": project_path,
            "RENDERHIVE_DCC": "houdini",
            "RENDERHIVE_HOUDINI_VERSION": str(task.get("dcc_version") or ""),
        },
        "max_retries": 2,
        "timeout_seconds": None,
    }

    pool_field = _contract_field(config, "layer_pool_ids_field")
    if pool_field:
        layer[pool_field] = effective_pool_ids

    payload = {
        "visible_name": _text(task.get("job_name"), maximum=255),
        "project": _text(task.get("project_name"), maximum=64),
        "department": _text(task.get("department"), maximum=64),
        "user": _text(task.get("user"), maximum=64, default="houdini_user") or "houdini_user",
        "priority": _integer(task.get("priority"), 50, minimum=1, maximum=100),
        "log_directory": _absolute_path(log_directory),
        "max_frames_per_worker": _integer(task.get("max_frames_per_worker"), 1, minimum=0),
        "layers": [layer],
    }

    suspended_field = _contract_field(config, "job_start_suspended_field")
    if suspended_field:
        payload[suspended_field] = bool(task.get("start_suspended", False))
    machine_field = _contract_field(config, "job_machine_limit_field")
    if machine_field:
        payload[machine_field] = _integer(task.get("machine_limit"), 0, minimum=0)
    return payload


# Backward-compatible helper retained for existing tests and callers.
def build_preview(context, node_info, job_name, priority=50, chunk_size=1, department="", start_suspended=False):
    return build_task(
        context,
        node_info,
        job_name=job_name,
        project_name=context.project_name or "Houdini Project",
        priority=priority,
        chunk_size=chunk_size,
        department=department,
        start_suspended=start_suspended,
    )
