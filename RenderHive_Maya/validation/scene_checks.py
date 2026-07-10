import os
import re

import maya.cmds as cmds


CATEGORY = "Scene"


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
    path = os.path.abspath(path)

    return os.path.normpath(path)


def path_is_inside(child_path, parent_path):
    child_path = normalize_path(child_path)
    parent_path = normalize_path(parent_path)

    if not child_path or not parent_path:
        return False

    try:
        return os.path.commonpath(
            [child_path, parent_path]
        ) == parent_path

    except ValueError:
        # Different drives on Windows.
        return False


def resolve_project_path(path, project_path):
    if not path:
        return ""

    expanded = os.path.expandvars(path)
    expanded = os.path.expanduser(expanded)

    # Remove Maya reference copy numbers:
    # file.ma{1}
    expanded = re.sub(r"\{\d+\}$", "", expanded)

    if os.path.isabs(expanded):
        return normalize_path(expanded)

    try:
        maya_expanded = cmds.workspace(
            expandName=expanded
        )

        if maya_expanded:
            return normalize_path(maya_expanded)

    except Exception:
        pass

    if project_path:
        return normalize_path(
            os.path.join(project_path, expanded)
        )

    return normalize_path(expanded)


def check_scene_saved(context):
    results = []

    scene_path = context.get("scene_path") or (
        cmds.file(query=True, sceneName=True) or ""
    )

    if not scene_path:
        results.append(make_result(
            "ERROR",
            "SCENE_NOT_SAVED",
            "The Maya scene has not been saved.",
            fixable=False
        ))
        return results

    scene_path = normalize_path(scene_path)

    if not os.path.exists(scene_path):
        results.append(make_result(
            "ERROR",
            "SCENE_FILE_MISSING",
            "Scene file does not exist: {}".format(scene_path),
            fixable=False,
            data={"path": scene_path}
        ))
        return results

    if cmds.file(query=True, modified=True):
        results.append(make_result(
            "WARNING",
            "SCENE_HAS_UNSAVED_CHANGES",
            "The scene contains unsaved changes.",
            fixable=True,
            data={"path": scene_path}
        ))
    else:
        results.append(make_result(
            "PASSED",
            "SCENE_SAVED",
            "The Maya scene is saved.",
            data={"path": scene_path}
        ))

    return results


def check_project_path(context):
    results = []

    project_path = context.get("project_path")

    if not project_path:
        try:
            project_path = cmds.workspace(
                query=True,
                rootDirectory=True
            )
        except Exception:
            project_path = ""

    if not project_path:
        results.append(make_result(
            "ERROR",
            "PROJECT_PATH_EMPTY",
            "Maya project path is empty."
        ))
        return results

    project_path = normalize_path(project_path)

    if not os.path.isdir(project_path):
        results.append(make_result(
            "ERROR",
            "PROJECT_PATH_MISSING",
            "Maya project folder does not exist: {}".format(
                project_path
            ),
            data={"path": project_path}
        ))
    else:
        results.append(make_result(
            "PASSED",
            "PROJECT_PATH_VALID",
            "Maya project path is valid.",
            data={"path": project_path}
        ))

    return results


def check_scene_inside_project(context):
    results = []

    scene_path = context.get("scene_path") or (
        cmds.file(query=True, sceneName=True) or ""
    )

    project_path = context.get("project_path")

    if not project_path:
        try:
            project_path = cmds.workspace(
                query=True,
                rootDirectory=True
            )
        except Exception:
            project_path = ""

    if not scene_path or not project_path:
        return results

    scene_path = normalize_path(scene_path)
    project_path = normalize_path(project_path)

    if path_is_inside(scene_path, project_path):
        results.append(make_result(
            "PASSED",
            "SCENE_INSIDE_PROJECT",
            "Scene file is inside the Maya project.",
            data={
                "scene_path": scene_path,
                "project_path": project_path,
            }
        ))
    else:
        results.append(make_result(
            "WARNING",
            "SCENE_OUTSIDE_PROJECT",
            (
                "Scene file is outside the Maya project. "
                "This may cause portability problems on another machine."
            ),
            data={
                "scene_path": scene_path,
                "project_path": project_path,
            }
        ))

    return results


def check_frame_range(context):
    results = []

    try:
        frame_start = int(context.get(
            "frame_start",
            cmds.getAttr("defaultRenderGlobals.startFrame")
        ))

        frame_end = int(context.get(
            "frame_end",
            cmds.getAttr("defaultRenderGlobals.endFrame")
        ))

    except Exception as error:
        results.append(make_result(
            "ERROR",
            "FRAME_RANGE_READ_FAILED",
            "Could not read frame range: {}".format(error)
        ))
        return results

    if frame_start > frame_end:
        results.append(make_result(
            "ERROR",
            "INVALID_FRAME_RANGE",
            "Frame start cannot be greater than frame end.",
            data={
                "frame_start": frame_start,
                "frame_end": frame_end,
            }
        ))
    else:
        results.append(make_result(
            "PASSED",
            "FRAME_RANGE_VALID",
            "Frame range is valid: {} to {}.".format(
                frame_start,
                frame_end
            ),
            data={
                "frame_start": frame_start,
                "frame_end": frame_end,
            }
        ))

    return results


def check_renderer(context):
    results = []

    requested_renderer = context.get("renderer")

    try:
        scene_renderer = cmds.getAttr(
            "defaultRenderGlobals.currentRenderer"
        )
    except Exception:
        scene_renderer = ""

    renderer = requested_renderer or scene_renderer

    if not renderer:
        results.append(make_result(
            "ERROR",
            "RENDERER_EMPTY",
            "No renderer is selected."
        ))
        return results

    if requested_renderer and scene_renderer:
        if requested_renderer != scene_renderer:
            results.append(make_result(
                "WARNING",
                "RENDERER_MISMATCH",
                (
                    "Task renderer is '{}' but scene renderer is '{}'."
                ).format(requested_renderer, scene_renderer),
                data={
                    "task_renderer": requested_renderer,
                    "scene_renderer": scene_renderer,
                }
            ))

    if renderer == "arnold":
        try:
            mtoa_registered = cmds.pluginInfo(
                "mtoa",
                query=True,
                registered=True
            )
        except Exception:
            mtoa_registered = False

        try:
            mtoa_loaded = cmds.pluginInfo(
                "mtoa",
                query=True,
                loaded=True
            )
        except Exception:
            mtoa_loaded = False

        if not mtoa_registered:
            results.append(make_result(
                "ERROR",
                "ARNOLD_NOT_INSTALLED",
                "Arnold for Maya (mtoa) is not available on this machine."
            ))

        elif not mtoa_loaded:
            results.append(make_result(
                "WARNING",
                "ARNOLD_NOT_LOADED",
                "Arnold is installed but mtoa is not currently loaded.",
                fixable=True
            ))

        else:
            results.append(make_result(
                "PASSED",
                "ARNOLD_AVAILABLE",
                "Arnold and mtoa are available."
            ))

    else:
        results.append(make_result(
            "INFO",
            "NON_ARNOLD_RENDERER",
            "Selected renderer: {}.".format(renderer)
        ))

    return results


def check_camera(context):
    results = []

    camera = context.get("camera")

    if not camera or camera == "NoCamera":
        results.append(make_result(
            "ERROR",
            "CAMERA_NOT_SELECTED",
            "No render camera is selected."
        ))
        return results

    if not cmds.objExists(camera):
        results.append(make_result(
            "ERROR",
            "CAMERA_MISSING",
            "Selected camera does not exist: {}".format(camera),
            node=camera
        ))
        return results

    shapes = cmds.listRelatives(
        camera,
        shapes=True,
        type="camera"
    ) or []

    if not shapes:
        results.append(make_result(
            "ERROR",
            "INVALID_CAMERA_NODE",
            "'{}' is not a valid camera transform.".format(camera),
            node=camera
        ))
        return results

    camera_shape = shapes[0]

    try:
        renderable = cmds.getAttr(
            camera_shape + ".renderable"
        )
    except Exception:
        renderable = False

    if camera in ["persp", "front", "side", "top"]:
        results.append(make_result(
            "WARNING",
            "DEFAULT_CAMERA_SELECTED",
            (
                "A default Maya camera is selected. "
                "A dedicated render camera is recommended."
            ),
            node=camera
        ))

    if not renderable:
        results.append(make_result(
            "WARNING",
            "CAMERA_NOT_RENDERABLE",
            "Camera '{}' is not marked renderable.".format(camera),
            node=camera,
            fixable=True
        ))
    else:
        results.append(make_result(
            "PASSED",
            "CAMERA_VALID",
            "Render camera '{}' is valid.".format(camera),
            node=camera
        ))

    return results


def check_output_path(context):
    results = []

    output_path = context.get("output_path")
    project_path = context.get("project_path")

    if not output_path:
        results.append(make_result(
            "ERROR",
            "OUTPUT_PATH_EMPTY",
            "Render output path is empty."
        ))
        return results

    output_path = normalize_path(output_path)

    if project_path:
        project_path = normalize_path(project_path)

        if not path_is_inside(output_path, project_path):
            results.append(make_result(
                "WARNING",
                "OUTPUT_OUTSIDE_PROJECT",
                (
                    "Render output is outside the Maya project. "
                    "This path may not be available on another worker."
                ),
                data={
                    "output_path": output_path,
                    "project_path": project_path,
                }
            ))
        else:
            results.append(make_result(
                "PASSED",
                "OUTPUT_INSIDE_PROJECT",
                "Render output is inside the Maya project.",
                data={"output_path": output_path}
            ))

    if not os.path.exists(output_path):
        results.append(make_result(
            "WARNING",
            "OUTPUT_FOLDER_MISSING",
            "Output folder does not exist: {}".format(output_path),
            fixable=True,
            data={"path": output_path}
        ))

    else:
        writable = os.access(output_path, os.W_OK)

        if not writable:
            results.append(make_result(
                "ERROR",
                "OUTPUT_FOLDER_NOT_WRITABLE",
                "Output folder is not writable: {}".format(
                    output_path
                ),
                data={"path": output_path}
            ))

    return results


def check_references(context):
    results = []

    project_path = context.get("project_path") or ""

    references = cmds.file(
        query=True,
        reference=True
    ) or []

    if not references:
        results.append(make_result(
            "INFO",
            "NO_REFERENCES",
            "Scene contains no external references."
        ))
        return results

    missing_references = []

    for reference_path in references:
        resolved_path = resolve_project_path(
            reference_path,
            project_path
        )

        if not os.path.exists(resolved_path):
            missing_references.append({
                "original_path": reference_path,
                "resolved_path": resolved_path,
            })

    if missing_references:
        for missing in missing_references:
            results.append(make_result(
                "ERROR",
                "REFERENCE_MISSING",
                "Missing reference: {}".format(
                    missing["original_path"]
                ),
                data=missing
            ))
    else:
        results.append(make_result(
            "PASSED",
            "REFERENCES_VALID",
            "All scene references are available.",
            data={"count": len(references)}
        ))

    return results


def check_unknown_nodes(context):
    results = []

    unknown_nodes = cmds.ls(type="unknown") or []

    try:
        unknown_plugins = cmds.unknownPlugin(
            query=True,
            list=True
        ) or []
    except Exception:
        unknown_plugins = []

    if unknown_nodes:
        results.append(make_result(
            "WARNING",
            "UNKNOWN_NODES_FOUND",
            "Scene contains {} unknown node(s).".format(
                len(unknown_nodes)
            ),
            data={"nodes": unknown_nodes}
        ))
    else:
        results.append(make_result(
            "PASSED",
            "NO_UNKNOWN_NODES",
            "No unknown nodes were found."
        ))

    if unknown_plugins:
        results.append(make_result(
            "WARNING",
            "UNKNOWN_PLUGINS_FOUND",
            "Scene contains unknown plugin records: {}".format(
                ", ".join(unknown_plugins)
            ),
            data={"plugins": unknown_plugins}
        ))

    return results


def run_checks(context):
    results = []

    checks = [
        check_scene_saved,
        check_project_path,
        check_scene_inside_project,
        check_frame_range,
        check_renderer,
        check_camera,
        check_output_path,
        check_references,
        check_unknown_nodes,
    ]

    for check in checks:
        try:
            check_results = check(context)

            if check_results:
                results.extend(check_results)

        except Exception as error:
            results.append(make_result(
                "ERROR",
                "SCENE_CHECK_FAILED",
                "Check '{}' failed: {}".format(
                    check.__name__,
                    error
                )
            ))

    return results