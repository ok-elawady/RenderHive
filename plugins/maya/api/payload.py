from __future__ import absolute_import

import base64
import getpass
import ntpath
import os
import platform
import re

from .contract import contract_capabilities


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


def _absolute_path(value):
    value = _text(value)
    if not value:
        return ""

    # Preserve Windows drive and UNC paths when contract tests run on another
    # operating system. Maya production runs on Windows, but deterministic path
    # handling keeps the request payload portable and testable.
    if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("\\\\", "//")):
        return ntpath.normpath(value)

    return os.path.abspath(value)


def build_frame_range(task):
    start = _integer(task.get("frame_start"), 1)
    end = _integer(task.get("frame_end"), start)
    step = _integer(task.get("frame_step"), 1, minimum=1)

    if end < start:
        raise PayloadError(
            "Frame end cannot be lower than frame start."
        )

    if start == end:
        return str(start)
    if step == 1:
        return "{}-{}".format(start, end)
    return "{}-{}x{}".format(start, end, step)


def _quote(value):
    value = str(value or "").replace('"', '\\"')
    return '"{}"'.format(value)


def _python_literal(value):
    return repr(str(value or ""))


def _mel_python_command(statements):
    script = "; ".join(str(item) for item in statements if item)
    escaped = script.replace("\\", "\\\\").replace('"', '\\"')
    return 'python("{}");'.format(escaped)


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
    camera = _text(task.get("camera"))
    project_path = _absolute_path(task.get("project_path"))
    output_path = _absolute_path(task.get("output_path"))
    scene_path = _absolute_path(task.get("scene_path"))

    if not camera:
        raise PayloadError("A render camera is required.")

    parts = [
        _quote(executable),
        "-r", renderer,
        "-s", frame_token,
        "-e", frame_token,
        "-b", "1",
        "-cam", _quote(camera),
        "-proj", _quote(project_path),
        "-rd", _quote(output_path),
    ]

    if renderer.lower() == "arnold":
        image_name = _text(task.get("image_name"))
        image_format = _text(task.get("image_format"), default="exr") or "exr"
        padding = _integer(task.get("frame_padding"), 4, minimum=1)

        py_script = [
            "import maya.cmds as cmds",
            "cmds.loadPlugin('mtoa', quiet=True)",
            "import mtoa.core",
            "mtoa.core.createOptions()",
        ]

        if image_name:
            py_script.append(
                "cmds.setAttr('defaultRenderGlobals.imageFilePrefix', {}, type='string')".format(
                    _python_literal(image_name)
                )
            )
        if image_format:
            py_script.append(
                "cmds.setAttr('defaultArnoldDriver.aiTranslator', {}, type='string')".format(
                    _python_literal(image_format)
                )
            )
        py_script.append(
            "cmds.setAttr('defaultRenderGlobals.extensionPadding', {})".format(
                padding
            )
        )
        py_script.append(
            "cmds.setAttr('defaultArnoldRenderOptions.abortOnLicenseFail', 0)"
        )

        encoded_script = base64.b64encode(
            "; ".join(py_script).encode("utf-8")
        ).decode("ascii")
        runner = (
            "import base64;exec(base64.b64decode('{}').decode('utf-8'))"
        ).format(encoded_script)

        parts.extend([
            "-preRender",
            _quote(_mel_python_command([runner])),
            "-fnc",
            "3",
        ])
    else:
        parts.extend([
            "-im", _quote(task.get("image_name")),
            "-of", _text(task.get("image_format"), default="exr") or "exr",
            "-pad", str(_integer(task.get("frame_padding"), 4, minimum=1)),
            "-fnc", "3",
        ])

    parts.append(_quote(scene_path))
    return " ".join(parts)


def _worker_targeting_info(task, config):
    farm = task.get("farm") or {}
    capabilities = contract_capabilities(config)
    effective_ids = list(
        task.get("effective_pool_ids")
        or farm.get("effective_pool_ids")
        or []
    )
    use_pool_as_tag = bool(
        config.get("maya", {}).get("use_pool_as_tag", True)
    )

    if capabilities.get("layer_pool_ids_field"):
        enforcement = "api_field"
    elif use_pool_as_tag:
        enforcement = "legacy_tags"
    else:
        enforcement = "metadata_only"

    return {
        "strategy": farm.get(
            "pool_strategy",
            task.get("pool_strategy", "all")
        ),
        "selected_pool_ids": farm.get(
            "selected_pool_ids",
            task.get("selected_pool_ids", [])
        ),
        "selected_pool_names": farm.get(
            "selected_pool_names",
            task.get("selected_pool_names", [])
        ),
        "excluded_pool_ids": farm.get(
            "excluded_pool_ids",
            task.get("excluded_pool_ids", [])
        ),
        "excluded_pool_names": farm.get(
            "excluded_pool_names",
            task.get("excluded_pool_names", [])
        ),
        "effective_pool_ids": effective_ids,
        "effective_pool_names": farm.get(
            "effective_pool_names",
            task.get("effective_pool_names", [])
        ),
        "pool_workers": farm.get(
            "pool_workers",
            task.get("pool_workers", [])
        ),
        "machine_limit": farm.get(
            "machine_limit",
            task.get("machine_limit", 0)
        ),
        "enforcement": enforcement,
        "api_field": capabilities.get("layer_pool_ids_field", ""),
    }


def _scene_info(task, config):
    software_info = task.get("software_info") or {}
    validation = task.get("validation") or {}
    submission = task.get("submission") or {}
    capabilities = contract_capabilities(config)

    return {
        "schema_version": task.get("schema_version", "2.1"),
        "api_contract_version": capabilities.get("contract_version"),
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
            "start_suspended": bool(task.get("start_suspended", False)),
        },
        "worker_targeting": _worker_targeting_info(task, config),
        "resource_requirements": {
            "minimum_ram_gb": _integer(
                task.get("minimum_ram_gb"),
                0,
                minimum=0,
            ),
            "minimum_vram_gb": _integer(
                task.get("minimum_vram_gb"),
                0,
                minimum=0,
            ),
        },
        "job_dependencies": task.get("job_dependencies", []),
        "comment": task.get("comment", ""),
        "validation": validation,
    }


def _apply_contract_extensions(payload, layer, task, config):
    capabilities = contract_capabilities(config)
    farm = task.get("farm") or {}

    pool_field = capabilities.get("layer_pool_ids_field")
    if pool_field:
        layer[pool_field] = list(
            task.get("effective_pool_ids")
            or farm.get("effective_pool_ids")
            or []
        )

    suspended_field = capabilities.get("job_start_suspended_field")
    if suspended_field:
        payload[suspended_field] = bool(
            task.get("start_suspended", False)
        )

    machine_limit_field = capabilities.get("job_machine_limit_field")
    if machine_limit_field:
        payload[machine_limit_field] = _integer(
            task.get("machine_limit"),
            0,
            minimum=0,
        )

    dependencies_field = capabilities.get("job_dependencies_field")
    if dependencies_field:
        payload[dependencies_field] = list(
            task.get("job_dependencies") or []
        )


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
    user = _text(
        task.get("user") or getpass.getuser(),
        maximum=64,
        default="maya_user",
    ) or "maya_user"
    scene_path = _absolute_path(task.get("scene_path"))
    project_path = _absolute_path(task.get("project_path"))
    output_path = _absolute_path(task.get("output_path"))

    if not project:
        raise PayloadError("Project is required by the RenderHive API.")
    if not visible_name:
        raise PayloadError("Job name is required by the RenderHive API.")
    if not scene_path:
        raise PayloadError("Scene path is required by the RenderHive API.")
    if not project_path:
        raise PayloadError("Project path is required for Maya rendering.")
    if not output_path:
        raise PayloadError("Output path is required by the RenderHive API.")

    frame_range = build_frame_range(task)

    log_directory = os.path.join(output_path, "_renderhive_logs")
    try:
        if not os.path.isdir(log_directory):
            os.makedirs(log_directory)
    except Exception:
        # Shared storage may be mounted only on workers. The API requires the
        # absolute path, but local creation is not mandatory for submission.
        pass

    farm = task.get("farm") or {}
    effective_pool_names = list(
        task.get("effective_pool_names")
        or farm.get("effective_pool_names")
        or []
    )
    tags = []
    if bool(config.get("maya", {}).get("use_pool_as_tag", True)):
        for pool_name in effective_pool_names:
            clean_name = _text(pool_name, maximum=64)
            if clean_name and clean_name not in tags:
                tags.append(clean_name)

    min_ram_gb = _integer(
        task.get("minimum_ram_gb"),
        0,
        minimum=0,
    )
    min_vram_gb = _integer(
        task.get("minimum_vram_gb"),
        0,
        minimum=0,
    )
    timeout_minutes = _integer(
        task.get("task_timeout_minutes"),
        0,
        minimum=0,
    )

    layer_name = _text(
        config.get("maya", {}).get("layer_name"),
        maximum=256,
        default="beauty",
    ) or "beauty"

    task_for_command = dict(task)
    task_for_command["scene_path"] = scene_path
    task_for_command["project_path"] = project_path
    task_for_command["output_path"] = output_path

    layer = {
        "name": layer_name,
        "layer_type": "RENDER",
        "command": build_maya_command(task_for_command, config),
        "frame_range": frame_range,
        "chunk_size": _integer(task.get("chunk_size"), 1, minimum=1),
        "min_cores": _integer(task.get("minimum_cores"), 0, minimum=0),
        "min_memory_mb": min_ram_gb * 1024,
        "min_gpus": 1 if min_vram_gb > 0 else 0,
        "tags": tags,
        "scene_path": scene_path,
        "scene_info": _scene_info(task_for_command, config),
        "env": {
            "MAYA_PROJECT": project_path,
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
        "priority": _integer(
            task.get("priority"),
            50,
            minimum=1,
            maximum=100,
        ),
        "log_directory": log_directory,
        "max_tasks_per_worker": _integer(
            task.get("concurrent_tasks"),
            1,
            minimum=0,
        ),
        "layers": [layer],
    }

    _apply_contract_extensions(payload, layer, task, config)
    validate_job_request(payload)
    return payload


def validate_job_request(payload):
    errors = []

    if not isinstance(payload, dict):
        raise PayloadError("Job request must be a dictionary.")

    for field in ("project", "user", "log_directory", "layers"):
        if not payload.get(field):
            errors.append("Missing required JobCreate field: {}".format(field))

    priority = payload.get("priority")
    if priority is not None and not 1 <= int(priority) <= 100:
        errors.append("Job priority must be between 1 and 100.")

    layers = payload.get("layers") or []
    if not isinstance(layers, list) or not layers:
        errors.append("JobCreate.layers must contain at least one layer.")
    else:
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                errors.append("Layer {} must be a dictionary.".format(index))
                continue

            for field in ("name", "command", "frame_range"):
                if not layer.get(field):
                    errors.append(
                        "Layer {} is missing required field: {}".format(
                            index,
                            field,
                        )
                    )

            if int(layer.get("chunk_size", 0)) < 0:
                errors.append(
                    "Layer {} chunk_size cannot be negative.".format(index)
                )

    if errors:
        raise PayloadError("\n".join(errors))

    return True
