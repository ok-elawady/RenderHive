import glob
import math
import os
import re

import maya.cmds as cmds


CATEGORY = "Lighting"

MAYA_LIGHT_TYPES = {
    "ambientLight",
    "directionalLight",
    "pointLight",
    "spotLight",
    "areaLight",
    "volumeLight",
}

ARNOLD_LIGHT_TYPES = {
    "aiAreaLight",
    "aiSkyDomeLight",
    "aiPhotometricLight",
    "aiMeshLight",
    "aiLightPortal",
}

ALL_LIGHT_TYPES = MAYA_LIGHT_TYPES | ARNOLD_LIGHT_TYPES

ARNOLD_WARNING_TYPES = {
    "ambientLight",
    "volumeLight",
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


def normalize_path(path):
    if not path:
        return ""

    path = os.path.expandvars(path)
    path = os.path.expanduser(path)
    path = path.replace("\\", os.sep).replace("/", os.sep)

    return os.path.normpath(path)


def path_is_inside(child_path, parent_path):
    child_path = normalize_path(child_path)
    parent_path = normalize_path(parent_path)

    if not child_path or not parent_path:
        return False

    try:
        return os.path.commonpath(
            [os.path.abspath(child_path), os.path.abspath(parent_path)]
        ) == os.path.abspath(parent_path)
    except ValueError:
        return False


def get_project_path(context):
    project_path = context.get("project_path") or ""

    if not project_path:
        try:
            project_path = cmds.workspace(
                query=True,
                rootDirectory=True
            ) or ""
        except Exception:
            project_path = ""

    return normalize_path(project_path)


def get_scene_path(context):
    scene_path = context.get("scene_path") or ""

    if not scene_path:
        scene_path = cmds.file(
            query=True,
            sceneName=True
        ) or ""

    return normalize_path(scene_path)


def get_search_folders(context):
    project_path = get_project_path(context)
    scene_path = get_scene_path(context)

    folders = []

    if project_path:
        folders.extend([
            project_path,
            os.path.join(project_path, "sourceimages"),
            os.path.join(project_path, "textures"),
            os.path.join(project_path, "tex"),
            os.path.join(project_path, "maps"),
            os.path.join(project_path, "ies"),
            os.path.join(project_path, "hdr"),
            os.path.join(project_path, "hdri"),
        ])

    if scene_path:
        scene_dir = os.path.dirname(scene_path)

        folders.extend([
            scene_dir,
            os.path.join(scene_dir, "..", "sourceimages"),
            os.path.join(scene_dir, "..", "textures"),
            os.path.join(scene_dir, "..", "ies"),
            os.path.join(scene_dir, "..", "hdr"),
            os.path.join(scene_dir, "..", "hdri"),
        ])

    unique_folders = []

    for folder in folders:
        folder = os.path.abspath(normalize_path(folder))

        if folder not in unique_folders and os.path.isdir(folder):
            unique_folders.append(folder)

    return unique_folders


def tokenized_path_to_glob(path):
    pattern = path

    replacements = [
        ("<UDIM>", "*"),
        ("<udim>", "*"),
        ("%(UDIM)d", "*"),
        ("<f>", "*"),
        ("<F>", "*"),
        ("$F", "*"),
    ]

    for token, replacement in replacements:
        pattern = pattern.replace(token, replacement)

    pattern = re.sub(r"%0?\d*d", "*", pattern)
    pattern = re.sub(r"#+", "*", pattern)

    return pattern


def find_existing_path(path, context):
    if not path:
        return "", False, []

    original = path
    expanded = normalize_path(path)
    candidates = []

    if os.path.isabs(expanded):
        candidates.append(expanded)

    try:
        workspace_expanded = cmds.workspace(expandName=path)

        if workspace_expanded:
            candidates.append(
                normalize_path(workspace_expanded)
            )
    except Exception:
        pass

    project_path = get_project_path(context)

    if project_path and not os.path.isabs(expanded):
        candidates.append(
            normalize_path(os.path.join(project_path, expanded))
        )

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate, True, [candidate]

        matches = glob.glob(
            tokenized_path_to_glob(candidate)
        )

        if matches:
            return normalize_path(matches[0]), True, matches

    basename = os.path.basename(expanded)
    basename_pattern = tokenized_path_to_glob(basename)

    for folder in get_search_folders(context):
        candidate = os.path.join(folder, basename)

        if os.path.isfile(candidate):
            return normalize_path(candidate), True, [candidate]

        matches = glob.glob(
            os.path.join(folder, basename_pattern)
        )

        if matches:
            return normalize_path(matches[0]), True, matches

    for folder in get_search_folders(context):
        matches = glob.glob(
            os.path.join(folder, "**", basename_pattern),
            recursive=True
        )

        if matches:
            return normalize_path(matches[0]), True, matches

    return original, False, []


def get_attr_value(node, attr_names, default=None):
    for attr_name in attr_names:
        attr = "{}.{}".format(node, attr_name)

        if not cmds.objExists(attr):
            continue

        try:
            return cmds.getAttr(attr)
        except Exception:
            pass

    return default


def get_light_shapes():
    shapes = set()

    try:
        shapes.update(
            cmds.ls(lights=True, long=True) or []
        )
    except Exception:
        pass

    for node_type in sorted(ALL_LIGHT_TYPES):
        try:
            shapes.update(
                cmds.ls(type=node_type, long=True) or []
            )
        except Exception:
            pass

    valid_shapes = []

    for shape in shapes:
        if not cmds.objExists(shape):
            continue

        try:
            node_type = cmds.nodeType(shape)
        except Exception:
            continue

        if node_type in ALL_LIGHT_TYPES:
            valid_shapes.append(shape)

    return sorted(set(valid_shapes))


def get_light_transform(shape):
    parents = cmds.listRelatives(
        shape,
        parent=True,
        fullPath=True
    ) or []

    if parents:
        return parents[0]

    return shape


def get_hierarchy_visibility(transform):
    current = transform

    while current:
        if cmds.objExists(current + ".visibility"):
            try:
                if not cmds.getAttr(current + ".visibility"):
                    return False
            except Exception:
                pass

        parents = cmds.listRelatives(
            current,
            parent=True,
            fullPath=True
        ) or []

        current = parents[0] if parents else ""

    return True


def get_light_enabled(shape):
    enabled = get_attr_value(
        shape,
        ["enabled", "aiEnabled"],
        default=True
    )

    return bool(enabled)


def get_light_intensity(shape):
    value = get_attr_value(
        shape,
        ["intensity", "aiIntensity"],
        default=1.0
    )

    try:
        return float(value)
    except Exception:
        return 1.0


def get_light_exposure(shape):
    value = get_attr_value(
        shape,
        ["exposure", "aiExposure"],
        default=0.0
    )

    try:
        return float(value)
    except Exception:
        return 0.0


def get_effective_brightness(shape):
    intensity = get_light_intensity(shape)
    exposure = get_light_exposure(shape)

    try:
        return intensity * math.pow(2.0, exposure)
    except Exception:
        return intensity


def get_light_color(shape):
    attr = shape + ".color"

    if not cmds.objExists(attr):
        return None

    try:
        value = cmds.getAttr(attr)

        if isinstance(value, (list, tuple)) and value:
            value = value[0]

        if isinstance(value, (list, tuple)) and len(value) >= 3:
            return (
                float(value[0]),
                float(value[1]),
                float(value[2]),
            )
    except Exception:
        pass

    return None


def has_color_input(shape):
    attr = shape + ".color"

    if not cmds.objExists(attr):
        return False

    try:
        connections = cmds.listConnections(
            attr,
            source=True,
            destination=False
        ) or []

        return bool(connections)
    except Exception:
        return False


def is_effectively_active(shape):
    transform = get_light_transform(shape)

    if not get_hierarchy_visibility(transform):
        return False

    if not get_light_enabled(shape):
        return False

    if get_effective_brightness(shape) <= 0.0:
        return False

    color = get_light_color(shape)

    if color is not None and not has_color_input(shape):
        if max(color) <= 0.000001:
            return False

    return True


def get_file_nodes_from_history(node):
    history = cmds.listHistory(
        node,
        pruneDagObjects=True
    ) or []

    result = []

    for history_node in history:
        try:
            node_type = cmds.nodeType(history_node)
        except Exception:
            continue

        if node_type == "file":
            result.append({
                "node": history_node,
                "type": "file",
                "path_attr": "fileTextureName",
            })

        elif node_type == "aiImage":
            result.append({
                "node": history_node,
                "type": "aiImage",
                "path_attr": "filename",
            })

    unique = []
    seen = set()

    for item in result:
        key = (item["node"], item["path_attr"])

        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def get_node_file_path(node, attr_names):
    for attr_name in attr_names:
        attr = "{}.{}".format(node, attr_name)

        if not cmds.objExists(attr):
            continue

        try:
            value = cmds.getAttr(attr)

            if value:
                return value, attr_name
        except Exception:
            pass

    return "", ""


def check_light_presence(context):
    results = []
    lights = get_light_shapes()

    if not lights:
        results.append(make_result(
            "WARNING",
            "NO_LIGHTS_FOUND",
            (
                "No Maya or Arnold lights were found. The render may be "
                "black unless the scene uses emissive geometry."
            )
        ))
        return results

    active_lights = [
        shape
        for shape in lights
        if is_effectively_active(shape)
    ]

    if not active_lights:
        results.append(make_result(
            "ERROR",
            "NO_ACTIVE_LIGHTS",
            (
                "Lights exist, but none are currently visible, enabled, "
                "and producing positive illumination."
            ),
            data={"lights": lights}
        ))
    else:
        results.append(make_result(
            "PASSED",
            "ACTIVE_LIGHTS_FOUND",
            "{} active light(s) were found.".format(
                len(active_lights)
            ),
            data={
                "active_lights": active_lights,
                "total_lights": len(lights),
            }
        ))

    return results


def check_light_states(context):
    results = []
    inactive = []
    invalid_brightness = []
    black_lights = []

    for shape in get_light_shapes():
        transform = get_light_transform(shape)

        if not get_hierarchy_visibility(transform):
            inactive.append({
                "shape": shape,
                "transform": transform,
                "reason": "hidden hierarchy",
            })
            continue

        if not get_light_enabled(shape):
            inactive.append({
                "shape": shape,
                "transform": transform,
                "reason": "disabled",
            })
            continue

        intensity = get_light_intensity(shape)
        exposure = get_light_exposure(shape)
        brightness = get_effective_brightness(shape)

        if intensity < 0.0 or brightness < 0.0:
            invalid_brightness.append({
                "shape": shape,
                "transform": transform,
                "intensity": intensity,
                "exposure": exposure,
            })

        elif brightness == 0.0:
            inactive.append({
                "shape": shape,
                "transform": transform,
                "reason": "zero intensity or exposure",
            })

        color = get_light_color(shape)

        if color is not None and not has_color_input(shape):
            if max(color) <= 0.000001:
                black_lights.append({
                    "shape": shape,
                    "transform": transform,
                    "color": color,
                })

    for item in invalid_brightness:
        results.append(make_result(
            "ERROR",
            "NEGATIVE_LIGHT_BRIGHTNESS",
            (
                "Light has a negative intensity or effective brightness: "
                "{}"
            ).format(item["transform"]),
            node=item["transform"],
            data=item
        ))

    for item in inactive:
        results.append(make_result(
            "WARNING",
            "INACTIVE_LIGHT",
            "Light is inactive because it is {}: {}".format(
                item["reason"],
                item["transform"]
            ),
            node=item["transform"],
            data=item
        ))

    for item in black_lights:
        results.append(make_result(
            "WARNING",
            "BLACK_LIGHT_COLOR",
            (
                "Light color is black and has no texture connection: {}"
            ).format(item["transform"]),
            node=item["transform"],
            data=item
        ))

    if not invalid_brightness and not inactive and not black_lights:
        results.append(make_result(
            "PASSED",
            "LIGHT_STATES_VALID",
            "All detected lights have valid active states."
        ))

    return results


def check_light_scale(context):
    results = []
    zero_scale = []
    negative_scale = []

    for shape in get_light_shapes():
        transform = get_light_transform(shape)

        scales = []

        for axis in "XYZ":
            attr = "{}.scale{}".format(transform, axis)

            try:
                scales.append(float(cmds.getAttr(attr)))
            except Exception:
                scales.append(1.0)

        if any(abs(value) <= 0.000001 for value in scales):
            zero_scale.append({
                "shape": shape,
                "transform": transform,
                "scale": scales,
            })

        elif any(value < 0.0 for value in scales):
            negative_scale.append({
                "shape": shape,
                "transform": transform,
                "scale": scales,
            })

    for item in zero_scale:
        results.append(make_result(
            "ERROR",
            "ZERO_LIGHT_SCALE",
            "Light transform contains a zero scale: {}".format(
                item["transform"]
            ),
            node=item["transform"],
            data=item
        ))

    for item in negative_scale:
        results.append(make_result(
            "WARNING",
            "NEGATIVE_LIGHT_SCALE",
            "Light transform contains a negative scale: {}".format(
                item["transform"]
            ),
            node=item["transform"],
            data=item
        ))

    if not zero_scale and not negative_scale:
        results.append(make_result(
            "PASSED",
            "LIGHT_SCALE_VALID",
            "Light transforms do not contain zero or negative scales."
        ))

    return results


def check_arnold_light_compatibility(context):
    results = []

    renderer = (
        context.get("renderer")
        or cmds.getAttr("defaultRenderGlobals.currentRenderer")
        or ""
    )

    if renderer != "arnold":
        results.append(make_result(
            "INFO",
            "ARNOLD_LIGHT_CHECK_SKIPPED",
            "Arnold light compatibility check was skipped."
        ))
        return results

    warnings = []

    for shape in get_light_shapes():
        node_type = cmds.nodeType(shape)

        if node_type in ARNOLD_WARNING_TYPES:
            warnings.append({
                "shape": shape,
                "transform": get_light_transform(shape),
                "type": node_type,
            })

    for item in warnings:
        results.append(make_result(
            "WARNING",
            "LIGHT_MAY_NOT_SUPPORT_ARNOLD",
            (
                "Light type '{type}' may not behave as expected with "
                "Arnold: {transform}"
            ).format(**item),
            node=item["transform"],
            data=item
        ))

    if not warnings:
        results.append(make_result(
            "PASSED",
            "ARNOLD_LIGHTS_COMPATIBLE",
            "Detected light types are compatible with Arnold."
        ))

    return results


def check_skydome_lights(context):
    results = []

    try:
        skydomes = cmds.ls(
            type="aiSkyDomeLight",
            long=True
        ) or []
    except Exception:
        skydomes = []

    active_skydomes = [
        shape
        for shape in skydomes
        if is_effectively_active(shape)
    ]

    if len(active_skydomes) > 1:
        results.append(make_result(
            "WARNING",
            "MULTIPLE_ACTIVE_SKYDOMES",
            (
                "{} active Arnold SkyDome lights were found. Multiple "
                "environment lights may cause unintended illumination."
            ).format(len(active_skydomes)),
            data={"active_skydomes": active_skydomes}
        ))

    elif len(active_skydomes) == 1:
        results.append(make_result(
            "PASSED",
            "SKYDOME_COUNT_VALID",
            "One active Arnold SkyDome light was found.",
            node=get_light_transform(active_skydomes[0])
        ))

    else:
        results.append(make_result(
            "INFO",
            "NO_ACTIVE_SKYDOME",
            "No active Arnold SkyDome light was found."
        ))

    project_path = get_project_path(context)

    for shape in skydomes:
        texture_nodes = get_file_nodes_from_history(shape)

        if not texture_nodes:
            continue

        for texture_info in texture_nodes:
            texture_path, attr_name = get_node_file_path(
                texture_info["node"],
                [texture_info["path_attr"]]
            )

            if not texture_path:
                continue

            resolved_path, exists, matches = find_existing_path(
                texture_path,
                context
            )

            data = {
                "light_shape": shape,
                "light_transform": get_light_transform(shape),
                "texture_node": texture_info["node"],
                "texture_attr": attr_name,
                "original_path": texture_path,
                "resolved_path": resolved_path,
                "matches": matches,
            }

            if not exists:
                results.append(make_result(
                    "ERROR",
                    "SKYDOME_TEXTURE_MISSING",
                    "SkyDome HDRI is missing: {}".format(
                        texture_path
                    ),
                    node=texture_info["node"],
                    data=data
                ))

            elif project_path and not path_is_inside(
                resolved_path,
                project_path
            ):
                results.append(make_result(
                    "WARNING",
                    "SKYDOME_TEXTURE_OUTSIDE_PROJECT",
                    (
                        "SkyDome HDRI is outside the Maya project and may "
                        "not exist on another worker: {}"
                    ).format(resolved_path),
                    node=texture_info["node"],
                    data=data
                ))

    return results


def check_photometric_lights(context):
    results = []

    try:
        photometric_lights = cmds.ls(
            type="aiPhotometricLight",
            long=True
        ) or []
    except Exception:
        photometric_lights = []

    if not photometric_lights:
        results.append(make_result(
            "INFO",
            "NO_PHOTOMETRIC_LIGHTS",
            "No Arnold photometric lights were found."
        ))
        return results

    project_path = get_project_path(context)
    valid_count = 0

    for shape in photometric_lights:
        file_path, attr_name = get_node_file_path(
            shape,
            [
                "aiFilename",
                "filename",
                "fileName",
                "iesFile",
            ]
        )

        transform = get_light_transform(shape)

        if not file_path:
            results.append(make_result(
                "ERROR",
                "IES_PATH_EMPTY",
                "Photometric light has no IES file: {}".format(
                    transform
                ),
                node=transform,
                data={"shape": shape}
            ))
            continue

        resolved_path, exists, matches = find_existing_path(
            file_path,
            context
        )

        data = {
            "shape": shape,
            "transform": transform,
            "file_attr": attr_name,
            "original_path": file_path,
            "resolved_path": resolved_path,
            "matches": matches,
        }

        if not exists:
            results.append(make_result(
                "ERROR",
                "IES_FILE_MISSING",
                "IES file is missing: {}".format(file_path),
                node=transform,
                data=data
            ))
            continue

        valid_count += 1

        if project_path and not path_is_inside(
            resolved_path,
            project_path
        ):
            results.append(make_result(
                "WARNING",
                "IES_FILE_OUTSIDE_PROJECT",
                (
                    "IES file is outside the Maya project and may not "
                    "exist on another worker: {}"
                ).format(resolved_path),
                node=transform,
                data=data
            ))

    if valid_count == len(photometric_lights):
        results.append(make_result(
            "PASSED",
            "PHOTOMETRIC_FILES_VALID",
            "All Arnold photometric lights have valid IES files.",
            data={"count": valid_count}
        ))

    return results


def check_light_samples(context):
    results = []
    invalid = []
    high = []

    for shape in get_light_shapes():
        sample_value = get_attr_value(
            shape,
            ["aiSamples", "samples"],
            default=None
        )

        if sample_value is None:
            continue

        try:
            sample_value = int(sample_value)
        except Exception:
            continue

        item = {
            "shape": shape,
            "transform": get_light_transform(shape),
            "samples": sample_value,
        }

        if sample_value < 1:
            invalid.append(item)

        elif sample_value > 16:
            high.append(item)

    for item in invalid:
        results.append(make_result(
            "ERROR",
            "INVALID_LIGHT_SAMPLES",
            "Light samples must be at least 1: {}".format(
                item["transform"]
            ),
            node=item["transform"],
            data=item
        ))

    for item in high:
        results.append(make_result(
            "WARNING",
            "HIGH_LIGHT_SAMPLES",
            (
                "Light uses {} samples and may increase render time: {}"
            ).format(
                item["samples"],
                item["transform"]
            ),
            node=item["transform"],
            data=item
        ))

    if not invalid and not high:
        results.append(make_result(
            "PASSED",
            "LIGHT_SAMPLES_REASONABLE",
            "Detected light sample values are valid and reasonable."
        ))

    return results


def run_checks(context):
    results = []

    checks = [
        check_light_presence,
        check_light_states,
        check_light_scale,
        check_arnold_light_compatibility,
        check_skydome_lights,
        check_photometric_lights,
        check_light_samples,
    ]

    for check in checks:
        try:
            check_results = check(context)

            if check_results:
                results.extend(check_results)

        except Exception as error:
            results.append(make_result(
                "ERROR",
                "LIGHTING_CHECK_FAILED",
                "Check '{}' failed: {}".format(
                    check.__name__,
                    error
                )
            ))

    return results
