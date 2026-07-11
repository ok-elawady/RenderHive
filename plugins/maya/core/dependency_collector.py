from __future__ import print_function

import glob
import os
import re
import time

import maya.cmds as cmds


NODE_PATH_SPECS = [
    # node type, attribute, category, path kind
    ("file", "fileTextureName", "texture", "file"),
    ("aiImage", "filename", "texture", "file"),
    ("AlembicNode", "abc_File", "alembic", "file"),
    ("gpuCache", "cacheFileName", "gpu_cache", "file"),
    ("audio", "filename", "audio", "file"),
    ("imagePlane", "imageName", "image_plane", "file"),
    ("aiStandIn", "dso", "arnold_standin", "file"),
    ("aiVolume", "filename", "volume", "file"),
    ("aiPhotometricLight", "aiFilename", "ies", "file"),
    ("mayaUsdProxyShape", "filePath", "usd", "file"),
    ("pxrUsdProxyShape", "filePath", "usd", "file"),
    ("RedshiftProxyMesh", "fileName", "redshift_proxy", "file"),
    ("VRayScene", "filepath", "vray_scene", "file"),
    ("cacheFile", "cachePath", "maya_cache", "directory"),
]


COMMON_PROJECT_FOLDERS = [
    "",
    "sourceimages",
    "textures",
    "tex",
    "maps",
    "images",
    "scenes",
    "cache",
    "caches",
    "data",
    "assets",
    "alembic",
    "abc",
    "usd",
    "vdb",
    "standins",
    "ies",
    "audio",
]


def normalize_path(path):
    if not path:
        return ""

    path = os.path.expanduser(path)
    path = path.replace("\\", os.sep).replace("/", os.sep)

    return os.path.normpath(path)


def get_scene_path(context):
    scene_path = context.get("scene_path") or ""

    if not scene_path:
        try:
            scene_path = cmds.file(
                query=True,
                sceneName=True
            ) or ""
        except Exception:
            scene_path = ""

    return normalize_path(scene_path)


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


def strip_reference_copy_number(path):
    return re.sub(r"\{\d+\}$", "", path or "")


def has_unresolved_environment_variable(path):
    if not path:
        return False

    windows_style = re.search(r"%[^%]+%", path)
    unix_style = re.search(
        r"\$(?:\{[A-Za-z_][A-Za-z0-9_]*\}|[A-Za-z_][A-Za-z0-9_]*)",
        path
    )

    return bool(windows_style or unix_style)


def expand_path(path):
    if not path:
        return ""

    path = strip_reference_copy_number(path)
    path = os.path.expandvars(path)
    path = os.path.expanduser(path)

    return normalize_path(path)


def is_network_path(path):
    if not path:
        return False

    normalized = path.replace("/", "\\")

    return normalized.startswith("\\\\")


def path_is_inside(child_path, parent_path):
    child_path = normalize_path(child_path)
    parent_path = normalize_path(parent_path)

    if not child_path or not parent_path:
        return False

    try:
        return os.path.commonpath(
            [
                os.path.abspath(child_path),
                os.path.abspath(parent_path),
            ]
        ) == os.path.abspath(parent_path)

    except ValueError:
        # Usually different drives on Windows.
        return False


def tokenized_path_to_glob(path):
    pattern = path or ""

    replacements = [
        ("<UDIM>", "*"),
        ("<udim>", "*"),
        ("%(UDIM)d", "*"),
        ("<f>", "*"),
        ("<F>", "*"),
        ("$F", "*"),
        ("$F2", "*"),
        ("$F3", "*"),
        ("$F4", "*"),
        ("$F5", "*"),
        ("$F6", "*"),
        ("$F7", "*"),
        ("$F8", "*"),
    ]

    for token, replacement in replacements:
        pattern = pattern.replace(
            token,
            replacement
        )

    pattern = re.sub(r"%0?\d*d", "*", pattern)
    pattern = re.sub(r"#+", "*", pattern)

    return pattern


def numbered_sequence_to_glob(path):
    """
    Convert a final frame-number group before the extension to a glob.

    Example:
        smoke.0001.vdb -> smoke.*.vdb
    """

    directory = os.path.dirname(path)
    basename = os.path.basename(path)

    match = re.match(
        r"^(.*?)(\d+)(\.[^.]+)$",
        basename
    )

    if not match:
        return ""

    pattern = "{}*{}".format(
        match.group(1),
        match.group(3)
    )

    return os.path.join(
        directory,
        pattern
    )


def get_search_folders(context):
    project_path = get_project_path(context)
    scene_path = get_scene_path(context)

    folders = []

    if project_path:
        for relative_folder in COMMON_PROJECT_FOLDERS:
            folders.append(
                os.path.join(
                    project_path,
                    relative_folder
                )
            )

    if scene_path:
        scene_dir = os.path.dirname(scene_path)

        folders.extend([
            scene_dir,
            os.path.dirname(scene_dir),
        ])

        parent = os.path.dirname(scene_dir)

        for relative_folder in COMMON_PROJECT_FOLDERS:
            folders.append(
                os.path.join(
                    parent,
                    relative_folder
                )
            )

    unique_folders = []

    for folder in folders:
        folder = os.path.abspath(
            normalize_path(folder)
        )

        if (
            folder not in unique_folders
            and os.path.isdir(folder)
        ):
            unique_folders.append(folder)

    return unique_folders


def _path_matches(path, path_kind):
    if path_kind == "directory":
        return os.path.isdir(path)

    return os.path.isfile(path)


def resolve_dependency_path(
    original_path,
    context,
    path_kind="file"
):
    """
    Resolve a dependency using:

    1. Direct absolute path.
    2. Maya workspace expansion.
    3. Project-relative path.
    4. Common project folders.
    5. Recursive basename search.
    6. UDIM / sequence glob patterns.
    """

    if not original_path:
        return {
            "resolved_path": "",
            "exists": False,
            "matches": [],
        }

    original_path = strip_reference_copy_number(
        original_path
    )

    expanded = expand_path(original_path)
    candidates = []

    if os.path.isabs(expanded):
        candidates.append(expanded)

    try:
        workspace_path = cmds.workspace(
            expandName=original_path
        )

        if workspace_path:
            candidates.append(
                normalize_path(workspace_path)
            )

    except Exception:
        pass

    project_path = get_project_path(context)

    if (
        project_path
        and not os.path.isabs(expanded)
    ):
        candidates.append(
            normalize_path(
                os.path.join(
                    project_path,
                    expanded
                )
            )
        )

    checked_candidates = []

    for candidate in candidates:
        if candidate in checked_candidates:
            continue

        checked_candidates.append(candidate)

        if _path_matches(candidate, path_kind):
            return {
                "resolved_path": candidate,
                "exists": True,
                "matches": [candidate],
            }

        if path_kind == "file":
            patterns = [
                tokenized_path_to_glob(candidate),
                numbered_sequence_to_glob(candidate),
            ]

            for pattern in patterns:
                if not pattern:
                    continue

                matches = glob.glob(pattern)

                if matches:
                    return {
                        "resolved_path": normalize_path(
                            matches[0]
                        ),
                        "exists": True,
                        "matches": [
                            normalize_path(item)
                            for item in matches
                        ],
                    }

    basename = os.path.basename(expanded)
    basename_pattern = tokenized_path_to_glob(
        basename
    )

    for folder in get_search_folders(context):
        candidate = os.path.join(
            folder,
            basename
        )

        if _path_matches(candidate, path_kind):
            return {
                "resolved_path": normalize_path(
                    candidate
                ),
                "exists": True,
                "matches": [
                    normalize_path(candidate)
                ],
            }

        if path_kind == "file":
            patterns = [
                os.path.join(
                    folder,
                    basename_pattern
                ),
                numbered_sequence_to_glob(
                    candidate
                ),
            ]

            for pattern in patterns:
                if not pattern:
                    continue

                matches = glob.glob(pattern)

                if matches:
                    return {
                        "resolved_path": normalize_path(
                            matches[0]
                        ),
                        "exists": True,
                        "matches": [
                            normalize_path(item)
                            for item in matches
                        ],
                    }

    for folder in get_search_folders(context):
        if path_kind == "directory":
            continue

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
            return {
                "resolved_path": normalize_path(
                    matches[0]
                ),
                "exists": True,
                "matches": [
                    normalize_path(item)
                    for item in matches
                ],
            }

    fallback = expanded or original_path

    return {
        "resolved_path": fallback,
        "exists": False,
        "matches": [],
    }


def get_node_path(node, attribute):
    plug = "{}.{}".format(
        node,
        attribute
    )

    if not cmds.objExists(plug):
        return ""

    try:
        value = cmds.getAttr(plug)
    except Exception:
        return ""

    if isinstance(value, str):
        return value

    return ""


def collect_reference_dependencies():
    dependencies = []

    try:
        references = cmds.file(
            query=True,
            reference=True
        ) or []
    except Exception:
        references = []

    for reference_path in references:
        dependencies.append({
            "category": "reference",
            "node": "",
            "attribute": "",
            "original_path": reference_path,
            "path_kind": "file",
        })

    return dependencies


def collect_node_dependencies():
    dependencies = []

    for (
        node_type,
        attribute,
        category,
        path_kind
    ) in NODE_PATH_SPECS:

        try:
            nodes = cmds.ls(
                type=node_type
            ) or []
        except Exception:
            nodes = []

        for node in nodes:
            path = get_node_path(
                node,
                attribute
            )

            if not path:
                continue

            dependencies.append({
                "category": category,
                "node": node,
                "attribute": attribute,
                "original_path": path,
                "path_kind": path_kind,
            })

    return dependencies


def deduplicate_dependencies(dependencies):
    unique = []
    seen = set()

    for dependency in dependencies:
        key = (
            dependency.get("category", ""),
            dependency.get("node", ""),
            dependency.get("attribute", ""),
            dependency.get("original_path", ""),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(dependency)

    return unique


def enrich_dependency(dependency, context):
    original_path = dependency.get(
        "original_path",
        ""
    )

    path_kind = dependency.get(
        "path_kind",
        "file"
    )

    unresolved_environment = (
        has_unresolved_environment_variable(
            original_path
        )
    )

    resolution = resolve_dependency_path(
        original_path,
        context,
        path_kind=path_kind
    )

    resolved_path = resolution[
        "resolved_path"
    ]

    project_path = get_project_path(context)

    inside_project = False
    relative_path = ""

    if (
        resolution["exists"]
        and project_path
    ):
        inside_project = path_is_inside(
            resolved_path,
            project_path
        )

        if inside_project:
            try:
                relative_path = os.path.relpath(
                    resolved_path,
                    project_path
                )
            except ValueError:
                relative_path = ""

    original_expanded = expand_path(
        original_path
    )

    original_is_absolute = os.path.isabs(
        original_expanded
    )

    dependency = dict(dependency)

    dependency.update({
        "resolved_path": resolved_path,
        "exists": bool(resolution["exists"]),
        "matches": resolution["matches"],
        "match_count": len(
            resolution["matches"]
        ),
        "inside_project": inside_project,
        "relative_path": normalize_path(
            relative_path
        ) if relative_path else "",
        "original_is_absolute": (
            original_is_absolute
        ),
        "network_path": is_network_path(
            resolved_path or original_path
        ),
        "unresolved_environment_variable": (
            unresolved_environment
        ),
    })

    if unresolved_environment:
        dependency["status"] = (
            "unresolved_environment"
        )

    elif not dependency["exists"]:
        dependency["status"] = "missing"

    elif not project_path:
        dependency["status"] = (
            "project_path_missing"
        )

    elif dependency["inside_project"]:
        if dependency[
            "original_is_absolute"
        ]:
            dependency["status"] = (
                "absolute_inside_project"
            )
        else:
            dependency["status"] = "portable"

    elif dependency["network_path"]:
        dependency["status"] = (
            "external_network"
        )

    else:
        dependency["status"] = (
            "external_local"
        )

    return dependency


def collect_dependencies(context=None):
    context = context or {}

    raw_dependencies = []

    raw_dependencies.extend(
        collect_reference_dependencies()
    )

    raw_dependencies.extend(
        collect_node_dependencies()
    )

    raw_dependencies = deduplicate_dependencies(
        raw_dependencies
    )

    dependencies = [
        enrich_dependency(
            dependency,
            context
        )
        for dependency in raw_dependencies
    ]

    return dependencies


def build_manifest(context=None):
    context = context or {}

    dependencies = collect_dependencies(
        context
    )

    status_counts = {}

    for dependency in dependencies:
        status = dependency.get(
            "status",
            "unknown"
        )

        status_counts[status] = (
            status_counts.get(status, 0) + 1
        )

    manifest = {
        "manifest_version": 1,
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "scene_path": get_scene_path(context),
        "project_path": get_project_path(context),
        "summary": {
            "total": len(dependencies),
            "status_counts": status_counts,
        },
        "dependencies": dependencies,
    }

    return manifest
