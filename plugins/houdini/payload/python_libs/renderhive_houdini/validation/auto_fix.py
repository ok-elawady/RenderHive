"""Safe Houdini validation fixes used by the submitter UI."""

from __future__ import absolute_import

import os

_FIX_LABELS = {
    "SCENE_UNSAVED": "Save HIP File",
    "SCENE_DIRTY": "Save HIP File",
    "JOB_NOT_SET": "Set $JOB",
    "PROJECT_INVALID": "Set $JOB from $HIP",
    "RENDER_NODE_BYPASSED": "Enable Render Node",
    "FRAME_STEP_INVALID": "Set Frame Step to 1",
    "OUTPUT_DIRECTORY_MISSING": "Create Output Directory",
    "OUTPUT_MISSING": "Set Default Output",
    "RESOLUTION_INVALID": "Set 1920 × 1080",
}


def can_fix_result(result):
    return bool(getattr(result, "fixable", False) and str(getattr(result, "code", "")) in _FIX_LABELS)


def is_batch_safe(result):
    return bool(can_fix_result(result) and getattr(result, "batch_safe", False))


def requires_confirmation(result):
    return bool(getattr(result, "requires_confirmation", False))


def fix_label(result):
    return _FIX_LABELS.get(str(getattr(result, "code", "")), "Apply Fix")


def collect_batch_safe(results):
    return [item for item in (results or []) if is_batch_safe(item)]


def _node(path):
    import hou
    return hou.node(str(path or "")) if path else None


def _set_first(node, names, value):
    if node is None:
        return False
    for name in names:
        try:
            parm = node.parm(name)
            if parm is not None:
                parm.set(value)
                return True
        except Exception:
            continue
    return False


def _save_scene():
    import hou
    path = str(hou.hipFile.path() or "")
    if not path or hou.hipFile.isNewFile():
        selected = hou.ui.selectFile(
            title="Save RenderHive HIP File",
            file_type=hou.fileType.Hip,
            chooser_mode=hou.fileChooserMode.Write,
        )
        if not selected:
            return False, "Save was cancelled."
        path = str(selected)
    hou.hipFile.save(path)
    return True, "HIP file saved."


def _set_job(path):
    import hou
    path = str(path or hou.getenv("HIP") or "").strip()
    if not path:
        return False, "$HIP is empty, so $JOB could not be set."
    hou.putenv("JOB", path)
    return True, "$JOB set to {}.".format(path)


def _create_output(path):
    path = str(path or "").strip()
    if not path:
        return False, "Output directory is empty."
    if not os.path.isdir(path):
        os.makedirs(path)
    return True, "Output directory created: {}".format(path)


def _unbypass(path):
    node = _node(path)
    if node is None:
        return False, "Render node no longer exists."
    node.bypass(False)
    return True, "Render node enabled: {}".format(path)


def _fix_frame_step(path):
    node = _node(path)
    if _set_first(node, ("f3", "step", "increment"), 1):
        return True, "Frame step set to 1."
    return False, "No writable frame-step parameter was found."


def _fix_resolution(path, width, height):
    node = _node(path)
    width_ok = _set_first(node, ("res1", "width", "resolutionx", "resx"), int(width))
    height_ok = _set_first(node, ("res2", "height", "resolutiony", "resy"), int(height))
    if width_ok and height_ok:
        return True, "Resolution set to {} × {}.".format(width, height)
    return False, "No writable resolution parameters were found."


def _fix_output(path):
    import hou
    node = _node(path)
    if node is None:
        return False, "Render node no longer exists."
    default_path = "$JOB/render/{}.$F4.exr".format(node.name())
    if _set_first(node, (
        "vm_picture", "ar_picture", "RS_outputFileNamePrefix", "picture",
        "outputimage", "productname", "output_file", "outputfile",
    ), default_path):
        return True, "Default output set to {}.".format(default_path)
    return False, "No writable image-output parameter was found."


def apply_fix(result):
    code = str(getattr(result, "code", "") or "")
    data = dict(getattr(result, "data", {}) or {})
    try:
        if code in ("SCENE_UNSAVED", "SCENE_DIRTY"):
            return _save_scene()
        if code in ("JOB_NOT_SET", "PROJECT_INVALID"):
            return _set_job(data.get("path") or data.get("suggested_path"))
        if code == "OUTPUT_DIRECTORY_MISSING":
            return _create_output(data.get("path"))
        if code == "RENDER_NODE_BYPASSED":
            return _unbypass(data.get("node_path") or getattr(result, "node_path", ""))
        if code == "FRAME_STEP_INVALID":
            return _fix_frame_step(data.get("node_path") or getattr(result, "node_path", ""))
        if code == "RESOLUTION_INVALID":
            return _fix_resolution(
                data.get("node_path") or getattr(result, "node_path", ""),
                data.get("width", 1920), data.get("height", 1080),
            )
        if code == "OUTPUT_MISSING":
            return _fix_output(data.get("node_path") or getattr(result, "node_path", ""))
        return False, "No Auto Fix is available for {}.".format(code or "this result")
    except Exception as error:
        return False, "{} failed: {}".format(fix_label(result), error)


def apply_many(results):
    messages = []
    success_count = 0
    for result in results or []:
        success, message = apply_fix(result)
        messages.append(message)
        if success:
            success_count += 1
    return {
        "success_count": success_count,
        "failure_count": len(messages) - success_count,
        "messages": messages,
    }
