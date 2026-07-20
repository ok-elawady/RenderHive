from __future__ import absolute_import

import getpass
import os
import platform


class PayloadError(RuntimeError):
    pass


def _text(value, maximum=None, default=""):
    text = str(value if value is not None else default).strip()
    if maximum is not None:
        text = text[:maximum]
    return text


def _integer(value, default=0, minimum=None, maximum=None):
    try:
        result = int(value)
    except Exception:
        result = int(default)

    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def build_frame_range(task):
    start = _integer(task.get("frame_start"), 1)
    end = _integer(task.get("frame_end"), start)
    step = _integer(task.get("frame_step"), 1, minimum=1)

    if start == end:
        return str(start)
    if step == 1:
        return "{}-{}".format(start, end)
    return "{}-{}x{}".format(start, end, step)


def _quote(value):
    value = str(value or "").replace('"', '\\"')
    return '"{}"'.format(value)


def build_maya_command(task, config):
    maya_config = config.get("maya", {})
    executable = _text(
        maya_config.get("render_executable"),
        default="Render.exe"
    ) or "Render.exe"
    frame_token = _text(
        maya_config.get("frame_token"),
        default="{frame}"
    ) or "{frame}"

    renderer = _text(task.get("renderer"), default="arnold") or "arnold"

    parts = [
        _quote(executable),
        "-r", renderer,
    ]

    parts.extend([
        "-s", frame_token,
        "-e", frame_token,
        "-b", "1",
        "-cam", _quote(task.get("camera")),
        "-proj", _quote(task.get("project_path")),
        "-rd", _quote(task.get("output_path")),
    ])

    # For Arnold, injecting image formatting flags directly into the command line (-of, -im)
    # causes Render.exe to crash because it applies them before plugins load.
    # Instead, we force-load Arnold and apply the user's overrides manually via python in the preRender script!
    if renderer == "arnold":
        image_name = task.get("image_name") or ""
        image_format = task.get("image_format") or "exr"
        padding = _integer(task.get("frame_padding"), 4, minimum=1)
        
        py_script = [
            "import maya.cmds as cmds",
            "cmds.loadPlugin('mtoa', quiet=True)",
            "import mtoa.core",
            "mtoa.core.createOptions()"
        ]
        
        if image_name:
            py_script.append(f"cmds.setAttr('defaultRenderGlobals.imageFilePrefix', '{image_name}', type='string')")
        if image_format:
            py_script.append(f"cmds.setAttr('defaultArnoldDriver.aiTranslator', '{image_format}', type='string')")
        if padding:
            py_script.append(f"cmds.setAttr('defaultRenderGlobals.extensionPadding', {padding})")
            
        # Prevent Arnold from silently aborting the batch render if no network license is found
        py_script.append("cmds.setAttr('defaultArnoldRenderOptions.abortOnLicenseFail', 0)")
            
        py_string = "; ".join(py_script)
        parts.extend(["-preRender", _quote(f"python(\"{py_string}\");")])
        
        # Force the formatting to be name.#.ext instead of name.ext.#
        parts.extend(["-fnc", "3"])
    else:
        parts.extend([
            "-im", _quote(task.get("image_name")),
            "-of", _text(task.get("image_format"), default="exr") or "exr",
            "-pad", str(_integer(task.get("frame_padding"), 4, minimum=1)),
            "-fnc", "3",
        ])

    parts.append(_quote(task.get("scene_path")))

    return " ".join(parts)


def _scene_info(task):
    software_info = task.get("software_info") or {}
    validation = task.get("validation") or {}
    farm = task.get("farm") or {}
    submission = task.get("submission") or {}

    return {
        "schema_version": task.get("schema_version", "2.0"),
        "task_uid": task.get("task_uid", ""),
        "dcc": "maya",
        "maya_version": software_info.get("maya_version", ""),
        "host_os": software_info.get("host_os", platform.system()),
        "renderer": task.get("renderer", ""),
        "camera": task.get("camera", ""),
        "project_path": task.get("project_path", ""),
        "output_path": task.get("output_path", ""),
        "image_name": task.get("image_name", ""),
        "image_format": task.get("image_format", ""),
        "frame_padding": task.get("frame_padding", 4),
        "resolution": {
            "width": task.get("width", 0),
            "height": task.get("height", 0),
        },
        "submission": {
            "mode": submission.get(
                "mode",
                task.get("submission_mode", "Shared Storage")
            ),
        },
        "worker_targeting": {
            "pool": farm.get("pool", task.get("pool", "All")),
            "pool_id": farm.get("pool_id", task.get("pool_id", "")),
            "pool_workers": farm.get(
                "pool_workers",
                task.get("pool_workers", [])
            ),
            "allowed_workers": farm.get(
                "allowed_workers",
                task.get("allowed_workers", [])
            ),
            "denied_workers": farm.get(
                "denied_workers",
                task.get("denied_workers", [])
            ),
            "machine_limit": farm.get(
                "machine_limit",
                task.get("machine_limit", 0)
            ),
        },
        "job_dependencies": task.get("job_dependencies", []),
        "comment": task.get("comment", ""),
        "validation": validation,
    }


def build_job_request(task, config):
    if not isinstance(task, dict):
        raise PayloadError("RenderHive task must be a dictionary.")

    project = _text(
        task.get("project_name")
        or (task.get("job") or {}).get("project"),
        maximum=64,
    )
    visible_name = _text(
        task.get("job_name")
        or (task.get("job") or {}).get("name"),
        maximum=255,
    )
    department = _text(
        task.get("department")
        or (task.get("job") or {}).get("department"),
        maximum=64,
    )
    user = _text(getpass.getuser(), maximum=64, default="maya_user") or "maya_user"
    scene_path = os.path.abspath(_text(task.get("scene_path")))
    output_path = os.path.abspath(_text(task.get("output_path")))

    if not project:
        raise PayloadError("Project is required by the RenderHive API.")
    if not visible_name:
        raise PayloadError("Job name is required by the RenderHive API.")
    if not scene_path:
        raise PayloadError("Scene path is required by the RenderHive API.")
    if not output_path:
        raise PayloadError("Output path is required by the RenderHive API.")

    log_directory = os.path.join(output_path, "_renderhive_logs")
    try:
        if not os.path.isdir(log_directory):
            os.makedirs(log_directory)
    except Exception:
        # Shared storage may be mounted only on workers. The API requires the
        # absolute path, but local creation is not mandatory for submission.
        pass

    pool_name = _text(
        task.get("pool")
        or (task.get("farm") or {}).get("pool"),
        maximum=64,
        default="All",
    ) or "All"

    tags = []
    if (
        bool(config.get("maya", {}).get("use_pool_as_tag", True))
        and pool_name.lower() not in ("all", "all workers")
    ):
        tags.append(pool_name)

    min_ram_gb = _integer(task.get("minimum_ram_gb"), 0, minimum=0)
    min_vram_gb = _integer(task.get("minimum_vram_gb"), 0, minimum=0)
    timeout_minutes = _integer(task.get("task_timeout_minutes"), 0, minimum=0)

    layer_name = _text(
        config.get("maya", {}).get("layer_name"),
        maximum=256,
        default="beauty",
    ) or "beauty"

    layer = {
        "name": layer_name,
        "layer_type": "RENDER",
        "command": build_maya_command(task, config),
        "frame_range": build_frame_range(task),
        "chunk_size": _integer(task.get("chunk_size"), 1, minimum=1),
        "min_cores": 0,
        "min_memory_mb": min_ram_gb * 1024,
        "min_gpus": 1 if min_vram_gb > 0 else 0,
        "tags": tags,
        "scene_path": scene_path,
        "scene_info": _scene_info(task),
        "env": {
            "MAYA_PROJECT": task.get("project_path", ""),
            "RENDERHIVE_SUBMISSION_MODE": task.get(
                "submission_mode",
                "Shared Storage"
            ),
        },
        "max_retries": _integer(task.get("retry_count"), 2, minimum=0),
        "timeout_seconds": timeout_minutes * 60 if timeout_minutes else None,
    }

    payload = {
        "visible_name": visible_name,
        "project": project,
        "department": department,
        "user": user,
        "priority": _integer(task.get("priority"), 50, minimum=1, maximum=100),
        "log_directory": log_directory,
        "max_frames_per_worker": _integer(
            task.get("concurrent_tasks"),
            1,
            minimum=0,
        ),
        "layers": [layer],
    }

    validate_job_request(payload)
    return payload


def validate_job_request(payload):
    errors = []

    for field in ("project", "user", "log_directory", "layers"):
        if not payload.get(field):
            errors.append("Missing required JobCreate field: {}".format(field))

    layers = payload.get("layers") or []
    if not isinstance(layers, list) or not layers:
        errors.append("JobCreate.layers must contain at least one layer.")
    else:
        for index, layer in enumerate(layers):
            for field in ("name", "command", "frame_range"):
                if not layer.get(field):
                    errors.append(
                        "Layer {} is missing required field: {}".format(
                            index,
                            field,
                        )
                    )

    if errors:
        raise PayloadError("\n".join(errors))

    return True
