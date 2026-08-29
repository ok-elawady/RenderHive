from __future__ import print_function

import importlib
import json
import os
import sys
import time

import maya.cmds as cmds

from api.version import PLUGIN_VERSION
from core.runtime_log import get_logger

VALIDATION_RESULTS = []
VALIDATION_REPORT = {}
LOGGER = get_logger("submitter")


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


def api_admin_mode_enabled():
    """Return the managed admin-mode state without making UI startup fragile."""
    try:
        from api.maya_bridge import api_admin_mode_enabled as _enabled
        return bool(_enabled())
    except Exception:
        return False


def get_api_config_source():
    """Return the active backend config source for status display."""
    try:
        from api.maya_bridge import get_api_config_source as _source
        return _source()
    except Exception:
        return "Managed"


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


def get_current_render_layer():
    """Return Maya's currently active render layer node/name."""
    try:
        value = cmds.editRenderLayerGlobals(
            query=True,
            currentRenderLayer=True,
        )
        if value:
            return str(value)
    except Exception:
        pass
    return "defaultRenderLayer"


def _render_layer_renderable(name, default=True):
    try:
        if cmds.objExists(name + ".renderable"):
            return bool(cmds.getAttr(name + ".renderable"))
    except Exception:
        pass
    return bool(default)


def get_render_layers():
    """Return Render Setup/legacy layers in a stable UI-friendly format.

    The returned ``name`` is the value passed to Maya ``Render.exe -rl``.
    Render Setup is queried first because its display names are the artist-facing
    layer identifiers. Legacy renderLayer nodes are then used as a compatibility
    fallback and to guarantee that the master/default layer is represented.
    """
    records = []
    seen = set()
    current = get_current_render_layer()

    def add_record(name, renderable=True, source="legacy", is_default=False):
        clean = str(name or "").strip()
        if not clean or clean in seen:
            return
        seen.add(clean)
        records.append({
            "name": clean,
            "display_name": "defaultRenderLayer (Beauty / Master)" if is_default else clean,
            "renderable": bool(renderable),
            "is_default": bool(is_default),
            "is_current": clean == current,
            "source": str(source or "legacy"),
        })

    # Maya Render Setup (2017+) is the authoritative source when available.
    render_setup_found = False
    try:
        from maya.app.renderSetup.model import renderSetup

        setup = renderSetup.instance()
        setup_layers = setup.getRenderLayers() or []
        setup_records = []
        for layer in setup_layers:
            try:
                setup_name = layer.name()
            except Exception:
                setup_name = str(layer or "")
            setup_name = str(setup_name or "").strip()
            if setup_name:
                setup_records.append((layer, setup_name))

        render_setup_found = bool(setup_records)
        has_custom_setup_layers = any(
            name != "defaultRenderLayer" for _layer, name in setup_records
        )

        for layer, name in setup_records:
            try:
                renderable = bool(layer.isRenderable())
            except Exception:
                renderable = _render_layer_renderable(name, True)

            # The master/beauty layer remains available for an explicit artist
            # choice, but custom Render Setup layers must not cause it to be
            # auto-selected alongside them.
            if name == "defaultRenderLayer" and has_custom_setup_layers:
                renderable = False

            add_record(
                name,
                renderable=renderable,
                source="renderSetup",
                is_default=(name == "defaultRenderLayer"),
            )
    except Exception:
        pass

    # Legacy nodes remain useful for older scenes and for the master layer.
    # When Render Setup is active, only import the default layer from the
    # legacy node list so internal/compatibility renderLayer nodes are not
    # accidentally exposed as submit targets.
    try:
        legacy_layers = cmds.ls(type="renderLayer") or []
    except Exception:
        legacy_layers = []

    for name in legacy_layers:
        clean = str(name or "").strip()
        if not clean:
            continue
        if render_setup_found and clean != "defaultRenderLayer":
            continue
        add_record(
            clean,
            renderable=(
                False
                if render_setup_found and clean == "defaultRenderLayer"
                else _render_layer_renderable(clean, True)
            ),
            source="legacy",
            is_default=(clean == "defaultRenderLayer"),
        )

    if "defaultRenderLayer" not in seen:
        add_record(
            "defaultRenderLayer",
            renderable=(
                False
                if render_setup_found
                else _render_layer_renderable("defaultRenderLayer", True)
            ),
            source="legacy",
            is_default=True,
        )

    # Keep the master layer first, then preserve Maya's layer order.
    records.sort(key=lambda item: (0 if item.get("is_default") else 1))
    return records


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


def browse_scene_path(*args):
    selected = cmds.fileDialog2(
        fileMode=1,
        caption="Select Scene File",
        fileFilter="Maya Scenes (*.mb *.ma)"
    )

    if selected:
        set_text(
            "rh_scene_path",
            selected[0]
        )


def browse_project_path(*args):
    selected = cmds.fileDialog2(
        fileMode=3,
        caption="Select Project Root"
    )

    if selected:
        set_text(
            "rh_project_path",
            selected[0]
        )


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
    """Build the canonical RenderHive Maya task model."""
    from submission.task_builder import build_task as build_submission_task

    return build_submission_task(
        sys.modules[__name__],
        window=None,
        widgets=None,
        validation_report=VALIDATION_REPORT,
    )


def validate_task(task):
    """Run the canonical production submission guard."""
    from submission.task_validation import validate_task as validate_submission_task

    return validate_submission_task(task)


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


def render_frame_locally(frame=None, camera=None, layer=None, width=None, height=None, output_path=None, show_render_view=True):
    """
    Renders a single frame locally inside Maya and displays it in the Render View.
    """
    try:
        import maya.cmds as cmds
        import maya.mel as mel

        current_time = cmds.currentTime(query=True) if cmds.objExists("time1") else 1
        target_frame = int(frame) if frame is not None else int(current_time)
        cmds.currentTime(target_frame)

        if layer and layer not in ("defaultRenderLayer", "masterLayer"):
            try:
                if cmds.objExists(layer):
                    cmds.editRenderLayerGlobals(currentRenderLayer=layer)
            except Exception:
                pass

        target_camera = camera or get_renderable_camera() or "persp"
        res = get_resolution()
        target_width = int(width) if width else res[0]
        target_height = int(height) if height else res[1]

        # 1. Open and raise Maya's native Render View window so the artist sees the output
        if show_render_view:
            try:
                mel.eval('RenderViewWindow;')
            except Exception:
                try:
                    if not cmds.window("renderViewWindow", exists=True):
                        mel.eval('renderIntoNewWindow render;')
                    else:
                        cmds.showWindow("renderViewWindow")
                except Exception:
                    pass

        # 2. Render frame into Maya's Render View
        rendered_via = "renderWindow"
        try:
            mel_cmd = 'renderWindowRenderCamera "render" "renderView" "{}";'.format(target_camera)
            mel.eval(mel_cmd)
            rendered_via = "renderWindowRenderCamera"
        except Exception:
            try:
                cmds.render(target_camera, x=target_width, y=target_height)
                rendered_via = "cmds.render"
            except Exception:
                renderer = get_current_renderer()
                if str(renderer).lower() == "arnold":
                    try:
                        import mtoa.core
                        mtoa.core.createOptions()
                        cmds.arnoldRender(cam=target_camera, width=target_width, height=target_height)
                        rendered_via = "cmds.arnoldRender"
                    except Exception as arnold_err:
                        raise RuntimeError("Arnold render failed: {}".format(arnold_err))
                else:
                    raise

        # Ensure Render View window is displayed
        try:
            if cmds.window("renderViewWindow", exists=True):
                cmds.showWindow("renderViewWindow")
        except Exception:
            pass

        return {
            "success": True,
            "frame": target_frame,
            "camera": target_camera,
            "layer": layer or "defaultRenderLayer",
            "resolution": "{}x{}".format(target_width, target_height),
            "rendered_via": rendered_via,
            "message": "Rendered frame {} (Camera: {}, Res: {}x{}) into Maya Render View.".format(
                target_frame, target_camera, target_width, target_height
            ),
        }
    except Exception as error:
        return {
            "success": False,
            "frame": frame,
            "error": str(error),
            "message": "Local render failed: {}".format(error),
        }


def stage_scene_to_repository(repository_path=None, job_id=None):
    """
    Stages the active scene file to the central server repository for worker access.
    """
    import shutil
    scene_path = get_scene_path()
    if not scene_path or not os.path.isfile(scene_path):
        raise RuntimeError("The Maya scene must be saved to disk before staging.")

    job_id = job_id or "job_{}".format(datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    if not repository_path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = os.path.join(local_app_data, "RenderHive", "repository") if local_app_data else os.path.expanduser("~/.renderhive/repository")
        repository_path = base

    target_dir = os.path.join(repository_path, "jobs", str(job_id))
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)

    target_file = os.path.join(target_dir, os.path.basename(scene_path))
    shutil.copy2(scene_path, target_file)

    return {
        "staged_scene_path": target_file,
        "staging_dir": target_dir,
        "job_id": job_id,
        "original_scene_path": scene_path,
    }


def show_submitter():
    try:
        _ensure_local_package("ui")
        import ui.qt_submitter_window as qt_submitter_window

        window = qt_submitter_window.show_submitter(sys.modules[__name__])
        LOGGER.info("RenderHive Maya v%s opened successfully", PLUGIN_VERSION)
        return window
    except Exception as error:
        LOGGER.exception("Could not open RenderHive Maya submitter")
        try:
            cmds.confirmDialog(
                title="RenderHive Error",
                message=(
                    "RenderHive could not open.\n\n{}\n\n"
                    "Check the runtime log for details."
                ).format(error),
                button=["OK"],
                icon="critical",
            )
        except Exception:
            pass
        raise
