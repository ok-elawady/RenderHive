from __future__ import print_function

import importlib
import json
import os
import sys
import time

import maya.cmds as cmds


PLUGIN_VERSION = "1.6.0"

VALIDATION_RESULTS = []
VALIDATION_REPORT = {}


# -----------------------------------------------------------------------------
# Package paths
# -----------------------------------------------------------------------------


def get_submitter_dir():
    return os.path.dirname(
        os.path.abspath(__file__)
    )


def get_install_root():
    return get_submitter_dir()


def get_install_info_path():
    return os.path.join(
        get_install_root(),
        "renderhive_install_info.json"
    )


def get_original_package_root():
    info_path = get_install_info_path()

    if os.path.isfile(info_path):
        try:
            with open(
                info_path,
                "r",
                encoding="utf-8"
            ) as handle:
                data = json.load(handle)

            source_dir = data.get("source_dir")

            if (
                source_dir
                and os.path.isdir(source_dir)
            ):
                return os.path.abspath(
                    source_dir
                )
        except Exception:
            pass

    return get_install_root()


# -----------------------------------------------------------------------------
# Maya scene helpers
# -----------------------------------------------------------------------------


def get_scene_path():
    return cmds.file(
        query=True,
        sceneName=True
    ) or ""


def get_project_path():
    try:
        return cmds.workspace(
            query=True,
            rootDirectory=True
        ) or ""
    except Exception:
        return ""


def get_scene_name():
    scene_path = get_scene_path()

    if scene_path:
        return os.path.splitext(
            os.path.basename(scene_path)
        )[0]

    return "maya_job"


def get_default_output_path():
    project_path = get_project_path()

    if project_path:
        return os.path.join(
            project_path,
            "images"
        )

    scene_path = get_scene_path()

    if scene_path:
        return os.path.join(
            os.path.dirname(scene_path),
            "images"
        )

    return ""


def get_frame_range():
    try:
        return (
            int(
                cmds.getAttr(
                    "defaultRenderGlobals.startFrame"
                )
            ),
            int(
                cmds.getAttr(
                    "defaultRenderGlobals.endFrame"
                )
            ),
        )
    except Exception:
        return 1, 1


def get_resolution():
    try:
        return (
            int(
                cmds.getAttr(
                    "defaultResolution.width"
                )
            ),
            int(
                cmds.getAttr(
                    "defaultResolution.height"
                )
            ),
        )
    except Exception:
        return 1280, 720


def get_current_renderer():
    try:
        return cmds.getAttr(
            "defaultRenderGlobals.currentRenderer"
        ) or "arnold"
    except Exception:
        return "arnold"


def get_cameras():
    cameras = []

    for shape in cmds.ls(
        type="camera"
    ) or []:
        parents = cmds.listRelatives(
            shape,
            parent=True
        ) or []

        if parents:
            cameras.append(
                parents[0]
            )

    return cameras


def get_renderable_camera():
    cameras = get_cameras()

    if "renderCam" in cameras:
        return "renderCam"

    for shape in cmds.ls(
        type="camera"
    ) or []:
        try:
            if cmds.getAttr(
                shape + ".renderable"
            ):
                parents = cmds.listRelatives(
                    shape,
                    parent=True
                ) or []

                if parents:
                    return parents[0]
        except Exception:
            pass

    return cameras[0] if cameras else "NoCamera"


def save_scene_if_needed():
    scene_path = get_scene_path()

    if not scene_path:
        return (
            False,
            "Scene is not saved. Save the Maya scene first."
        )

    if cmds.file(
        query=True,
        modified=True
    ):
        result = cmds.confirmDialog(
            title="Save Scene",
            message=(
                "The scene has unsaved changes. "
                "Save before submission?"
            ),
            button=["Save", "Cancel"],
            defaultButton="Save",
            cancelButton="Cancel",
            dismissString="Cancel",
        )

        if result != "Save":
            return False, "Scene was not saved."

        cmds.file(
            save=True
        )

    return True, ""


# -----------------------------------------------------------------------------
# UI bridge fallbacks
# The Qt window replaces these functions when it opens.
# -----------------------------------------------------------------------------


def get_text(name, default=""):
    return default


def set_text(name, value):
    return None


def get_int(name, default=0):
    return int(default)


def set_int(name, value):
    return None


def get_option(name, default=""):
    return default


def set_status(message):
    print(
        "[RenderHive] {}".format(
            message
        )
    )


def refresh_from_scene(*args):
    return None


def rebuild_camera_menu():
    return None


def browse_output_path(*args):
    selected = cmds.fileDialog2(
        fileMode=3,
        caption="Select Output Folder"
    )

    if selected:
        set_text(
            "rh_output_path",
            selected[0]
        )


def open_folder(path):
    if not path:
        cmds.confirmDialog(
            title="RenderHive",
            message="Path is empty.",
            button=["OK"],
            icon="warning",
        )
        return

    if not os.path.isdir(path):
        os.makedirs(path)

    try:
        os.startfile(path)
    except Exception as error:
        cmds.confirmDialog(
            title="RenderHive",
            message=(
                "Could not open folder:\n{}\n\n{}"
            ).format(
                path,
                error
            ),
            button=["OK"],
            icon="warning",
        )


def open_output_folder(*args):
    open_folder(
        get_text(
            "rh_output_path",
            get_default_output_path()
        )
    )


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def load_validation_engine_class():
    submitter_dir = os.path.abspath(
        get_submitter_dir()
    )

    if submitter_dir in sys.path:
        sys.path.remove(
            submitter_dir
        )
    sys.path.insert(
        0,
        submitter_dir
    )

    existing_package = sys.modules.get(
        "validation"
    )

    if existing_package is not None:
        existing_file = getattr(
            existing_package,
            "__file__",
            "",
        ) or ""
        existing_file = (
            os.path.abspath(existing_file)
            if existing_file
            else ""
        )

        if (
            existing_file
            and not existing_file.startswith(
                submitter_dir
            )
        ):
            for module_name in list(
                sys.modules
            ):
                if (
                    module_name == "validation"
                    or module_name.startswith(
                        "validation."
                    )
                ):
                    del sys.modules[module_name]

    validation_dir = os.path.join(
        submitter_dir,
        "validation"
    )

    for filename in sorted(
        os.listdir(validation_dir)
    ):
        if not filename.endswith(
            "_checks.py"
        ):
            continue

        module_name = "validation.{}".format(
            filename[:-3]
        )
        module = importlib.import_module(
            module_name
        )
        importlib.reload(
            module
        )

    collector = importlib.import_module(
        "core.dependency_collector"
    )
    importlib.reload(
        collector
    )

    validator = importlib.import_module(
        "validation.validator"
    )
    importlib.reload(
        validator
    )

    return validator.ValidationEngine


def update_validation_ui(report):
    return None


def get_selected_validation_result():
    return None


def clear_validation_results(*args):
    global VALIDATION_RESULTS
    global VALIDATION_REPORT

    VALIDATION_RESULTS = []
    VALIDATION_REPORT = {}
    set_status(
        "Validation results cleared."
    )


def run_validation(
    show_dialog_on_error=True
):
    global VALIDATION_RESULTS
    global VALIDATION_REPORT

    try:
        set_status(
            "Validating scene..."
        )

        task = build_task()
        engine_class = load_validation_engine_class()
        engine = engine_class(
            task
        )

        VALIDATION_RESULTS = engine.run()
        VALIDATION_REPORT = engine.to_dict()

        update_validation_ui(
            VALIDATION_REPORT
        )

        return VALIDATION_REPORT

    except Exception as error:
        VALIDATION_RESULTS = []
        VALIDATION_REPORT = {}
        set_status(
            "Validation could not run."
        )

        if show_dialog_on_error:
            cmds.confirmDialog(
                title="RenderHive Validation Error",
                message=str(error),
                button=["OK"],
                icon="critical",
            )

        return None


def validate_scene_from_ui(*args):
    return run_validation(
        show_dialog_on_error=True
    )


def select_validation_node(*args):
    result = get_selected_validation_result()

    if not result:
        set_status(
            "Select a validation result first."
        )
        return

    node = result.get("node")

    if (
        not node
        or node == "-"
        or not cmds.objExists(node)
    ):
        set_status(
            "The linked Maya node is unavailable."
        )
        return

    cmds.select(
        node,
        replace=True
    )
    set_status(
        "Selected node: {}".format(
            node
        )
    )


def get_validation_reports_folder():
    folder = os.path.join(
        get_original_package_root(),
        "logs",
        "validation"
    )

    if not os.path.isdir(folder):
        os.makedirs(folder)

    return folder


def export_validation_report(*args):
    global VALIDATION_REPORT

    if not VALIDATION_REPORT:
        if not run_validation(
            show_dialog_on_error=True
        ):
            return None

    selected = cmds.fileDialog2(
        fileMode=0,
        caption="Export RenderHive Validation Report",
        fileFilter="JSON Files (*.json)",
        startingDirectory=get_validation_reports_folder(),
    )

    if not selected:
        return None

    path = selected[0]

    if not path.lower().endswith(
        ".json"
    ):
        path += ".json"

    task = build_task()

    payload = {
        "generated_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "maya_version": cmds.about(
            version=True
        ),
        "scene_path": task.get(
            "scene_path",
            ""
        ),
        "project_path": task.get(
            "project_path",
            ""
        ),
        "task": task,
        "summary": VALIDATION_REPORT.get(
            "summary",
            {}
        ),
        "results": VALIDATION_REPORT.get(
            "results",
            []
        ),
    }

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=4
        )

    set_status(
        "Validation report exported."
    )
    return path


# -----------------------------------------------------------------------------
# Task data
# -----------------------------------------------------------------------------


def build_task():
    scene_name = get_scene_name()
    scene_path = get_scene_path()
    project_path = get_project_path()
    output_path = get_default_output_path()
    frame_start, frame_end = get_frame_range()
    width, height = get_resolution()

    return {
        "job_name": get_text(
            "rh_job_name",
            scene_name
        ),
        "project_name": get_text(
            "rh_project_name",
            (
                os.path.basename(
                    os.path.normpath(
                        project_path
                    )
                )
                if project_path
                else "RenderHive Project"
            )
        ),
        "software": "maya",
        "scene_path": get_text(
            "rh_scene_path",
            scene_path
        ),
        "project_path": get_text(
            "rh_project_path",
            project_path
        ),
        "output_path": get_text(
            "rh_output_path",
            output_path
        ),
        "frame_start": get_int(
            "rh_frame_start",
            frame_start
        ),
        "frame_end": get_int(
            "rh_frame_end",
            frame_end
        ),
        "renderer": get_option(
            "rh_renderer",
            get_current_renderer()
        ),
        "camera": get_option(
            "rh_camera",
            get_renderable_camera()
        ),
        "image_name": get_text(
            "rh_image_name",
            scene_name
        ),
        "image_format": get_option(
            "rh_image_format",
            "png"
        ),
        "frame_padding": get_int(
            "rh_frame_padding",
            4
        ),
        "width": get_int(
            "rh_width",
            width
        ),
        "height": get_int(
            "rh_height",
            height
        ),
        "priority": get_int(
            "rh_priority",
            50
        ),
    }


def validate_task(task):
    errors = []

    if not task.get("job_name"):
        errors.append(
            "Job name is empty."
        )

    scene_path = task.get(
        "scene_path"
    )

    if not scene_path:
        errors.append(
            "Scene path is empty. Save the Maya scene first."
        )
    elif not os.path.isfile(
        scene_path
    ):
        errors.append(
            "Scene file does not exist:\n{}".format(
                scene_path
            )
        )

    project_path = task.get(
        "project_path"
    )

    if not project_path:
        errors.append(
            "Project path is empty."
        )
    elif not os.path.isdir(
        project_path
    ):
        errors.append(
            "Project path does not exist:\n{}".format(
                project_path
            )
        )

    if not task.get(
        "output_path"
    ):
        errors.append(
            "Output path is empty."
        )

    if (
        task.get("frame_start", 1)
        > task.get("frame_end", 1)
    ):
        errors.append(
            "Frame start cannot be greater than frame end."
        )

    if task.get(
        "camera"
    ) in (
        "",
        None,
        "NoCamera",
    ):
        errors.append(
            "No valid camera selected."
        )

    if not task.get(
        "image_name"
    ):
        errors.append(
            "Image name is empty."
        )

    if int(
        task.get(
            "frame_padding",
            0
        )
    ) < 1:
        errors.append(
            "Frame padding must be at least 1."
        )

    if (
        int(task.get("width", 0)) <= 0
        or int(task.get("height", 0)) <= 0
    ):
        errors.append(
            "Resolution must be greater than zero."
        )

    return errors


# -----------------------------------------------------------------------------
# Installation
# -----------------------------------------------------------------------------


def uninstall_renderhive_from_maya(*args):
    try:
        submitter_dir = get_submitter_dir()

        if submitter_dir not in sys.path:
            sys.path.insert(
                0,
                submitter_dir
            )

        import renderhive_installer
        importlib.reload(
            renderhive_installer
        )
        renderhive_installer.uninstall_renderhive(
            confirm=True
        )

    except Exception as error:
        cmds.confirmDialog(
            title="RenderHive Uninstall Failed",
            message=str(error),
            button=["OK"],
            icon="critical",
        )


def _ensure_local_package(
    package_name
):
    package_root = get_submitter_dir()

    if package_root in sys.path:
        sys.path.remove(
            package_root
        )
    sys.path.insert(
        0,
        package_root
    )

    existing = sys.modules.get(
        package_name
    )

    if existing is not None:
        existing_file = getattr(
            existing,
            "__file__",
            "",
        ) or ""
        existing_file = (
            os.path.abspath(existing_file)
            if existing_file
            else ""
        )

        if (
            existing_file
            and not existing_file.startswith(
                package_root
            )
        ):
            for module_name in list(
                sys.modules
            ):
                if (
                    module_name == package_name
                    or module_name.startswith(
                        package_name + "."
                    )
                ):
                    del sys.modules[module_name]

    importlib.invalidate_caches()


def show_submitter():
    _ensure_local_package(
        "ui"
    )

    import ui.qt_theme as qt_theme
    import ui.qt_submitter_window as qt_submitter_window

    importlib.reload(
        qt_theme
    )
    importlib.reload(
        qt_submitter_window
    )

    return qt_submitter_window.show_submitter(
        sys.modules[__name__]
    )
