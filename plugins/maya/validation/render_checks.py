from __future__ import print_function

import os
import re

import maya.cmds as cmds


CATEGORY = "Render"

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5",
    "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
    "LPT6", "LPT7", "LPT8", "LPT9",
}

ARNOLD_ALLOWED_FORMATS = {
    "exr",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
}


def make_result(
    severity,
    code,
    message,
    node="",
    fixable=False,
    data=None
):
    return {
        "severity": severity,
        "category": CATEGORY,
        "code": code,
        "node": node or "",
        "message": message,
        "fixable": bool(fixable),
        "data": data or {},
    }


def safe_get_attr(node, attribute, default=None, as_string=False):
    plug = "{}.{}".format(node, attribute)

    if not cmds.objExists(plug):
        return default

    try:
        if as_string:
            return cmds.getAttr(plug, asString=True)

        return cmds.getAttr(plug)

    except Exception:
        return default


def get_context_value(context, key, fallback=None):
    value = context.get(key)

    if value is None or value == "":
        return fallback

    return value


def get_scene_renderer():
    return safe_get_attr(
        "defaultRenderGlobals",
        "currentRenderer",
        default=""
    ) or ""


def check_renderer(context):
    results = []

    requested_renderer = get_context_value(
        context,
        "renderer",
        get_scene_renderer()
    )

    scene_renderer = get_scene_renderer()

    if not requested_renderer:
        results.append(make_result(
            "ERROR",
            "RENDERER_NOT_SELECTED",
            "No renderer is selected."
        ))
        return results

    if str(requested_renderer).lower() != "arnold":
        results.append(make_result(
            "ERROR",
            "ARNOLD_REQUIRED",
            "RenderHive Maya currently supports Arnold only.",
            fixable=True,
            data={
                "task_renderer": requested_renderer,
                "scene_renderer": scene_renderer,
            }
        ))
        return results

    if scene_renderer and str(scene_renderer).lower() != "arnold":
        results.append(make_result(
            "ERROR",
            "SCENE_RENDERER_NOT_ARNOLD",
            (
                "The Maya scene renderer is '{}'. RenderHive Maya requires Arnold."
            ).format(scene_renderer),
            fixable=True,
            data={
                "task_renderer": "arnold",
                "scene_renderer": scene_renderer,
            }
        ))

    if requested_renderer == "arnold":
        try:
            registered = bool(
                cmds.pluginInfo(
                    "mtoa",
                    query=True,
                    registered=True
                )
            )
        except Exception:
            registered = False

        try:
            loaded = bool(
                cmds.pluginInfo(
                    "mtoa",
                    query=True,
                    loaded=True
                )
            )
        except Exception:
            loaded = False

        if not registered:
            results.append(make_result(
                "ERROR",
                "ARNOLD_NOT_AVAILABLE",
                "Arnold for Maya (mtoa) is not installed on this machine."
            ))

        elif not loaded:
            results.append(make_result(
                "ERROR",
                "ARNOLD_NOT_LOADED",
                "Arnold is selected but the mtoa plugin is not loaded.",
                fixable=True
            ))

        else:
            results.append(make_result(
                "PASSED",
                "RENDERER_AVAILABLE",
                "Arnold and mtoa are available."
            ))

    return results


def check_frame_range(context):
    results = []

    start = get_context_value(
        context,
        "frame_start",
        safe_get_attr(
            "defaultRenderGlobals",
            "startFrame",
            default=1
        )
    )

    end = get_context_value(
        context,
        "frame_end",
        safe_get_attr(
            "defaultRenderGlobals",
            "endFrame",
            default=1
        )
    )

    step = get_context_value(
        context,
        "frame_step",
        safe_get_attr(
            "defaultRenderGlobals",
            "byFrameStep",
            default=1
        )
    )

    try:
        start = int(start)
        end = int(end)
        step = float(step)

    except Exception:
        results.append(make_result(
            "ERROR",
            "FRAME_RANGE_INVALID_TYPE",
            "Frame range values must be numeric."
        ))
        return results

    if start > end:
        results.append(make_result(
            "ERROR",
            "FRAME_RANGE_REVERSED",
            "Frame start cannot be greater than frame end.",
            data={
                "frame_start": start,
                "frame_end": end,
            }
        ))

    elif step <= 0:
        results.append(make_result(
            "ERROR",
            "FRAME_STEP_INVALID",
            "Frame step must be greater than zero.",
            data={"frame_step": step}
        ))

    else:
        results.append(make_result(
            "PASSED",
            "FRAME_RANGE_VALID",
            "Frame range is valid: {} to {} by {}.".format(
                start,
                end,
                step
            ),
            data={
                "frame_start": start,
                "frame_end": end,
                "frame_step": step,
            }
        ))

    animation_enabled = bool(
        safe_get_attr(
            "defaultRenderGlobals",
            "animation",
            default=False
        )
    )

    if end > start and not animation_enabled:
        results.append(make_result(
            "WARNING",
            "SCENE_ANIMATION_DISABLED",
            (
                "The task contains multiple frames, but Maya's Animation "
                "render setting is disabled. Command-line frame overrides "
                "may still work."
            )
        ))

    return results


def check_resolution(context):
    results = []

    width = get_context_value(
        context,
        "width",
        safe_get_attr(
            "defaultResolution",
            "width",
            default=0
        )
    )

    height = get_context_value(
        context,
        "height",
        safe_get_attr(
            "defaultResolution",
            "height",
            default=0
        )
    )

    pixel_aspect = safe_get_attr(
        "defaultResolution",
        "pixelAspect",
        default=1.0
    )

    try:
        width = int(width)
        height = int(height)
        pixel_aspect = float(pixel_aspect)

    except Exception:
        results.append(make_result(
            "ERROR",
            "RESOLUTION_INVALID_TYPE",
            "Resolution values must be numeric."
        ))
        return results

    if width <= 0 or height <= 0:
        results.append(make_result(
            "ERROR",
            "RESOLUTION_INVALID",
            "Render resolution must be greater than zero.",
            data={
                "width": width,
                "height": height,
            }
        ))

    elif width > 16384 or height > 16384:
        results.append(make_result(
            "WARNING",
            "RESOLUTION_VERY_HIGH",
            (
                "Render resolution is very high: {} x {}. "
                "This may require significant memory."
            ).format(width, height),
            data={
                "width": width,
                "height": height,
            }
        ))

    else:
        results.append(make_result(
            "PASSED",
            "RESOLUTION_VALID",
            "Render resolution is valid: {} x {}.".format(
                width,
                height
            ),
            data={
                "width": width,
                "height": height,
            }
        ))

    if pixel_aspect <= 0:
        results.append(make_result(
            "ERROR",
            "PIXEL_ASPECT_INVALID",
            "Pixel aspect ratio must be greater than zero.",
            data={"pixel_aspect": pixel_aspect}
        ))

    return results


def check_camera(context):
    results = []

    camera = get_context_value(
        context,
        "camera",
        ""
    )

    if not camera:
        results.append(make_result(
            "ERROR",
            "RENDER_CAMERA_EMPTY",
            "No render camera is selected."
        ))
        return results

    if not cmds.objExists(camera):
        results.append(make_result(
            "ERROR",
            "RENDER_CAMERA_MISSING",
            "Selected render camera does not exist: {}.".format(
                camera
            ),
            node=camera
        ))
        return results

    shapes = cmds.listRelatives(
        camera,
        shapes=True,
        type="camera",
        fullPath=True
    ) or []

    if not shapes:
        results.append(make_result(
            "ERROR",
            "RENDER_CAMERA_INVALID",
            "Selected node is not a valid camera: {}.".format(
                camera
            ),
            node=camera
        ))
        return results

    shape = shapes[0]

    renderable = bool(
        safe_get_attr(
            shape,
            "renderable",
            default=False
        )
    )

    if not renderable:
        results.append(make_result(
            "WARNING",
            "RENDER_CAMERA_NOT_RENDERABLE",
            "Selected camera is not marked renderable: {}.".format(
                camera
            ),
            node=camera,
            fixable=True
        ))

    else:
        results.append(make_result(
            "PASSED",
            "RENDER_CAMERA_VALID",
            "Render camera is valid and renderable: {}.".format(
                camera
            ),
            node=camera
        ))

    near_clip = safe_get_attr(
        shape,
        "nearClipPlane",
        default=0.1
    )

    far_clip = safe_get_attr(
        shape,
        "farClipPlane",
        default=10000.0
    )

    try:
        near_clip = float(near_clip)
        far_clip = float(far_clip)

        if near_clip <= 0 or far_clip <= near_clip:
            results.append(make_result(
                "ERROR",
                "CAMERA_CLIPPING_INVALID",
                (
                    "Camera clipping planes are invalid. Near: {}, Far: {}."
                ).format(
                    near_clip,
                    far_clip
                ),
                node=camera
            ))

    except Exception:
        pass

    return results


def check_output_path(context):
    results = []

    output_path = get_context_value(
        context,
        "output_path",
        ""
    )

    if not output_path:
        results.append(make_result(
            "ERROR",
            "OUTPUT_PATH_EMPTY",
            "Render output path is empty."
        ))
        return results

    output_path = os.path.abspath(
        os.path.expandvars(
            os.path.expanduser(output_path)
        )
    )

    if not os.path.exists(output_path):
        parent = os.path.dirname(output_path)

        if parent and os.path.isdir(parent) and os.access(parent, os.W_OK):
            results.append(make_result(
                "WARNING",
                "OUTPUT_FOLDER_MISSING",
                "Output folder does not exist: {}.".format(
                    output_path
                ),
                fixable=True,
                data={"path": output_path}
            ))

        else:
            results.append(make_result(
                "ERROR",
                "OUTPUT_PARENT_NOT_WRITABLE",
                (
                    "Output folder does not exist and its parent is not "
                    "writable: {}."
                ).format(output_path),
                data={"path": output_path}
            ))

        return results

    if not os.path.isdir(output_path):
        results.append(make_result(
            "ERROR",
            "OUTPUT_PATH_NOT_DIRECTORY",
            "Output path is not a folder: {}.".format(
                output_path
            ),
            data={"path": output_path}
        ))

    elif not os.access(output_path, os.W_OK):
        results.append(make_result(
            "ERROR",
            "OUTPUT_FOLDER_NOT_WRITABLE",
            "Output folder is not writable: {}.".format(
                output_path
            ),
            data={"path": output_path}
        ))

    else:
        results.append(make_result(
            "PASSED",
            "OUTPUT_FOLDER_VALID",
            "Output folder exists and is writable.",
            data={"path": output_path}
        ))

    project_path = get_context_value(context, "project_path", "")
    if project_path:
        project_path = os.path.abspath(
            os.path.expandvars(os.path.expanduser(str(project_path)))
        )
        try:
            inside_project = os.path.commonpath([output_path, project_path]) == project_path
        except (ValueError, OSError):
            inside_project = False

        if inside_project:
            results.append(make_result(
                "PASSED",
                "OUTPUT_INSIDE_PROJECT",
                "Render output is inside the Maya project.",
                data={"output_path": output_path, "project_path": project_path},
            ))
        else:
            results.append(make_result(
                "WARNING",
                "OUTPUT_OUTSIDE_PROJECT",
                "Render output is outside the Maya project. Ensure the farm can access this path.",
                data={"output_path": output_path, "project_path": project_path},
            ))

    return results


def check_output_name(context):
    results = []

    image_name = get_context_value(
        context,
        "image_name",
        safe_get_attr(
            "defaultRenderGlobals",
            "imageFilePrefix",
            default=""
        )
    )

    if not image_name:
        results.append(make_result(
            "ERROR",
            "OUTPUT_NAME_EMPTY",
            "Image name or output prefix is empty."
        ))
        return results

    image_name = str(image_name)

    invalid_characters = re.findall(
        r'[<>:"/\\|?*]',
        image_name
    )

    if invalid_characters:
        results.append(make_result(
            "ERROR",
            "OUTPUT_NAME_INVALID_CHARACTERS",
            (
                "Image name contains invalid path characters: {}."
            ).format(
                "".join(sorted(set(invalid_characters)))
            ),
            data={"image_name": image_name}
        ))

    if image_name != image_name.strip():
        results.append(make_result(
            "WARNING",
            "OUTPUT_NAME_WHITESPACE",
            "Image name has leading or trailing whitespace.",
            data={"image_name": image_name}
        ))

    root_name = image_name.split(".")[0].upper()

    if root_name in WINDOWS_RESERVED_NAMES:
        results.append(make_result(
            "ERROR",
            "OUTPUT_NAME_RESERVED",
            "Image name is reserved by Windows: {}.".format(
                image_name
            ),
            data={"image_name": image_name}
        ))

    if not invalid_characters and root_name not in WINDOWS_RESERVED_NAMES:
        results.append(make_result(
            "PASSED",
            "OUTPUT_NAME_VALID",
            "Image name is valid: {}.".format(
                image_name
            )
        ))

    return results


def check_image_format(context):
    results = []

    renderer = get_context_value(
        context,
        "renderer",
        get_scene_renderer()
    )

    image_format = get_context_value(
        context,
        "image_format",
        ""
    )

    image_format = str(image_format).lower().lstrip(".")

    if not image_format:
        results.append(make_result(
            "ERROR",
            "IMAGE_FORMAT_EMPTY",
            "No output image format is selected."
        ))
        return results

    allowed = ARNOLD_ALLOWED_FORMATS

    if image_format not in allowed:
        results.append(make_result(
            "ERROR",
            "IMAGE_FORMAT_UNSUPPORTED",
            (
                "Image format '{}' is not supported by the selected "
                "renderer validation profile."
            ).format(image_format),
            data={
                "renderer": renderer,
                "image_format": image_format,
            }
        ))

    else:
        results.append(make_result(
            "PASSED",
            "IMAGE_FORMAT_VALID",
            "Image format is valid: {}.".format(
                image_format
            )
        ))

    if image_format in {"jpg", "jpeg"}:
        results.append(make_result(
            "WARNING",
            "LOSSY_OUTPUT_FORMAT",
            (
                "JPEG is a lossy format. PNG or EXR is recommended for "
                "production rendering."
            )
        ))

    if renderer == "arnold" and image_format == "exr":
        results.append(make_result(
            "INFO",
            "PRODUCTION_FORMAT_SELECTED",
            "EXR is selected for Arnold production output."
        ))

    if renderer == "arnold" and cmds.objExists("defaultArnoldDriver.ai_translator"):
        driver_format = safe_get_attr(
            "defaultArnoldDriver",
            "ai_translator",
            default="",
            as_string=True
        )

        if driver_format:
            normalized_driver = str(driver_format).lower()

            aliases = {
                "jpeg": "jpg",
                "tiff": "tif",
            }

            task_format = aliases.get(
                image_format,
                image_format
            )

            scene_format = aliases.get(
                normalized_driver,
                normalized_driver
            )

            if task_format != scene_format:
                results.append(make_result(
                    "WARNING",
                    "ARNOLD_DRIVER_FORMAT_MISMATCH",
                    (
                        "Task image format is '{}' while the Arnold driver "
                        "is set to '{}'. The worker may override it."
                    ).format(
                        image_format,
                        driver_format
                    )
                ))

    return results


def check_frame_padding(context):
    results = []

    padding = get_context_value(
        context,
        "frame_padding",
        safe_get_attr(
            "defaultRenderGlobals",
            "extensionPadding",
            default=4
        )
    )

    try:
        padding = int(padding)

    except Exception:
        results.append(make_result(
            "ERROR",
            "FRAME_PADDING_INVALID_TYPE",
            "Frame padding must be an integer."
        ))
        return results

    if padding < 1:
        results.append(make_result(
            "ERROR",
            "FRAME_PADDING_TOO_LOW",
            "Frame padding must be at least 1."
        ))

    elif padding > 8:
        results.append(make_result(
            "WARNING",
            "FRAME_PADDING_VERY_HIGH",
            "Frame padding is unusually high: {}.".format(
                padding
            )
        ))

    else:
        results.append(make_result(
            "PASSED",
            "FRAME_PADDING_VALID",
            "Frame padding is valid: {}.".format(
                padding
            )
        ))

    return results


def check_render_layers(context):
    results = []

    selected_layers = context.get("render_layers")
    missing_names = [
        str(value or "").strip()
        for value in context.get("render_layer_missing_names") or []
        if str(value or "").strip()
    ]

    if isinstance(selected_layers, list):
        names = []
        disabled = []
        for layer in selected_layers:
            if isinstance(layer, dict):
                name = str(layer.get("name") or "").strip()
                renderable = bool(layer.get("renderable", True))
            else:
                name = str(layer or "").strip()
                renderable = True

            if not name:
                results.append(make_result(
                    "ERROR",
                    "RENDER_LAYER_NAME_EMPTY",
                    "A selected render layer has no Maya layer name.",
                ))
                continue
            if name in names:
                results.append(make_result(
                    "ERROR",
                    "RENDER_LAYER_DUPLICATE",
                    "Render layer is selected more than once: {}.".format(name),
                    data={"render_layer": name},
                ))
                continue
            names.append(name)
            if not renderable:
                disabled.append(name)

        if missing_names:
            results.append(make_result(
                "ERROR",
                "RENDER_LAYER_MISSING",
                "Selected render layer(s) no longer exist: {}.".format(", ".join(missing_names)),
                data={"render_layers": missing_names},
            ))

        if not names:
            results.append(make_result(
                "ERROR",
                "NO_RENDER_LAYER_SELECTED",
                "Select at least one Maya render layer for submission.",
            ))
        else:
            results.append(make_result(
                "PASSED",
                "RENDER_LAYER_SELECTION_VALID",
                "{} render layer(s) selected for submission.".format(len(names)),
                data={"render_layers": names},
            ))

        if disabled:
            results.append(make_result(
                "INFO",
                "SELECTED_LAYER_DISABLED_IN_SCENE",
                "Selected layer(s) are disabled in Maya but were explicitly selected in RenderHive: {}.".format(
                    ", ".join(disabled)
                ),
                data={"render_layers": disabled},
            ))
        return results

    # Compatibility path for callers that do not provide RenderHive's explicit
    # layer selection in the validation context.
    layers = cmds.ls(type="renderLayer") or []
    renderable_layers = [
        layer
        for layer in layers
        if safe_get_attr(layer, "renderable", default=False)
    ]

    if not layers:
        results.append(make_result(
            "WARNING",
            "NO_RENDER_LAYERS_FOUND",
            "No Maya render layers were found.",
        ))
    elif not renderable_layers:
        results.append(make_result(
            "ERROR",
            "NO_RENDERABLE_LAYER",
            "No render layer is enabled for rendering.",
        ))
    else:
        results.append(make_result(
            "PASSED",
            "RENDER_LAYER_AVAILABLE",
            "{} renderable layer(s) were found.".format(len(renderable_layers)),
            data={"renderable_layers": renderable_layers},
        ))

    return results


def get_aov_name(aov_node):
    value = safe_get_attr(
        aov_node,
        "name",
        default=""
    )

    return str(value or "").strip()


def get_connected_aov_drivers(aov_node):
    drivers = []

    try:
        drivers.extend(
            cmds.listConnections(
                aov_node,
                source=False,
                destination=True,
                type="aiAOVDriver"
            ) or []
        )
    except Exception:
        pass

    try:
        drivers.extend(
            cmds.listConnections(
                aov_node + ".outputs",
                source=False,
                destination=True,
                type="aiAOVDriver"
            ) or []
        )
    except Exception:
        pass

    return sorted(set(drivers))


def check_arnold_aovs(context):
    results = []

    renderer = get_context_value(
        context,
        "renderer",
        get_scene_renderer()
    )

    if renderer != "arnold":
        results.append(make_result(
            "INFO",
            "ARNOLD_AOV_CHECK_SKIPPED",
            "Arnold AOV validation was skipped."
        ))
        return results

    aov_nodes = cmds.ls(type="aiAOV") or []

    if not aov_nodes:
        results.append(make_result(
            "INFO",
            "NO_ARNOLD_AOVS",
            "No Arnold AOV nodes were found."
        ))
        return results

    names = {}
    empty_names = []
    missing_drivers = []

    for aov_node in aov_nodes:
        enabled = safe_get_attr(
            aov_node,
            "enabled",
            default=True
        )

        if enabled is False:
            continue

        aov_name = get_aov_name(aov_node)

        if not aov_name:
            empty_names.append(aov_node)
            continue

        names.setdefault(
            aov_name.lower(),
            []
        ).append(aov_node)

        drivers = get_connected_aov_drivers(
            aov_node
        )

        if not drivers and cmds.objExists("defaultArnoldDriver"):
            drivers = ["defaultArnoldDriver"]

        if not drivers:
            missing_drivers.append({
                "node": aov_node,
                "name": aov_name,
            })

    duplicate_names = {
        name: nodes
        for name, nodes in names.items()
        if len(nodes) > 1
    }

    for aov_node in empty_names:
        results.append(make_result(
            "ERROR",
            "AOV_NAME_EMPTY",
            "Enabled Arnold AOV has an empty name.",
            node=aov_node
        ))

    for name, nodes in duplicate_names.items():
        results.append(make_result(
            "ERROR",
            "AOV_NAME_DUPLICATE",
            "Duplicate Arnold AOV name '{}': {}.".format(
                name,
                ", ".join(nodes)
            ),
            node=nodes[0],
            data={
                "name": name,
                "nodes": nodes,
            }
        ))

    for item in missing_drivers:
        results.append(make_result(
            "WARNING",
            "AOV_DRIVER_MISSING",
            "Arnold AOV has no detected output driver: {}.".format(
                item["name"]
            ),
            node=item["node"],
            data=item
        ))

    if not empty_names and not duplicate_names and not missing_drivers:
        results.append(make_result(
            "PASSED",
            "ARNOLD_AOVS_VALID",
            "{} enabled Arnold AOV(s) passed validation.".format(
                len(aov_nodes)
            )
        ))

    return results


def check_arnold_sampling(context):
    results = []

    renderer = get_context_value(
        context,
        "renderer",
        get_scene_renderer()
    )

    if renderer != "arnold":
        results.append(make_result(
            "INFO",
            "ARNOLD_SAMPLING_CHECK_SKIPPED",
            "Arnold sampling validation was skipped."
        ))
        return results

    options = "defaultArnoldRenderOptions"

    if not cmds.objExists(options):
        results.append(make_result(
            "ERROR",
            "ARNOLD_OPTIONS_MISSING",
            "defaultArnoldRenderOptions does not exist."
        ))
        return results

    sample_attributes = {
        "AASamples": {
            "label": "Camera AA",
            "low_warning": 1,
            "high_warning": 8,
        },
        "GIDiffuseSamples": {
            "label": "Diffuse",
            "low_warning": None,
            "high_warning": 6,
        },
        "GISpecularSamples": {
            "label": "Specular",
            "low_warning": None,
            "high_warning": 6,
        },
        "GITransmissionSamples": {
            "label": "Transmission",
            "low_warning": None,
            "high_warning": 6,
        },
        "GISssSamples": {
            "label": "SSS",
            "low_warning": None,
            "high_warning": 6,
        },
        "GIVolumeSamples": {
            "label": "Volume",
            "low_warning": None,
            "high_warning": 6,
        },
    }

    found_any = False
    issues = 0

    for attribute, rule in sample_attributes.items():
        value = safe_get_attr(
            options,
            attribute,
            default=None
        )

        if value is None:
            continue

        found_any = True

        try:
            value = int(value)
        except Exception:
            continue

        if value < 0:
            issues += 1

            results.append(make_result(
                "ERROR",
                "ARNOLD_SAMPLE_NEGATIVE",
                "{} samples cannot be negative: {}.".format(
                    rule["label"],
                    value
                ),
                node=options
            ))

        low_warning = rule["low_warning"]

        if (
            low_warning is not None
            and value <= low_warning
        ):
            issues += 1

            results.append(make_result(
                "WARNING",
                "ARNOLD_SAMPLES_LOW",
                (
                    "{} samples are very low ({}). Preview quality may be noisy."
                ).format(
                    rule["label"],
                    value
                ),
                node=options
            ))

        if value > rule["high_warning"]:
            issues += 1

            results.append(make_result(
                "WARNING",
                "ARNOLD_SAMPLES_HIGH",
                (
                    "{} samples are high ({}). Render time may increase."
                ).format(
                    rule["label"],
                    value
                ),
                node=options
            ))

    if found_any and issues == 0:
        results.append(make_result(
            "PASSED",
            "ARNOLD_SAMPLING_REASONABLE",
            "Arnold sampling values are within reasonable validation limits."
        ))

    elif not found_any:
        results.append(make_result(
            "INFO",
            "ARNOLD_SAMPLING_NOT_FOUND",
            "Arnold sampling attributes could not be read."
        ))

    render_device = safe_get_attr(
        options,
        "renderDevice",
        default=None,
        as_string=True
    )

    if render_device:
        results.append(make_result(
            "INFO",
            "ARNOLD_RENDER_DEVICE",
            "Arnold render device: {}.".format(
                render_device
            ),
            node=options
        ))

    motion_blur = safe_get_attr(
        options,
        "motion_blur_enable",
        default=False
    )

    if motion_blur:
        results.append(make_result(
            "INFO",
            "ARNOLD_MOTION_BLUR_ENABLED",
            (
                "Arnold motion blur is enabled. Confirm that the worker "
                "frame range and shutter settings are intentional."
            ),
            node=options
        ))

    return results


def check_render_region(context):
    results = []

    region_attributes = [
        (
            "defaultRenderGlobals",
            "useRenderRegion"
        ),
        (
            "defaultRenderGlobals",
            "enableDefaultLight"
        ),
    ]

    region_enabled = False

    node, attribute = region_attributes[0]

    if cmds.objExists(
        "{}.{}".format(node, attribute)
    ):
        region_enabled = bool(
            safe_get_attr(
                node,
                attribute,
                default=False
            )
        )

    if region_enabled:
        results.append(make_result(
            "WARNING",
            "RENDER_REGION_ENABLED",
            (
                "Render Region is enabled. Full-frame farm renders may be "
                "cropped."
            ),
            node="defaultRenderGlobals",
            fixable=True
        ))

    else:
        results.append(make_result(
            "PASSED",
            "RENDER_REGION_DISABLED",
            "Render Region is disabled."
        ))

    return results


def run_checks(context):
    results = []

    checks = [
        check_renderer,
        check_frame_range,
        check_resolution,
        check_camera,
        check_output_path,
        check_output_name,
        check_image_format,
        check_frame_padding,
        check_render_layers,
        check_arnold_aovs,
        check_arnold_sampling,
        check_render_region,
    ]

    for check in checks:
        try:
            check_results = check(context)

            if check_results:
                results.extend(check_results)

        except Exception as error:
            results.append(make_result(
                "ERROR",
                "RENDER_CHECK_FAILED",
                "Check '{}' failed: {}".format(
                    check.__name__,
                    error
                )
            ))

    return results
