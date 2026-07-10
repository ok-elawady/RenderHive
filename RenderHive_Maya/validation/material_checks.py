import glob
import os
import re

import maya.cmds as cmds


CATEGORY = "Material"

DEFAULT_MATERIALS = {
    "lambert1",
    "particleCloud1",
    "shaderGlow1",
}

DEFAULT_SHADING_ENGINES = {
    "initialShadingGroup",
    "initialParticleSE",
}

ARNOLD_SUPPORTED_SURFACE_TYPES = {
    "aiStandardSurface",
    "standardSurface",
    "lambert",
    "blinn",
    "phong",
    "phongE",
    "anisotropic",
    "surfaceShader",
    "useBackground",
    "aiFlat",
    "aiMixShader",
    "aiLayerShader",
    "aiShadowMatte",
    "aiWireframe",
}

COLOR_KEYWORDS = {
    "basecolor",
    "base_color",
    "base color",
    "albedo",
    "diffuse",
    "diff",
    "beauty",
}

DATA_KEYWORDS = {
    "roughness",
    "rough",
    "metalness",
    "metallic",
    "metal",
    "normal",
    "nrm",
    "bump",
    "height",
    "displacement",
    "disp",
    "mask",
    "opacity",
    "alpha",
    "ambientocclusion",
    "ambient_occlusion",
    "occlusion",
    "ao",
    "gloss",
    "specularroughness",
    "specular_roughness",
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
        common_path = os.path.commonpath([
            os.path.abspath(child_path),
            os.path.abspath(parent_path),
        ])

        return os.path.normcase(common_path) == os.path.normcase(
            os.path.abspath(parent_path)
        )
    except ValueError:
        return False


def is_referenced(node):
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
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
            os.path.join(project_path, "images"),
        ])

    if scene_path:
        scene_dir = os.path.dirname(scene_path)

        folders.extend([
            scene_dir,
            os.path.join(scene_dir, "sourceimages"),
            os.path.join(scene_dir, "textures"),
            os.path.join(scene_dir, "tex"),
            os.path.join(scene_dir, "..", "sourceimages"),
            os.path.join(scene_dir, "..", "textures"),
            os.path.join(scene_dir, "..", "tex"),
            os.path.join(scene_dir, "..", "maps"),
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
    """
    Resolve normal, project-relative, filename-only, UDIM and sequence paths.

    Returns:
        resolved_path: a real file path or the best unresolved path.
        exists: bool
        matches: list of matching files for tokenized paths.
    """

    if not path:
        return "", False, []

    original = path
    expanded = normalize_path(path)

    direct_candidates = []

    if os.path.isabs(expanded):
        direct_candidates.append(expanded)

    try:
        workspace_expanded = cmds.workspace(
            expandName=path
        )

        if workspace_expanded:
            direct_candidates.append(
                normalize_path(workspace_expanded)
            )
    except Exception:
        pass

    project_path = get_project_path(context)

    if project_path and not os.path.isabs(expanded):
        direct_candidates.append(
            normalize_path(os.path.join(project_path, expanded))
        )

    for candidate in direct_candidates:
        if os.path.isfile(candidate):
            return candidate, True, [candidate]

        pattern = tokenized_path_to_glob(candidate)
        matches = glob.glob(pattern)

        if matches:
            return matches[0], True, matches

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
        recursive_pattern = os.path.join(
            folder,
            "**",
            basename_pattern
        )

        matches = glob.glob(
            recursive_pattern,
            recursive=True
        )

        if matches:
            return normalize_path(matches[0]), True, matches

    return original, False, []


def get_texture_nodes():
    nodes = []

    try:
        file_nodes = cmds.ls(type="file") or []
    except Exception:
        file_nodes = []

    for node in file_nodes:
        nodes.append({
            "node": node,
            "type": "file",
            "path_attr": "fileTextureName",
            "color_space_attrs": ["colorSpace"],
        })

    try:
        ai_image_nodes = cmds.ls(type="aiImage") or []
    except Exception:
        ai_image_nodes = []

    for node in ai_image_nodes:
        nodes.append({
            "node": node,
            "type": "aiImage",
            "path_attr": "filename",
            "color_space_attrs": [
                "color_space",
                "colorSpace",
            ],
        })

    return nodes


def get_texture_path(texture_info):
    node = texture_info["node"]
    attr_name = texture_info["path_attr"]
    attr = "{}.{}".format(node, attr_name)

    if not cmds.objExists(attr):
        return ""

    try:
        return cmds.getAttr(attr) or ""
    except Exception:
        return ""


def get_color_space(texture_info):
    node = texture_info["node"]

    for attr_name in texture_info["color_space_attrs"]:
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


def get_downstream_plugs(node):
    try:
        plugs = cmds.listConnections(
            node,
            source=False,
            destination=True,
            plugs=True
        ) or []
    except Exception:
        plugs = []

    return plugs


def infer_texture_usage(texture_info, texture_path):
    node = texture_info["node"]

    text_parts = [
        node,
        texture_path,
    ]

    text_parts.extend(get_downstream_plugs(node))
    text = " ".join(text_parts).lower()

    data_match = any(
        keyword in text
        for keyword in DATA_KEYWORDS
    )

    color_match = any(
        keyword in text
        for keyword in COLOR_KEYWORDS
    )

    if data_match:
        return "data"

    if color_match:
        return "color"

    return "unknown"


def is_srgb_color_space(color_space):
    return "srgb" in (color_space or "").lower()


def is_raw_color_space(color_space):
    return "raw" in (color_space or "").lower()


def get_renderable_mesh_shapes():
    shapes = []

    for shape in cmds.ls(type="mesh", long=True) or []:
        try:
            if cmds.getAttr(shape + ".intermediateObject"):
                continue
        except Exception:
            pass

        parents = cmds.listRelatives(
            shape,
            parent=True,
            fullPath=True
        ) or []

        if not parents:
            continue

        transform = parents[0]

        try:
            if not cmds.getAttr(transform + ".visibility"):
                continue
        except Exception:
            pass

        if cmds.objExists(shape + ".primaryVisibility"):
            try:
                if not cmds.getAttr(shape + ".primaryVisibility"):
                    continue
            except Exception:
                pass

        shapes.append(shape)

    return shapes


def check_material_assignments(context):
    results = []
    missing_assignments = []

    for shape in get_renderable_mesh_shapes():
        shading_engines = cmds.listConnections(
            shape,
            source=False,
            destination=True,
            type="shadingEngine"
        ) or []

        shading_engines = sorted(set(shading_engines))

        if not shading_engines:
            missing_assignments.append(shape)

    if missing_assignments:
        for shape in missing_assignments:
            results.append(make_result(
                "ERROR",
                "MESH_WITHOUT_MATERIAL",
                "Renderable mesh has no material assignment: {}".format(
                    shape
                ),
                node=shape,
                data={"shape": shape}
            ))
    else:
        results.append(make_result(
            "PASSED",
            "ALL_MESHES_HAVE_MATERIALS",
            "All renderable meshes have material assignments."
        ))

    return results


def check_shading_groups(context):
    results = []
    broken = []

    shading_engines = cmds.ls(type="shadingEngine") or []

    for shading_engine in shading_engines:
        if shading_engine in DEFAULT_SHADING_ENGINES:
            continue

        surface_attr = shading_engine + ".surfaceShader"

        if not cmds.objExists(surface_attr):
            broken.append(shading_engine)
            continue

        materials = cmds.listConnections(
            surface_attr,
            source=True,
            destination=False
        ) or []

        if not materials:
            broken.append(shading_engine)

    if broken:
        for shading_engine in broken:
            results.append(make_result(
                "ERROR",
                "BROKEN_SHADING_GROUP",
                "Shading group has no surface shader: {}".format(
                    shading_engine
                ),
                node=shading_engine
            ))
    else:
        results.append(make_result(
            "PASSED",
            "SHADING_GROUPS_VALID",
            "All non-default shading groups have surface shaders."
        ))

    return results


def check_texture_files(context):
    results = []
    checked_count = 0
    missing = []
    external = []

    project_path = get_project_path(context)

    for texture_info in get_texture_nodes():
        texture_path = get_texture_path(texture_info)

        if not texture_path:
            continue

        checked_count += 1

        resolved_path, exists, matches = find_existing_path(
            texture_path,
            context
        )

        item = {
            "node": texture_info["node"],
            "type": texture_info["type"],
            "original_path": texture_path,
            "resolved_path": resolved_path,
            "matches": matches,
        }

        if not exists:
            missing.append(item)
            continue

        if project_path and not path_is_inside(
            resolved_path,
            project_path
        ):
            external.append(item)

    for item in missing:
        results.append(make_result(
            "ERROR",
            "TEXTURE_MISSING",
            "Missing texture: {}".format(
                item["original_path"]
            ),
            node=item["node"],
            data=item
        ))

    for item in external:
        results.append(make_result(
            "WARNING",
            "TEXTURE_OUTSIDE_PROJECT",
            (
                "Texture is outside the Maya project and may not be "
                "available on another worker: {}"
            ).format(item["resolved_path"]),
            node=item["node"],
            data=item
        ))

    if checked_count == 0:
        results.append(make_result(
            "INFO",
            "NO_TEXTURE_NODES",
            "No file or Arnold aiImage texture nodes were found."
        ))

    elif not missing:
        results.append(make_result(
            "PASSED",
            "TEXTURES_AVAILABLE",
            "All {} checked texture path(s) are available.".format(
                checked_count
            ),
            data={"checked_count": checked_count}
        ))

    if checked_count and not external:
        results.append(make_result(
            "PASSED",
            "TEXTURES_PORTABLE",
            "All resolved textures are inside the Maya project."
        ))

    return results


def check_texture_color_spaces(context):
    results = []
    checked_count = 0
    mismatches = []

    for texture_info in get_texture_nodes():
        texture_path = get_texture_path(texture_info)

        if not texture_path:
            continue

        usage = infer_texture_usage(
            texture_info,
            texture_path
        )

        if usage == "unknown":
            continue

        color_space, color_space_attr = get_color_space(
            texture_info
        )

        if not color_space:
            continue

        checked_count += 1

        expected = ""
        valid = True

        if usage == "color":
            expected = "sRGB"
            valid = is_srgb_color_space(color_space)

        elif usage == "data":
            expected = "Raw"
            valid = is_raw_color_space(color_space)

        if not valid:
            mismatches.append({
                "node": texture_info["node"],
                "path": texture_path,
                "usage": usage,
                "current_color_space": color_space,
                "expected_color_space": expected,
                "color_space_attr": color_space_attr,
            })

    for item in mismatches:
        results.append(make_result(
            "WARNING",
            "TEXTURE_COLOR_SPACE_MISMATCH",
            (
                "Texture appears to be a {usage} map but uses "
                "'{current_color_space}'. Expected '{expected_color_space}'."
            ).format(**item),
            node=item["node"],
            fixable=True,
            data=item
        ))

    if checked_count and not mismatches:
        results.append(make_result(
            "PASSED",
            "TEXTURE_COLOR_SPACES_VALID",
            "Checked texture color spaces match their likely usage.",
            data={"checked_count": checked_count}
        ))

    elif checked_count == 0:
        results.append(make_result(
            "INFO",
            "COLOR_SPACE_CHECK_SKIPPED",
            (
                "No texture usage could be inferred for color-space "
                "validation."
            )
        ))

    return results


def check_unused_materials(context):
    results = []
    unused = []

    materials = cmds.ls(materials=True) or []

    for material in materials:
        short_name = material.split("|")[-1]

        if short_name in DEFAULT_MATERIALS:
            continue

        if is_referenced(material):
            continue

        shading_engines = cmds.listConnections(
            material,
            source=False,
            destination=True,
            type="shadingEngine"
        ) or []

        used = False

        for shading_engine in set(shading_engines):
            members = cmds.sets(
                shading_engine,
                query=True
            ) or []

            if members:
                used = True
                break

        if not used:
            unused.append(material)

    if unused:
        for material in unused:
            results.append(make_result(
                "WARNING",
                "UNUSED_MATERIAL",
                "Material is not assigned to scene geometry: {}".format(
                    material
                ),
                node=material
            ))
    else:
        results.append(make_result(
            "PASSED",
            "NO_UNUSED_MATERIALS",
            "No obvious unused local materials were found."
        ))

    return results


def check_arnold_material_compatibility(context):
    results = []

    renderer = (
        context.get("renderer")
        or cmds.getAttr("defaultRenderGlobals.currentRenderer")
        or ""
    )

    if renderer != "arnold":
        results.append(make_result(
            "INFO",
            "ARNOLD_MATERIAL_CHECK_SKIPPED",
            "Arnold material compatibility check was skipped."
        ))
        return results

    unsupported = []

    for shading_engine in cmds.ls(type="shadingEngine") or []:
        surface_attr = shading_engine + ".surfaceShader"

        if not cmds.objExists(surface_attr):
            continue

        materials = cmds.listConnections(
            surface_attr,
            source=True,
            destination=False
        ) or []

        for material in materials:
            node_type = cmds.nodeType(material)

            if node_type not in ARNOLD_SUPPORTED_SURFACE_TYPES:
                unsupported.append({
                    "material": material,
                    "type": node_type,
                    "shading_engine": shading_engine,
                })

    unique_items = []
    seen = set()

    for item in unsupported:
        key = (
            item["material"],
            item["type"],
            item["shading_engine"],
        )

        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    for item in unique_items:
        results.append(make_result(
            "WARNING",
            "MATERIAL_MAY_NOT_SUPPORT_ARNOLD",
            (
                "Material type '{type}' may not render correctly with "
                "Arnold: {material}"
            ).format(**item),
            node=item["material"],
            data=item
        ))

    if not unique_items:
        results.append(make_result(
            "PASSED",
            "ARNOLD_MATERIALS_COMPATIBLE",
            "Assigned surface materials are compatible with Arnold."
        ))

    return results


def run_checks(context):
    results = []

    checks = [
        check_material_assignments,
        check_shading_groups,
        check_texture_files,
        check_texture_color_spaces,
        check_unused_materials,
        check_arnold_material_compatibility,
    ]

    for check in checks:
        try:
            check_results = check(context)

            if check_results:
                results.extend(check_results)

        except Exception as error:
            results.append(make_result(
                "ERROR",
                "MATERIAL_CHECK_FAILED",
                "Check '{}' failed: {}".format(
                    check.__name__,
                    error
                )
            ))

    return results
