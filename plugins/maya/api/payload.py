from __future__ import absolute_import

import base64
import getpass
import ntpath
import os
import platform
import re
import uuid

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

    if start == end:
        return str(start)

    min_frame = min(start, end)
    max_frame = max(start, end)

    if step == 1:
        return "{}-{}".format(min_frame, max_frame)
    return "{}-{}x{}".format(min_frame, max_frame, step)


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

    renderer = (_text(task.get("renderer"), default="arnold") or "arnold").lower()
    if renderer != "arnold":
        raise PayloadError(
            "RenderHive Maya currently supports Arnold only; got renderer '{}'.".format(renderer)
        )
    camera = _text(task.get("camera"))
    render_layer = _text(
        task.get("render_layer") or task.get("render_layer_name")
    )
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

    # Render Setup layers are submitted as separate backend layers. The master
    # layer intentionally omits -rl because that is Maya's native default
    # render context; named Render Setup/legacy layers are selected explicitly.
    if render_layer and render_layer not in (
        "defaultRenderLayer",
        "masterLayer",
        "Master Layer",
    ):
        parts.extend(["-rl", _quote(render_layer)])

    image_name = _text(task.get("image_name"))
    image_format = (_text(task.get("image_format"), default="exr") or "exr").lower()
    if image_format == "jpg":
        image_format = "jpeg"
    padding = _integer(task.get("frame_padding"), 4, minimum=1)

    py_script = [
        "import maya.cmds as cmds",
        "cmds.loadPlugin('mtoa', quiet=True)",
        "cmds.setAttr('defaultRenderGlobals.currentRenderer', 'arnold', type='string')",
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

    parts.append(_quote(scene_path))
    return " ".join(parts)


def _unique_uuid_strings(values, field_name):
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        try:
            text = str(uuid.UUID(text))
        except Exception:
            raise PayloadError(
                "{} contains an invalid UUID: {}".format(field_name, text)
            )
        if text not in result:
            result.append(text)
    return result


def _pool_submission_fields(task, config):
    capabilities = contract_capabilities(config)
    if not capabilities.get("job_pool_targeting", False):
        return {}

    farm = task.get("farm") or {}
    strategy = str(
        farm.get("pool_strategy", task.get("pool_strategy", "all"))
        or "all"
    ).strip().lower()

    selected = _unique_uuid_strings(
        task.get("selected_pool_ids")
        or farm.get("selected_pool_ids")
        or [],
        "selected_pool_ids",
    )
    excluded = _unique_uuid_strings(
        task.get("excluded_pool_ids")
        or farm.get("excluded_pool_ids")
        or [],
        "excluded_pool_ids",
    )

    overlap = sorted(set(selected).intersection(excluded))
    if overlap:
        raise PayloadError(
            "Pools cannot be both included and excluded: {}".format(
                ", ".join(overlap)
            )
        )

    if strategy == "selected":
        if not selected:
            raise PayloadError(
                "Selected Pools Only requires at least one backend pool."
            )
        return {"included_pools": selected, "excluded_pools": []}

    if strategy == "all_except":
        return {"included_pools": [], "excluded_pools": excluded}

    return {"included_pools": [], "excluded_pools": []}


def _dependency_specs(task, config):
    capabilities = contract_capabilities(config)
    if not capabilities.get("job_dependencies", False):
        return []

    raw_values = task.get("job_dependencies") or []
    result = []

    for value in raw_values:
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
            raise PayloadError(
                "Job dependency contains an invalid UUID: {}".format(parent_job)
            )

        item = {
            "type": dep_type,
            "parent_job": parent_job,
        }
        if parent_layer not in (None, ""):
            item["parent_layer"] = _text(parent_layer, maximum=256)
        if dep_layer not in (None, ""):
            item["dep_layer"] = _text(dep_layer, maximum=256)

        if item not in result:
            result.append(item)

    return result


def _worker_targeting_info(task, config):
    farm = task.get("farm") or {}
    capabilities = contract_capabilities(config)
    effective_ids = list(
        task.get("effective_pool_ids")
        or farm.get("effective_pool_ids")
        or []
    )
    if capabilities.get("job_pool_targeting", False):
        enforcement = "job_pool_fields"
        api_field = "included_pools/excluded_pools"
    else:
        enforcement = "metadata_only"
        api_field = ""

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
        "enforcement": enforcement,
        "api_field": api_field,
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
        "render_layer": task.get("render_layer", ""),
        "render_layer_display_name": task.get("render_layer_display_name", ""),
        "render_layer_source": task.get("render_layer_source", ""),
        "render_layer_is_default": bool(task.get("render_layer_is_default", False)),
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
        "worker_targeting": _worker_targeting_info(task, config),
        "resource_requirements": {
            "minimum_cores": _integer(
                task.get("minimum_cores"),
                0,
                minimum=0,
            ),
            "minimum_ram_gb": _integer(
                task.get("minimum_ram_gb"),
                0,
                minimum=0,
            ),
            "minimum_gpus": _integer(
                task.get("minimum_gpus"),
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

    # RenderHive API 0.2.0 owns pool targeting at the Job level. Pool names are
    # no longer smuggled through Layer.tags, which could incorrectly require
    # workers to carry tags that merely happen to match pool names.
    payload.update(_pool_submission_fields(task, config))

    if capabilities.get("job_dependencies", False):
        payload["dependencies"] = _dependency_specs(task, config)


def _safe_layer_segment(value):
    text = _text(value, maximum=128, default="layer") or "layer"
    text = re.sub(r'[<>:"/\\|?*]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return text or "layer"


def _layer_task_value(spec, task, key):
    if isinstance(spec, dict) and spec.get(key) not in (None, ""):
        return spec.get(key)
    return task.get(key)


def _build_layer_payload(
    task,
    spec,
    config,
    scene_path,
    project_path,
    output_path,
    tags,
    multi_layer=False,
    legacy_backend_layer=False,
):
    spec = dict(spec or {})
    maya_layer_name = "" if legacy_backend_layer else _text(
        spec.get("name"),
        maximum=256,
    )
    backend_layer_name = _text(
        spec.get("name"),
        maximum=256,
        default=config.get("maya", {}).get("layer_name", "beauty"),
    ) or "beauty"

    layer_task = dict(task)
    layer_task["scene_path"] = scene_path
    layer_task["project_path"] = project_path
    layer_task["output_path"] = _absolute_path(
        _layer_task_value(spec, task, "output_path") or output_path
    )
    layer_task["render_layer"] = maya_layer_name
    layer_task["render_layer_display_name"] = _text(
        spec.get("display_name"),
        maximum=256,
        default=backend_layer_name,
    )
    layer_task["render_layer_source"] = _text(
        spec.get("source"),
        maximum=64,
        default="maya",
    )
    layer_task["render_layer_is_default"] = bool(
        spec.get("is_default", maya_layer_name == "defaultRenderLayer")
    )

    override_keys = (
        "renderer",
        "camera",
        "frame_start",
        "frame_end",
        "frame_step",
        "image_name",
        "image_format",
        "frame_padding",
        "width",
        "height",
        "chunk_size",
        "minimum_cores",
        "minimum_ram_gb",
        "minimum_gpus",
        "retry_count",
        "task_timeout_minutes",
    )
    for key in override_keys:
        if spec.get(key) not in (None, ""):
            layer_task[key] = spec.get(key)

    # Explicit Maya layer selections always receive their own image namespace.
    # This prevents collisions both inside a multi-layer Job and across separate
    # submissions of individual layers. Legacy callers without render_layers
    # retain the historical un-namespaced output behavior.
    if not legacy_backend_layer and spec.get("image_name") in (None, ""):
        base_name = _text(task.get("image_name"), default="render") or "render"
        layer_task["image_name"] = "{}/{}".format(
            _safe_layer_segment(backend_layer_name),
            base_name,
        )

    min_ram_gb = _integer(
        layer_task.get("minimum_ram_gb"),
        0,
        minimum=0,
    )
    timeout_minutes = _integer(
        layer_task.get("task_timeout_minutes"),
        0,
        minimum=0,
    )

    env = {
        "MAYA_PROJECT": project_path,
        "RENDERHIVE_SUBMISSION_MODE": task.get(
            "submission_mode",
            "Shared Storage",
        ),
    }
    if maya_layer_name:
        env["RENDERHIVE_MAYA_RENDER_LAYER"] = maya_layer_name
        env["RENDERHIVE_MAYA_RENDER_LAYER_SOURCE"] = layer_task.get(
            "render_layer_source",
            "maya",
        )

    return {
        "name": backend_layer_name,
        "layer_type": "RENDER",
        "command": build_maya_command(layer_task, config),
        "frame_range": build_frame_range(layer_task),
        "chunk_size": _integer(
            layer_task.get("chunk_size"),
            1,
            minimum=1,
        ),
        "min_cores": _integer(
            layer_task.get("minimum_cores"),
            0,
            minimum=0,
        ),
        "min_memory_mb": min_ram_gb * 1024,
        "min_gpus": _integer(
            layer_task.get("minimum_gpus"),
            0,
            minimum=0,
        ),
        "tags": list(tags),
        "scene_path": scene_path,
        "scene_info": _scene_info(layer_task, config),
        "env": env,
        "max_retries": _integer(
            layer_task.get("retry_count"),
            2,
            minimum=0,
        ),
        "timeout_seconds": (
            timeout_minutes * 60 if timeout_minutes else None
        ),
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

    log_directory = os.path.join(output_path, "_renderhive_logs")
    windows_style_path = bool(
        re.match(r"^[A-Za-z]:[\\/]", log_directory)
        or log_directory.startswith(("\\\\", "//"))
    )
    try:
        # Contract tests may run on Linux/macOS using Windows production paths.
        # Never materialize a literal ``C:\...`` directory in the source tree.
        if (os.name == "nt" or not windows_style_path) and not os.path.isdir(log_directory):
            os.makedirs(log_directory)
    except Exception:
        # Shared storage may be mounted only on workers. The API requires the
        # absolute path, but local creation is not mandatory for submission.
        pass

    tags = []
    for value in task.get("worker_tags") or task.get("tags") or []:
        clean_value = _text(value, maximum=64)
        if clean_value and clean_value not in tags:
            tags.append(clean_value)

    render_layer_specs = task.get("render_layers")
    legacy_backend_layer = not isinstance(render_layer_specs, list)
    if legacy_backend_layer:
        render_layer_specs = [{
            "name": _text(
                config.get("maya", {}).get("layer_name"),
                maximum=256,
                default="beauty",
            ) or "beauty",
        }]
    elif not render_layer_specs:
        raise PayloadError("At least one Maya render layer must be selected.")

    clean_specs = []
    seen_names = set()
    for raw_spec in render_layer_specs:
        if isinstance(raw_spec, dict):
            spec = dict(raw_spec)
        else:
            spec = {"name": str(raw_spec or "")}
        name = _text(spec.get("name"), maximum=256)
        if not name:
            raise PayloadError("A selected Maya render layer has no name.")
        if name in seen_names:
            raise PayloadError(
                "Maya render layer is selected more than once: {}".format(name)
            )
        seen_names.add(name)
        spec["name"] = name
        clean_specs.append(spec)

    multi_layer = len(clean_specs) > 1
    layers = [
        _build_layer_payload(
            task=task,
            spec=spec,
            config=config,
            scene_path=scene_path,
            project_path=project_path,
            output_path=output_path,
            tags=tags,
            multi_layer=multi_layer,
            legacy_backend_layer=legacy_backend_layer,
        )
        for spec in clean_specs
    ]

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
        "layers": layers,
    }

    _apply_contract_extensions(payload, layers[0], task, config)
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
        layer_names = set()
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                errors.append("Layer {} must be a dictionary.".format(index))
                continue

            layer_name = str(layer.get("name") or "").strip()
            if layer_name and layer_name in layer_names:
                errors.append(
                    "Layer name must be unique within a Job: {}".format(
                        layer_name
                    )
                )
            elif layer_name:
                layer_names.add(layer_name)

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

    included = set(payload.get("included_pools") or [])
    excluded = set(payload.get("excluded_pools") or [])
    overlap = sorted(included.intersection(excluded))
    if overlap:
        errors.append(
            "Pools cannot be both included and excluded: {}".format(
                ", ".join(overlap)
            )
        )

    dependencies = payload.get("dependencies") or []
    if not isinstance(dependencies, list):
        errors.append("JobCreate.dependencies must be a list.")
    else:
        for index, dependency in enumerate(dependencies):
            if not isinstance(dependency, dict) or not dependency.get("parent_job"):
                errors.append(
                    "Dependency {} must include parent_job.".format(index)
                )

    if errors:
        raise PayloadError("\n".join(errors))

    return True
