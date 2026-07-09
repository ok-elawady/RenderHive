import os
import json
import maya.cmds as cmds


WINDOW_NAME = "renderHiveMayaSubmitter"


# ============================================================
# MAYA HELPERS
# ============================================================

def get_scene_path():
    return cmds.file(query=True, sceneName=True) or ""


def get_project_path():
    try:
        return cmds.workspace(query=True, rootDirectory=True)
    except Exception:
        return ""


def get_default_output_path():
    project_path = get_project_path()

    if project_path:
        return os.path.join(project_path, "images")

    scene_path = get_scene_path()

    if scene_path:
        return os.path.join(os.path.dirname(scene_path), "images")

    return ""


def get_scene_name():
    scene_path = get_scene_path()

    if scene_path:
        return os.path.splitext(os.path.basename(scene_path))[0]

    return "maya_job"


def get_frame_range():
    try:
        start = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
        end = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
        return start, end
    except Exception:
        return 1, 1


def get_resolution():
    try:
        width = int(cmds.getAttr("defaultResolution.width"))
        height = int(cmds.getAttr("defaultResolution.height"))
        return width, height
    except Exception:
        return 1280, 720


def get_current_renderer():
    try:
        return cmds.getAttr("defaultRenderGlobals.currentRenderer")
    except Exception:
        return "arnold"


def get_cameras():
    cameras = []
    camera_shapes = cmds.ls(type="camera") or []

    for shape in camera_shapes:
        parent = cmds.listRelatives(shape, parent=True) or []
        if parent:
            cameras.append(parent[0])

    return cameras


def get_renderable_camera():
    camera_shapes = cmds.ls(type="camera") or []

    for shape in camera_shapes:
        try:
            if cmds.getAttr(shape + ".renderable"):
                parent = cmds.listRelatives(shape, parent=True) or []
                if parent:
                    return parent[0]
        except Exception:
            pass

    cameras = get_cameras()

    if "renderCam" in cameras:
        return "renderCam"

    if cameras:
        return cameras[0]

    return "NoCamera"


# ============================================================
# UI FIELD HELPERS
# ============================================================

def get_text(name):
    return cmds.textField(name, query=True, text=True)


def set_text(name, value):
    cmds.textField(name, edit=True, text=value)


def get_int(name):
    return int(cmds.intField(name, query=True, value=True))


def set_int(name, value):
    cmds.intField(name, edit=True, value=int(value))


def get_option(name):
    return cmds.optionMenu(name, query=True, value=True)


# ============================================================
# UI ACTIONS
# ============================================================

def browse_output_path(*args):
    selected = cmds.fileDialog2(
        fileMode=3,
        caption="Select Output Folder"
    )

    if selected:
        set_text("rh_output_path", selected[0])


def rebuild_camera_menu():
    menu = "rh_camera"

    items = cmds.optionMenu(menu, query=True, itemListLong=True) or []

    for item in items:
        cmds.deleteUI(item)

    cameras = get_cameras()

    if not cameras:
        cmds.menuItem(label="NoCamera", parent=menu)
        return

    for cam in cameras:
        cmds.menuItem(label=cam, parent=menu)

    renderable = get_renderable_camera()

    if renderable in cameras:
        cmds.optionMenu(menu, edit=True, value=renderable)


def refresh_from_scene(*args):
    scene_name = get_scene_name()
    start, end = get_frame_range()
    width, height = get_resolution()

    set_text("rh_job_name", scene_name)
    set_text("rh_scene_path", get_scene_path())
    set_text("rh_project_path", get_project_path())
    set_text("rh_output_path", get_default_output_path())
    set_text("rh_image_name", scene_name)

    set_int("rh_frame_start", start)
    set_int("rh_frame_end", end)
    set_int("rh_width", width)
    set_int("rh_height", height)

    current_renderer = get_current_renderer()

    if current_renderer in ["arnold", "sw"]:
        cmds.optionMenu("rh_renderer", edit=True, value=current_renderer)

    rebuild_camera_menu()


# ============================================================
# TASK
# ============================================================

def build_task():
    task = {
        "job_id": 1,
        "task_id": 1,

        "job_name": get_text("rh_job_name"),
        "project_name": get_text("rh_project_name"),

        "software": "maya",

        "scene_path": get_text("rh_scene_path"),
        "project_path": get_text("rh_project_path"),
        "output_path": get_text("rh_output_path"),

        "frame_start": get_int("rh_frame_start"),
        "frame_end": get_int("rh_frame_end"),

        "renderer": get_option("rh_renderer"),
        "camera": get_option("rh_camera"),

        "image_name": get_text("rh_image_name"),
        "image_format": get_option("rh_image_format"),
        "frame_padding": get_int("rh_frame_padding"),

        "width": get_int("rh_width"),
        "height": get_int("rh_height"),

        "priority": get_int("rh_priority")
    }

    return task


def validate_task(task):
    errors = []

    if not task["job_name"]:
        errors.append("Job name is empty.")

    if not task["scene_path"]:
        errors.append("Scene path is empty. Please save the Maya scene first.")

    elif not os.path.exists(task["scene_path"]):
        errors.append("Scene file does not exist:\n" + task["scene_path"])

    if not task["project_path"]:
        errors.append("Project path is empty.")

    elif not os.path.exists(task["project_path"]):
        errors.append("Project path does not exist:\n" + task["project_path"])

    if not task["output_path"]:
        errors.append("Output path is empty.")

    if task["frame_start"] > task["frame_end"]:
        errors.append("Frame start cannot be greater than frame end.")

    if not task["camera"] or task["camera"] == "NoCamera":
        errors.append("No valid camera selected.")

    if not task["image_name"]:
        errors.append("Image name is empty.")

    return errors


def show_error_dialog(errors):
    message = "\n".join("- " + error for error in errors)

    cmds.confirmDialog(
        title="RenderHive Validation Failed",
        message=message,
        button=["OK"],
        icon="critical"
    )


def save_task_json(*args):
    task = build_task()
    errors = validate_task(task)

    if errors:
        show_error_dialog(errors)
        return

    selected = cmds.fileDialog2(
        fileMode=0,
        caption="Save RenderHive Task JSON",
        fileFilter="JSON Files (*.json)"
    )

    if not selected:
        return

    json_path = selected[0]

    if not json_path.lower().endswith(".json"):
        json_path += ".json"

    folder = os.path.dirname(json_path)

    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=4)

    cmds.confirmDialog(
        title="RenderHive",
        message="Task JSON saved successfully:\n\n" + json_path,
        button=["OK"],
        icon="information"
    )


# ============================================================
# UI
# ============================================================

def show_submitter():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    scene_name = get_scene_name()
    start, end = get_frame_range()
    width, height = get_resolution()

    window = cmds.window(
        WINDOW_NAME,
        title="RenderHive Maya Submitter",
        widthHeight=(520, 560),
        sizeable=True
    )

    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

    cmds.text(
        label="RenderHive Maya Submitter",
        height=35,
        align="center"
    )

    cmds.separator(height=10, style="in")

    cmds.rowColumnLayout(
        numberOfColumns=2,
        columnWidth=[(1, 140), (2, 340)],
        columnSpacing=[(1, 8), (2, 8)]
    )

    cmds.text(label="Project Name")
    cmds.textField("rh_project_name", text="RenderHive Demo")

    cmds.text(label="Job Name")
    cmds.textField("rh_job_name", text=scene_name)

    cmds.text(label="Scene Path")
    cmds.textField("rh_scene_path", text=get_scene_path())

    cmds.text(label="Project Path")
    cmds.textField("rh_project_path", text=get_project_path())

    cmds.text(label="Output Path")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(255, 80))
    cmds.textField("rh_output_path", text=get_default_output_path(), width=255)
    cmds.button(label="Browse", width=80, command=browse_output_path)
    cmds.setParent("..")

    cmds.text(label="Frame Start")
    cmds.intField("rh_frame_start", value=start)

    cmds.text(label="Frame End")
    cmds.intField("rh_frame_end", value=end)

    cmds.text(label="Renderer")
    cmds.optionMenu("rh_renderer")
    cmds.menuItem(label="arnold")
    cmds.menuItem(label="sw")

    current_renderer = get_current_renderer()
    if current_renderer in ["arnold", "sw"]:
        cmds.optionMenu("rh_renderer", edit=True, value=current_renderer)

    cmds.text(label="Camera")
    cmds.optionMenu("rh_camera")
    cmds.menuItem(label="Loading")

    cmds.text(label="Image Name")
    cmds.textField("rh_image_name", text=scene_name)

    cmds.text(label="Image Format")
    cmds.optionMenu("rh_image_format")
    cmds.menuItem(label="png")
    cmds.menuItem(label="jpg")
    cmds.menuItem(label="exr")

    cmds.text(label="Frame Padding")
    cmds.intField("rh_frame_padding", value=4)

    cmds.text(label="Width")
    cmds.intField("rh_width", value=width)

    cmds.text(label="Height")
    cmds.intField("rh_height", value=height)

    cmds.text(label="Priority")
    cmds.intField("rh_priority", value=50)

    cmds.setParent("..")

    cmds.separator(height=12, style="in")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(250, 250))

    cmds.button(
        label="Refresh From Scene",
        height=35,
        command=refresh_from_scene
    )

    cmds.button(
        label="Save Task JSON",
        height=35,
        command=save_task_json
    )

    cmds.setParent("..")

    cmds.separator(height=10, style="in")

    cmds.text(
        label="V1: Save JSON only. Backend submit will be added later.",
        align="center",
        height=25
    )

    cmds.showWindow(window)

    rebuild_camera_menu()