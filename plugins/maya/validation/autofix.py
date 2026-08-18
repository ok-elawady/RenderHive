from __future__ import print_function

import os

import maya.cmds as cmds


# Codes are grouped by the actual change they perform. Some validation modules
# report the same scene issue using slightly different codes.
FIX_GROUPS = {
    "set_arnold_renderer": {
        "codes": {
            "ARNOLD_REQUIRED",
            "SCENE_RENDERER_NOT_ARNOLD",
        },
        "batch_safe": True,
        "confirmation": False,
    },
    "load_mtoa": {
        "codes": {
            "ARNOLD_NOT_LOADED",
        },
        "batch_safe": True,
        "undoable": False,
        "confirmation": False,
    },
    "make_camera_renderable": {
        "codes": {
            "RENDER_CAMERA_NOT_RENDERABLE",
        },
        "batch_safe": True,
        "undoable": True,
        "confirmation": False,
    },
    "create_output_folder": {
        "codes": {
            "OUTPUT_FOLDER_MISSING",
        },
        "batch_safe": True,
        "undoable": False,
        "confirmation": False,
    },
    "disable_render_region": {
        "codes": {
            "RENDER_REGION_ENABLED",
        },
        "batch_safe": True,
        "undoable": True,
        "confirmation": False,
    },
    "set_texture_color_space": {
        "codes": {
            "TEXTURE_COLOR_SPACE_MISMATCH",
        },
        "batch_safe": True,
        "undoable": True,
        "confirmation": False,
    },
    "rename_shape": {
        "codes": {
            "SHAPE_NAME_MISMATCH",
        },
        "batch_safe": True,
        "undoable": True,
        "confirmation": False,
    },
    "save_scene": {
        "codes": {
            "SCENE_HAS_UNSAVED_CHANGES",
        },
        # Saving is supported for Fix Selected, but it is intentionally
        # excluded from Fix All Safe because saving cannot be undone.
        "batch_safe": False,
        "undoable": False,
        "confirmation": True,
    },
}


def _group_for_code(code):
    code = str(code or "").upper()

    for group_name, settings in FIX_GROUPS.items():
        if code in settings["codes"]:
            return group_name, settings

    return "", None


def can_fix_result(result):
    if not isinstance(result, dict):
        return False

    if not result.get("fixable"):
        return False

    group_name, settings = _group_for_code(
        result.get("code")
    )

    return bool(group_name and settings)


def is_batch_safe(result):
    if not can_fix_result(result):
        return False

    _, settings = _group_for_code(
        result.get("code")
    )

    return bool(settings.get("batch_safe"))


def requires_confirmation(result):
    if not can_fix_result(result):
        return False

    _, settings = _group_for_code(
        result.get("code")
    )

    return bool(settings.get("confirmation"))


def fix_label(result):
    group_name, _ = _group_for_code(
        result.get("code") if isinstance(result, dict) else ""
    )

    labels = {
        "set_arnold_renderer": "Set Arnold Renderer",
        "load_mtoa": "Load Arnold",
        "make_camera_renderable": "Make Camera Renderable",
        "create_output_folder": "Create Output Folder",
        "disable_render_region": "Disable Render Region",
        "set_texture_color_space": "Set Texture Color Space",
        "rename_shape": "Rename Shape",
        "save_scene": "Save Scene",
    }

    return labels.get(group_name, "Auto Fix")


def fix_key(result):
    """
    Build a stable key so duplicate findings from Scene and Render validators
    are fixed only once by Fix All Safe.
    """
    if not isinstance(result, dict):
        return ("invalid",)

    group_name, _ = _group_for_code(
        result.get("code")
    )

    data = result.get("data") or {}
    node = result.get("node") or data.get("node") or ""

    if group_name == "set_arnold_renderer":
        return (group_name, "arnold")

    if group_name == "load_mtoa":
        return (group_name, "mtoa")

    if group_name == "make_camera_renderable":
        return (group_name, node)

    if group_name == "create_output_folder":
        return (
            group_name,
            os.path.normcase(
                os.path.normpath(
                    data.get("path") or ""
                )
            ),
        )

    if group_name == "disable_render_region":
        return (
            group_name,
            "defaultRenderGlobals.useRenderRegion",
        )

    if group_name == "set_texture_color_space":
        return (
            group_name,
            data.get("node") or node,
            data.get("color_space_attr") or "",
            data.get("expected_color_space") or "",
        )

    if group_name == "rename_shape":
        return (
            group_name,
            data.get("shape") or node,
            data.get("expected_shape_name") or "",
        )

    if group_name == "save_scene":
        return (group_name, "scene")

    return (
        group_name,
        result.get("code") or "",
        node,
    )


def collect_batch_safe(results):
    unique = []
    seen = set()

    for result in results or []:
        if not is_batch_safe(result):
            continue

        key = fix_key(result)

        if key in seen:
            continue

        seen.add(key)
        unique.append(result)

    return unique


def _node_is_referenced(node):
    try:
        return bool(
            cmds.referenceQuery(
                node,
                isNodeReferenced=True
            )
        )
    except Exception:
        return False


def _node_is_locked(node):
    try:
        values = cmds.lockNode(
            node,
            query=True,
            lock=True
        ) or []

        return bool(values and values[0])
    except Exception:
        return False


def _camera_shape(node):
    if not node or not cmds.objExists(node):
        raise RuntimeError(
            "Camera node does not exist: {}".format(
                node or "<empty>"
            )
        )

    if cmds.nodeType(node) == "camera":
        return node

    shapes = cmds.listRelatives(
        node,
        shapes=True,
        type="camera",
        fullPath=True
    ) or []

    if not shapes:
        raise RuntimeError(
            "Node is not a camera transform: {}".format(
                node
            )
        )

    return shapes[0]


def _set_string_or_enum(plug, value):
    if not cmds.objExists(plug):
        raise RuntimeError(
            "Attribute does not exist: {}".format(
                plug
            )
        )

    attribute_type = cmds.getAttr(
        plug,
        type=True
    )

    if attribute_type == "string":
        cmds.setAttr(
            plug,
            str(value),
            type="string"
        )
        return

    if attribute_type == "enum":
        node, attribute = plug.rsplit(".", 1)
        enum_data = cmds.attributeQuery(
            attribute,
            node=node,
            listEnum=True
        ) or []

        options = (
            enum_data[0].split(":")
            if enum_data
            else []
        )

        lowered = [
            item.lower()
            for item in options
        ]

        try:
            index = lowered.index(
                str(value).lower()
            )
        except ValueError:
            raise RuntimeError(
                "Value '{}' is not available for {}. "
                "Available values: {}".format(
                    value,
                    plug,
                    ", ".join(options) or "unknown"
                )
            )

        cmds.setAttr(
            plug,
            index
        )
        return

    # Several Maya/Arnold color-space attributes report a custom type but
    # still accept a string. Try the safe string setter before a direct value.
    try:
        cmds.setAttr(
            plug,
            str(value),
            type="string"
        )
    except Exception:
        cmds.setAttr(
            plug,
            value
        )



def _fix_set_arnold_renderer(result):
    try:
        if not cmds.pluginInfo("mtoa", query=True, registered=True):
            raise RuntimeError("Arnold for Maya (mtoa) is not installed.")
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("Could not verify the Arnold for Maya plugin.")

    try:
        if not cmds.pluginInfo("mtoa", query=True, loaded=True):
            cmds.loadPlugin("mtoa", quiet=True)
    except Exception as error:
        raise RuntimeError("Could not load Arnold for Maya: {}".format(error))

    cmds.setAttr(
        "defaultRenderGlobals.currentRenderer",
        "arnold",
        type="string",
    )
    return "Scene renderer set to Arnold."

def _fix_load_mtoa(result):
    try:
        if cmds.pluginInfo(
            "mtoa",
            query=True,
            loaded=True
        ):
            return "Arnold is already loaded."
    except Exception:
        pass

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

    if not registered:
        raise RuntimeError(
            "Arnold for Maya (mtoa) is not installed."
        )

    cmds.loadPlugin(
        "mtoa",
        quiet=True
    )

    if not cmds.pluginInfo(
        "mtoa",
        query=True,
        loaded=True
    ):
        raise RuntimeError(
            "Maya did not load the mtoa plugin."
        )

    return "Arnold for Maya was loaded."


def _fix_camera_renderable(result):
    node = (
        result.get("node")
        or (result.get("data") or {}).get("camera")
        or ""
    )

    shape = _camera_shape(node)
    plug = shape + ".renderable"

    if bool(cmds.getAttr(plug)):
        return "Camera is already renderable: {}.".format(
            node
        )

    cmds.setAttr(
        plug,
        1
    )

    return "Camera marked renderable: {}.".format(
        node
    )


def _fix_output_folder(result):
    data = result.get("data") or {}
    path = data.get("path") or ""

    path = os.path.abspath(
        os.path.expandvars(
            os.path.expanduser(path)
        )
    ) if path else ""

    if not path:
        raise RuntimeError(
            "The validation result does not contain an output path."
        )

    if os.path.exists(path):
        if not os.path.isdir(path):
            raise RuntimeError(
                "The output path exists but is not a folder: {}".format(
                    path
                )
            )

        return "Output folder already exists: {}.".format(
            path
        )

    parent = os.path.dirname(path)

    if not parent or not os.path.isdir(parent):
        raise RuntimeError(
            "The output folder parent does not exist: {}".format(
                parent or "<empty>"
            )
        )

    if not os.access(parent, os.W_OK):
        raise RuntimeError(
            "The output folder parent is not writable: {}".format(
                parent
            )
        )

    os.makedirs(
        path
    )

    return "Output folder created: {}.".format(
        path
    )


def _fix_render_region(result):
    plug = "defaultRenderGlobals.useRenderRegion"

    if not cmds.objExists(plug):
        raise RuntimeError(
            "Render Region attribute is unavailable in this Maya scene."
        )

    if not bool(cmds.getAttr(plug)):
        return "Render Region is already disabled."

    cmds.setAttr(
        plug,
        0
    )

    return "Render Region was disabled."


def _fix_texture_color_space(result):
    data = result.get("data") or {}
    node = data.get("node") or result.get("node") or ""
    attribute = data.get("color_space_attr") or ""
    expected = data.get("expected_color_space") or ""

    if not node or not attribute or not expected:
        raise RuntimeError(
            "Texture color-space validation data is incomplete."
        )

    if not cmds.objExists(node):
        raise RuntimeError(
            "Texture node does not exist: {}".format(
                node
            )
        )

    if _node_is_referenced(node):
        raise RuntimeError(
            "Referenced texture nodes are not modified automatically: {}".format(
                node
            )
        )

    plug = "{}.{}".format(
        node,
        attribute
    )

    _set_string_or_enum(
        plug,
        expected
    )

    return "Set {} to '{}'.".format(
        plug,
        expected
    )


def _fix_shape_name(result):
    data = result.get("data") or {}
    shape = data.get("shape") or result.get("node") or ""
    expected = data.get("expected_shape_name") or ""

    if not shape or not expected:
        raise RuntimeError(
            "Shape rename validation data is incomplete."
        )

    if not cmds.objExists(shape):
        raise RuntimeError(
            "Shape node does not exist: {}".format(
                shape
            )
        )

    if _node_is_referenced(shape):
        raise RuntimeError(
            "Referenced shapes are not renamed automatically: {}".format(
                shape
            )
        )

    if _node_is_locked(shape):
        raise RuntimeError(
            "Shape node is locked: {}".format(
                shape
            )
        )

    leaf = shape.rsplit("|", 1)[-1]

    if leaf == expected:
        return "Shape already has the expected name: {}.".format(
            expected
        )

    matching_nodes = cmds.ls(
        expected,
        long=True
    ) or []

    if matching_nodes:
        raise RuntimeError(
            "The expected shape name already exists: {}".format(
                expected
            )
        )

    renamed = cmds.rename(
        shape,
        expected
    )

    return "Shape renamed to {}.".format(
        renamed
    )


def _fix_save_scene(result):
    scene_path = cmds.file(
        query=True,
        sceneName=True
    ) or ""

    if not scene_path:
        raise RuntimeError(
            "The scene has not been saved before. Use Save As first."
        )

    if not cmds.file(
        query=True,
        modified=True
    ):
        return "The Maya scene is already saved."

    cmds.file(
        save=True
    )

    return "Maya scene saved: {}.".format(
        scene_path
    )


FIXERS = {
    "set_arnold_renderer": _fix_set_arnold_renderer,
    "load_mtoa": _fix_load_mtoa,
    "make_camera_renderable": _fix_camera_renderable,
    "create_output_folder": _fix_output_folder,
    "disable_render_region": _fix_render_region,
    "set_texture_color_space": _fix_texture_color_space,
    "rename_shape": _fix_shape_name,
    "save_scene": _fix_save_scene,
}


def _execute_fix(result):
    if not can_fix_result(result):
        return {
            "success": False,
            "changed": False,
            "message": "No safe auto-fix is registered for this result.",
            "result": result,
        }

    group_name, settings = _group_for_code(
        result.get("code")
    )

    fixer = FIXERS.get(group_name)

    if fixer is None:
        return {
            "success": False,
            "changed": False,
            "message": "The auto-fix handler is missing: {}.".format(
                group_name
            ),
            "result": result,
        }

    message = fixer(result)

    return {
        "success": True,
        "changed": True,
        "message": message,
        "group": group_name,
        "undoable": bool(settings.get("undoable")),
        "result": result,
    }


def apply_fix(result):
    group_name, settings = _group_for_code(
        result.get("code") if isinstance(result, dict) else ""
    )

    if not group_name or not settings:
        return {
            "success": False,
            "changed": False,
            "message": "No auto-fix is registered for this result.",
            "result": result,
        }

    opened_chunk = False

    try:
        if settings.get("undoable"):
            cmds.undoInfo(
                openChunk=True,
                chunkName="RenderHive Auto Fix"
            )
            opened_chunk = True

        return _execute_fix(result)

    except Exception as error:
        return {
            "success": False,
            "changed": False,
            "message": str(error),
            "group": group_name,
            "result": result,
        }

    finally:
        if opened_chunk:
            cmds.undoInfo(
                closeChunk=True
            )


def apply_many(results):
    results = collect_batch_safe(results)

    outcomes = []
    opened_chunk = False

    try:
        undoable_found = False

        for result in results:
            _, settings = _group_for_code(
                result.get("code")
            )

            if settings and settings.get("undoable"):
                undoable_found = True
                break

        if undoable_found:
            cmds.undoInfo(
                openChunk=True,
                chunkName="RenderHive Fix All Safe"
            )
            opened_chunk = True

        for result in results:
            try:
                outcomes.append(
                    _execute_fix(result)
                )
            except Exception as error:
                outcomes.append({
                    "success": False,
                    "changed": False,
                    "message": str(error),
                    "result": result,
                })

    finally:
        if opened_chunk:
            cmds.undoInfo(
                closeChunk=True
            )

    return outcomes
