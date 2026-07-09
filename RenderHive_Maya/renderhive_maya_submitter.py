import os
import sys
import json
import time
import subprocess

import maya.cmds as cmds


WINDOW_NAME = "renderHiveMayaSubmitter"


# ============================================================
# PATHS
# ============================================================

def get_submitter_dir():
    return os.path.dirname(os.path.abspath(__file__))


def get_install_root():
    """
    المكان اللي السكربت شغال منه حاليًا.
    غالبًا هيكون:
    C:/Users/.../Documents/maya/2023/scripts/RenderHive
    بعد الـdrag and drop install.
    """
    return get_submitter_dir()


def get_install_info_path():
    return os.path.join(get_install_root(), "renderhive_install_info.json")


def get_original_package_root():
    """
    لو الأداة شغالة من نسخة Maya Documents/scripts،
    نقرأ الباث الأصلي اللي اتعمل منه drag and drop install.

    المفروض يرجع:
    D:/Moemen/iti/CGTD/RenderHiveProject/RenderHive_Maya

    لو الملف مش موجود، يرجع install root كـfallback.
    """

    info_path = get_install_info_path()

    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            source_dir = data.get("source_dir")

            if source_dir and os.path.exists(source_dir):
                return os.path.abspath(source_dir)

        except Exception:
            pass

    return get_install_root()


def get_repo_root():
    """
    يدور على root فيه worker/worker.py.
    الأول يحاول الـOriginal Package Root،
    وبعدها يحاول مكان التثبيت.
    """

    candidates = [
        get_original_package_root(),
        get_install_root(),
        os.path.abspath(os.path.join(get_submitter_dir(), "..")),
        os.path.abspath(os.path.join(get_submitter_dir(), "..", "..")),
    ]

    for candidate in candidates:
        worker_script = os.path.join(candidate, "worker", "worker.py")

        if os.path.exists(worker_script):
            return candidate

    return get_original_package_root()


def get_worker_dir():
    return os.path.join(get_repo_root(), "worker")


def get_worker_script():
    return os.path.join(get_worker_dir(), "worker.py")


def get_worker_tasks_dir():
    return os.path.join(get_worker_dir(), "tasks")


def get_mayapy_path():
    """
    يحاول يجيب mayapy من نفس Maya اللي فاتح منه الأداة.
    """

    maya_bin = os.path.dirname(sys.executable)
    mayapy = os.path.join(maya_bin, "mayapy.exe")

    if os.path.exists(mayapy):
        return mayapy

    return "mayapy"


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


def get_scene_name():
    scene_path = get_scene_path()

    if scene_path:
        return os.path.splitext(os.path.basename(scene_path))[0]

    return "maya_job"


def get_default_output_path():
    project_path = get_project_path()

    if project_path:
        return os.path.join(project_path, "images")

    scene_path = get_scene_path()

    if scene_path:
        return os.path.join(os.path.dirname(scene_path), "images")

    return ""


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
        parents = cmds.listRelatives(shape, parent=True) or []

        if parents:
            cameras.append(parents[0])

    return cameras


def get_renderable_camera():
    """
    نفضل renderCam لو موجودة، عشان مايا ساعات بتخلي persp renderable.
    """

    cameras = get_cameras()

    if "renderCam" in cameras:
        return "renderCam"

    camera_shapes = cmds.ls(type="camera") or []

    for shape in camera_shapes:
        try:
            if cmds.getAttr(shape + ".renderable"):
                parents = cmds.listRelatives(shape, parent=True) or []

                if parents:
                    return parents[0]

        except Exception:
            pass

    if cameras:
        return cameras[0]

    return "NoCamera"


def save_scene_if_needed():
    scene_path = get_scene_path()

    if not scene_path:
        return False, "Scene is not saved. Please save the Maya scene first."

    modified = cmds.file(query=True, modified=True)

    if modified:
        result = cmds.confirmDialog(
            title="Save Scene",
            message="Scene has unsaved changes. Save before creating the task?",
            button=["Save", "Cancel"],
            defaultButton="Save",
            cancelButton="Cancel",
            dismissString="Cancel"
        )

        if result != "Save":
            return False, "Scene was not saved."

        cmds.file(save=True)

    return True, ""


# ============================================================
# UI HELPERS
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


def safe_name(name):
    clean = ""

    for char in name:
        if char.isalnum() or char in ["_", "-"]:
            clean += char
        else:
            clean += "_"

    return clean.strip("_") or "maya_job"


def open_folder(path):
    if not path:
        cmds.confirmDialog(
            title="RenderHive",
            message="Path is empty.",
            button=["OK"],
            icon="warning"
        )
        return

    if not os.path.exists(path):
        os.makedirs(path)

    try:
        os.startfile(path)
    except Exception as e:
        cmds.confirmDialog(
            title="RenderHive",
            message="Could not open folder:\n{}\n\n{}".format(path, e),
            button=["OK"],
            icon="warning"
        )


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


def open_output_folder(*args):
    open_folder(get_text("rh_output_path"))


def open_tasks_folder(*args):
    open_folder(get_worker_tasks_dir())


def open_diagnostics_folder(*args):
    open_folder(get_diagnostics_folder())


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

    if current_renderer in ["arnold", "sw", "mayaHardware2"]:
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

    if task["frame_padding"] < 1:
        errors.append("Frame padding must be at least 1.")

    if task["width"] <= 0 or task["height"] <= 0:
        errors.append("Resolution must be greater than zero.")

    return errors


def show_error_dialog(errors):
    message = "\n".join("- " + error for error in errors)

    cmds.confirmDialog(
        title="RenderHive Validation Failed",
        message=message,
        button=["OK"],
        icon="critical"
    )


def get_auto_task_path(task):
    tasks_dir = get_worker_tasks_dir()

    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)

    job_name = safe_name(task["job_name"])
    frame_start = task["frame_start"]
    frame_end = task["frame_end"]
    stamp = time.strftime("%Y%m%d_%H%M%S")

    filename = "{}_{}_{}_{}.json".format(
        job_name,
        frame_start,
        frame_end,
        stamp
    )

    return os.path.join(tasks_dir, filename)


def write_task_json(path, task):
    folder = os.path.dirname(path)

    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=4)


def save_task_json_auto(*args):
    ok, message = save_scene_if_needed()

    if not ok:
        cmds.confirmDialog(
            title="RenderHive",
            message=message,
            button=["OK"],
            icon="warning"
        )
        return None

    refresh_from_scene()

    task = build_task()
    errors = validate_task(task)

    if errors:
        show_error_dialog(errors)
        return None

    json_path = get_auto_task_path(task)
    write_task_json(json_path, task)

    cmds.confirmDialog(
        title="RenderHive",
        message="Task JSON saved automatically:\n\n" + json_path,
        button=["OK"],
        icon="information"
    )

    return json_path


def save_task_json_as(*args):
    ok, message = save_scene_if_needed()

    if not ok:
        cmds.confirmDialog(
            title="RenderHive",
            message=message,
            button=["OK"],
            icon="warning"
        )
        return

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

    write_task_json(json_path, task)

    cmds.confirmDialog(
        title="RenderHive",
        message="Task JSON saved successfully:\n\n" + json_path,
        button=["OK"],
        icon="information"
    )


def run_local_worker(*args):
    json_path = save_task_json_auto()

    if not json_path:
        return

    worker_script = get_worker_script()
    worker_dir = get_worker_dir()
    mayapy = get_mayapy_path()

    if not os.path.exists(worker_script):
        cmds.confirmDialog(
            title="RenderHive",
            message="Worker script not found:\n" + worker_script,
            button=["OK"],
            icon="critical"
        )
        return

    command = [
        mayapy,
        worker_script,
        "--task",
        json_path
    ]

    try:
        creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

        subprocess.Popen(
            command,
            cwd=worker_dir,
            creationflags=creation_flags
        )

        cmds.confirmDialog(
            title="RenderHive",
            message="Local worker started.\n\nTask:\n" + json_path,
            button=["OK"],
            icon="information"
        )

    except Exception as e:
        cmds.confirmDialog(
            title="RenderHive Worker Failed",
            message=str(e),
            button=["OK"],
            icon="critical"
        )


# ============================================================
# DIAGNOSTICS
# ============================================================

def get_diagnostics_folder():
    """
    Diagnostics logs تتحفظ في فولدر الباكدج الأصلي RenderHive_Maya،
    مش جوه Maya project folder ولا Render folder.
    """

    folder = os.path.join(
        get_original_package_root(),
        "logs",
        "diagnostics"
    )

    if not os.path.exists(folder):
        os.makedirs(folder)

    return folder


def generate_diagnostics_log(*args):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_folder = get_diagnostics_folder()

    log_path = os.path.join(
        log_folder,
        "renderhive_submitter_diagnostics_{}.txt".format(timestamp)
    )

    lines = []

    def add(label, value=""):
        lines.append("{}: {}".format(label, value))

    lines.append("=" * 80)
    lines.append("RenderHive Maya Submitter Diagnostics")
    lines.append("=" * 80)
    lines.append("")

    add("Maya Version", cmds.about(version=True))
    add("Maya API Version", cmds.about(apiVersion=True))
    add("Maya Executable", sys.executable)
    add("Submitter Dir", get_submitter_dir())
    add("Install Root", get_install_root())
    add("Install Info Path", get_install_info_path())
    add("Original Package Root", get_original_package_root())
    add("Diagnostics Folder", get_diagnostics_folder())
    add("Repo Root", get_repo_root())
    add("Worker Dir", get_worker_dir())
    add("Worker Script", get_worker_script())
    add("Worker Tasks Dir", get_worker_tasks_dir())
    add("Mayapy Path", get_mayapy_path())

    lines.append("")
    lines.append("Scene Information")
    lines.append("-" * 80)

    add("Scene Path", get_scene_path())
    add("Project Path", get_project_path())
    add("Output Path", get_default_output_path())
    add("Current Renderer", get_current_renderer())

    start, end = get_frame_range()
    add("Frame Range", "{} - {}".format(start, end))

    width, height = get_resolution()
    add("Resolution", "{} x {}".format(width, height))

    lines.append("")
    lines.append("Cameras")
    lines.append("-" * 80)

    cameras = get_cameras()
    renderable = get_renderable_camera()

    if cameras:
        for cam in cameras:
            add("Camera", cam)
    else:
        lines.append("No cameras found.")

    add("Selected Renderable Camera", renderable)

    lines.append("")
    lines.append("Arnold Check")
    lines.append("-" * 80)

    try:
        arnold_loaded = cmds.pluginInfo("mtoa", query=True, loaded=True)
    except Exception:
        arnold_loaded = False

    add("mtoa Loaded", arnold_loaded)

    try:
        arnold_path = cmds.pluginInfo("mtoa", query=True, path=True)
    except Exception:
        arnold_path = "Not found"

    add("mtoa Path", arnold_path)

    lines.append("")
    lines.append("Loaded Plugins")
    lines.append("-" * 80)

    loaded_plugins = cmds.pluginInfo(query=True, listPlugins=True) or []

    if loaded_plugins:
        for plugin in loaded_plugins:
            lines.append(plugin)
    else:
        lines.append("No loaded plugins found.")

    lines.append("")
    lines.append("Potential Side Plugins")
    lines.append("-" * 80)

    side_keywords = [
        "zoo",
        "mgear",
        "ngskintools",
        "redshift",
        "vray",
        "renderman",
        "yeti",
        "xgen"
    ]

    found_side_plugins = []

    for plugin in loaded_plugins:
        low = plugin.lower()

        for keyword in side_keywords:
            if keyword in low:
                found_side_plugins.append(plugin)

    if found_side_plugins:
        for plugin in found_side_plugins:
            lines.append(plugin)
    else:
        lines.append("No obvious side plugins detected.")

    lines.append("")
    lines.append("Path Checks")
    lines.append("-" * 80)

    path_checks = {
        "Scene Exists": get_scene_path(),
        "Project Exists": get_project_path(),
        "Worker Script Exists": get_worker_script(),
        "Worker Dir Exists": get_worker_dir(),
        "Tasks Dir Exists": get_worker_tasks_dir(),
        "Mayapy Exists": get_mayapy_path(),
        "Original Package Root Exists": get_original_package_root(),
        "Diagnostics Folder Exists": get_diagnostics_folder(),
    }

    for label, path in path_checks.items():
        if path:
            add(label, "{} | {}".format(os.path.exists(path), path))
        else:
            add(label, "False | Empty path")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    try:
        os.startfile(log_path)
    except Exception:
        pass

    cmds.confirmDialog(
        title="RenderHive Diagnostics",
        message="Diagnostics log generated:\n\n{}".format(log_path),
        button=["OK"],
        icon="information"
    )

    return log_path


# ============================================================
# UNINSTALL
# ============================================================

def uninstall_renderhive_from_maya(*args):
    try:
        import importlib

        submitter_dir = get_submitter_dir()

        if submitter_dir not in sys.path:
            sys.path.insert(0, submitter_dir)

        import renderhive_installer
        importlib.reload(renderhive_installer)

        renderhive_installer.uninstall_renderhive(confirm=True)

    except Exception as e:
        cmds.confirmDialog(
            title="RenderHive Uninstall Failed",
            message=str(e),
            button=["OK"],
            icon="critical"
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
        widthHeight=(580, 780),
        sizeable=True
    )

    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

    cmds.text(
        label="RenderHive Maya Submitter",
        height=38,
        align="center"
    )

    cmds.separator(height=8, style="in")

    # ---------------- Job Info ----------------

    cmds.frameLayout(
        label="Job Info",
        collapsable=True,
        collapse=False,
        marginWidth=8,
        marginHeight=8
    )

    cmds.rowColumnLayout(
        numberOfColumns=2,
        columnWidth=[(1, 150), (2, 390)],
        columnSpacing=[(1, 8), (2, 8)]
    )

    cmds.text(label="Project Name")
    cmds.textField("rh_project_name", text="RenderHive Demo")

    cmds.text(label="Job Name")
    cmds.textField("rh_job_name", text=scene_name)

    cmds.text(label="Priority")
    cmds.intField("rh_priority", value=50)

    cmds.setParent("..")
    cmds.setParent("..")

    # ---------------- Paths ----------------

    cmds.frameLayout(
        label="Paths",
        collapsable=True,
        collapse=False,
        marginWidth=8,
        marginHeight=8
    )

    cmds.rowColumnLayout(
        numberOfColumns=2,
        columnWidth=[(1, 150), (2, 390)],
        columnSpacing=[(1, 8), (2, 8)]
    )

    cmds.text(label="Scene Path")
    cmds.textField("rh_scene_path", text=get_scene_path())

    cmds.text(label="Project Path")
    cmds.textField("rh_project_path", text=get_project_path())

    cmds.text(label="Output Path")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(280, 100))
    cmds.textField("rh_output_path", text=get_default_output_path(), width=280)
    cmds.button(label="Browse", width=100, command=browse_output_path)
    cmds.setParent("..")

    cmds.setParent("..")
    cmds.setParent("..")

    # ---------------- Render Settings ----------------

    cmds.frameLayout(
        label="Render Settings",
        collapsable=True,
        collapse=False,
        marginWidth=8,
        marginHeight=8
    )

    cmds.rowColumnLayout(
        numberOfColumns=2,
        columnWidth=[(1, 150), (2, 390)],
        columnSpacing=[(1, 8), (2, 8)]
    )

    cmds.text(label="Frame Start")
    cmds.intField("rh_frame_start", value=start)

    cmds.text(label="Frame End")
    cmds.intField("rh_frame_end", value=end)

    cmds.text(label="Renderer")
    cmds.optionMenu("rh_renderer")
    cmds.menuItem(label="arnold")
    cmds.menuItem(label="sw")
    cmds.menuItem(label="mayaHardware2")

    current_renderer = get_current_renderer()

    if current_renderer in ["arnold", "sw", "mayaHardware2"]:
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

    cmds.setParent("..")
    cmds.setParent("..")

    # ---------------- Actions ----------------

    cmds.frameLayout(
        label="Actions",
        collapsable=True,
        collapse=False,
        marginWidth=8,
        marginHeight=8
    )

    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(280, 280))

    cmds.button(
        label="Refresh From Scene",
        height=35,
        command=refresh_from_scene
    )

    cmds.button(
        label="Save Task JSON As...",
        height=35,
        command=save_task_json_as
    )

    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(280, 280))

    cmds.button(
        label="Auto Save Task JSON",
        height=35,
        command=save_task_json_auto
    )

    cmds.button(
        label="Run Local Worker",
        height=35,
        command=run_local_worker
    )

    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(280, 280))

    cmds.button(
        label="Open Output Folder",
        height=30,
        command=open_output_folder
    )

    cmds.button(
        label="Open Worker Tasks Folder",
        height=30,
        command=open_tasks_folder
    )

    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(280, 280))

    cmds.button(
        label="Generate Diagnostics Log",
        height=32,
        command=generate_diagnostics_log
    )

    cmds.button(
        label="Open Diagnostics Folder",
        height=32,
        command=open_diagnostics_folder
    )

    cmds.setParent("..")

    cmds.separator(height=8, style="in")

    cmds.button(
        label="Uninstall RenderHive",
        height=34,
        backgroundColor=(0.45, 0.12, 0.12),
        command=uninstall_renderhive_from_maya
    )

    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=8, style="in")

    cmds.text(
        label="V2: Portable submitter + Auto JSON + Local Worker + Diagnostics + Uninstall.",
        align="center",
        height=25
    )

    cmds.showWindow(window)

    rebuild_camera_menu()