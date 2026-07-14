from __future__ import print_function

import importlib
import os
import sys
import time

import maya.cmds as cmds


UI_VERSION = "1.0"
UI_SETTING_PREFIX = "renderHive_"

VALIDATION_SEVERITY_FILTER = "rh_validation_severity_filter"
VALIDATION_CATEGORY_FILTER = "rh_validation_category_filter"

VALIDATION_ERROR_COUNT = "rh_validation_error_count"
VALIDATION_WARNING_COUNT = "rh_validation_warning_count"
VALIDATION_INFO_COUNT = "rh_validation_info_count"
VALIDATION_PASSED_COUNT = "rh_validation_passed_count"
VALIDATION_TOTAL_COUNT = "rh_validation_total_count"

MAIN_TABS_NAME = "rh_main_tabs"
VALIDATION_SEARCH_FIELD = "rh_validation_search"
VALIDATION_DETAIL_TITLE = "rh_validation_detail_title"
VALIDATION_DETAIL_BODY = "rh_validation_detail_body"
VALIDATION_HEALTH_BADGE = "rh_validation_health_badge"
SCENE_STATE_BADGE = "rh_scene_state_badge"
RESOLUTION_META_TEXT = "rh_resolution_meta"
ACTIVITY_LOG_FIELD = "rh_activity_log"
ORIGINAL_SET_STATUS = None
ACTIVITY_LOG_ENTRIES = []

API = None
DISPLAYED_VALIDATION_RESULTS = []

# RenderHive final compact theme: graphite + electric mint.
BG = (0.070, 0.078, 0.092)
PANEL = (0.105, 0.118, 0.137)
PANEL_ALT = (0.135, 0.151, 0.174)
PANEL_SOFT = (0.175, 0.190, 0.214)
ACCENT = (0.000, 0.720, 0.620)
ACCENT_DARK = (0.000, 0.430, 0.380)
BLUE = (0.100, 0.390, 0.650)
SUCCESS = (0.070, 0.390, 0.220)
WARNING = (0.520, 0.335, 0.060)
ERROR = (0.500, 0.100, 0.125)
MUTED = (0.210, 0.225, 0.250)
TEXT_SOFT = (0.690, 0.720, 0.760)

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 700




def append_activity_log(message):
    """Append a timestamped message to the compact Activity Log."""
    if not message:
        return

    clean_message = str(message).replace("\r", " ").replace("\n", " ").strip()

    if clean_message.lower().startswith("status:"):
        clean_message = clean_message.split(":", 1)[1].strip()

    timestamp = time.strftime("%H:%M:%S")
    line = "{}  {}".format(timestamp, clean_message)

    ACTIVITY_LOG_ENTRIES.append(line)

    # Keep the log compact during long Maya sessions.
    del ACTIVITY_LOG_ENTRIES[:-200]

    if cmds.scrollField(ACTIVITY_LOG_FIELD, exists=True):
        cmds.scrollField(
            ACTIVITY_LOG_FIELD,
            edit=True,
            text="\n".join(ACTIVITY_LOG_ENTRIES)
        )


def set_status_with_activity(message):
    """Preserve the original status behavior and mirror it to Activity Log."""
    if ORIGINAL_SET_STATUS is not None:
        ORIGINAL_SET_STATUS(message)

    append_activity_log(message)


def submit_job(*args):
    """
    Temporary submission bridge.

    For now this calls the existing local-worker submission flow.
    Replace this single function with the backend API call later.
    """
    if API is None:
        return

    append_activity_log("Submitting job...")

    try:
        API.run_local_worker()
    except Exception as error:
        append_activity_log("Submit failed: {}".format(error))
        raise


def initialize_activity_log():
    if not ACTIVITY_LOG_ENTRIES:
        append_activity_log("RenderHive is ready.")

def get_option_var(name, default=None):
    full_name = UI_SETTING_PREFIX + name

    try:
        if cmds.optionVar(exists=full_name):
            return cmds.optionVar(query=full_name)
    except Exception:
        pass

    return default


def set_option_var(name, value):
    full_name = UI_SETTING_PREFIX + name

    try:
        if isinstance(value, bool):
            cmds.optionVar(intValue=(full_name, int(value)))
        elif isinstance(value, int):
            cmds.optionVar(intValue=(full_name, value))
        elif isinstance(value, float):
            cmds.optionVar(floatValue=(full_name, value))
        else:
            cmds.optionVar(stringValue=(full_name, str(value)))
    except Exception:
        pass


def set_option_menu_value(name, value):
    if not cmds.optionMenu(name, exists=True):
        return

    items = cmds.optionMenu(
        name,
        query=True,
        itemListLong=True
    ) or []

    labels = []

    for item in items:
        try:
            labels.append(
                cmds.menuItem(
                    item,
                    query=True,
                    label=True
                )
            )
        except Exception:
            pass

    if value in labels:
        cmds.optionMenu(
            name,
            edit=True,
            value=value
        )


def save_ui_preferences(*args):
    if API is None:
        return

    values = {
        "project_name": API.get_text("rh_project_name", ""),
        "priority": API.get_int("rh_priority", 50),
        "image_format": API.get_option("rh_image_format", "png"),
        "frame_padding": API.get_int("rh_frame_padding", 4),
        "validation_severity": API.get_option(
            VALIDATION_SEVERITY_FILTER,
            "All"
        ),
        "validation_category": API.get_option(
            VALIDATION_CATEGORY_FILTER,
            "All"
        ),
        "validation_search": (
            cmds.textField(
                VALIDATION_SEARCH_FIELD,
                query=True,
                text=True
            )
            if cmds.textField(VALIDATION_SEARCH_FIELD, exists=True)
            else ""
        ),
        "active_tab": (
            cmds.tabLayout(
                MAIN_TABS_NAME,
                query=True,
                selectTabIndex=True
            )
            if cmds.tabLayout(MAIN_TABS_NAME, exists=True)
            else 1
        ),
    }

    for name, value in values.items():
        set_option_var(name, value)

def load_ui_preferences():
    if API is None:
        return

    project_name = get_option_var("project_name", "")

    if project_name:
        API.set_text(
            "rh_project_name",
            project_name
        )

    API.set_int(
        "rh_priority",
        get_option_var("priority", 50)
    )

    set_option_menu_value(
        "rh_image_format",
        get_option_var("image_format", "png")
    )

    API.set_int(
        "rh_frame_padding",
        get_option_var("frame_padding", 4)
    )

    set_option_menu_value(
        VALIDATION_SEVERITY_FILTER,
        get_option_var("validation_severity", "All")
    )

    if cmds.textField(VALIDATION_SEARCH_FIELD, exists=True):
        cmds.textField(
            VALIDATION_SEARCH_FIELD,
            edit=True,
            text=get_option_var("validation_search", "")
        )

    active_tab = get_option_var("active_tab", 1)

    try:
        active_tab = int(active_tab)
    except Exception:
        active_tab = 1

    if cmds.tabLayout(MAIN_TABS_NAME, exists=True):
        active_tab = max(1, min(active_tab, 4))
        cmds.tabLayout(
            MAIN_TABS_NAME,
            edit=True,
            selectTabIndex=active_tab
        )

def on_submitter_close(*args):
    save_ui_preferences()


def save_active_tab(*args):
    if cmds.tabLayout(MAIN_TABS_NAME, exists=True):
        set_option_var(
            "active_tab",
            cmds.tabLayout(
                MAIN_TABS_NAME,
                query=True,
                selectTabIndex=True
            )
        )


def calculate_aspect_ratio(width, height):
    try:
        width = int(width)
        height = int(height)
    except Exception:
        return ""

    if width <= 0 or height <= 0:
        return ""

    import math
    divisor = math.gcd(width, height)

    if divisor <= 0:
        return ""

    return "{}:{}".format(
        int(width / divisor),
        int(height / divisor)
    )


def update_resolution_meta(*args):
    if API is None:
        return

    if not cmds.text(RESOLUTION_META_TEXT, exists=True):
        return

    width = API.get_int("rh_width", 0)
    height = API.get_int("rh_height", 0)
    ratio = calculate_aspect_ratio(width, height)

    label = "{} x {}".format(width, height)

    if ratio:
        label += "   /   {}".format(ratio)

    cmds.text(
        RESOLUTION_META_TEXT,
        edit=True,
        label=label
    )


def get_selected_validation_detail_text(result):
    if not result:
        return ""

    severity = result.get("severity", "INFO")
    category = result.get("category", "General")
    code = result.get("code", "")
    node = result.get("node", "")
    message = result.get("message", "")

    lines = [
        "{} / {}".format(severity, category)
    ]

    if code:
        lines.append("Code: {}".format(code))

    if node:
        lines.append("Node: {}".format(node))

    lines.append("")
    lines.append(message)

    return "\n".join(lines)


def update_validation_detail(*args):
    result = get_selected_validation_result()

    if not cmds.text(VALIDATION_DETAIL_TITLE, exists=True):
        return

    if not result:
        cmds.text(
            VALIDATION_DETAIL_TITLE,
            edit=True,
            label="RESULT DETAILS"
        )

        if cmds.scrollField(VALIDATION_DETAIL_BODY, exists=True):
            cmds.scrollField(
                VALIDATION_DETAIL_BODY,
                edit=True,
                text="Select a validation result to inspect it."
            )
        return

    severity = result.get("severity", "INFO")
    category = result.get("category", "General")

    cmds.text(
        VALIDATION_DETAIL_TITLE,
        edit=True,
        label="{}  /  {}".format(severity, category)
    )

    if cmds.scrollField(VALIDATION_DETAIL_BODY, exists=True):
        cmds.scrollField(
            VALIDATION_DETAIL_BODY,
            edit=True,
            text=get_selected_validation_detail_text(result)
        )


def copy_selected_validation_details(*args):
    result = get_selected_validation_result()

    if not result:
        if API is not None:
            API.set_status("Select a validation result first.")
        return

    text = get_selected_validation_detail_text(result)

    try:
        from PySide2 import QtWidgets
        app = QtWidgets.QApplication.instance()

        if app is None:
            raise RuntimeError("Qt application is unavailable.")

        app.clipboard().setText(text)

        if API is not None:
            API.set_status("Validation details copied.")

    except Exception as error:
        if API is not None:
            API.set_status(
                "Could not copy validation details: {}".format(error)
            )


def set_validation_health(error_count=0, warning_count=0, checked=False):
    if not cmds.text(VALIDATION_HEALTH_BADGE, exists=True):
        return

    if not checked:
        label = "NOT CHECKED"
        color = MUTED
    elif error_count:
        label = "BLOCKED  {}".format(error_count)
        color = ERROR
    elif warning_count:
        label = "REVIEW  {}".format(warning_count)
        color = WARNING
    else:
        label = "READY"
        color = SUCCESS

    cmds.text(
        VALIDATION_HEALTH_BADGE,
        edit=True,
        label=label,
        backgroundColor=color
    )


def reset_ui_preferences(*args):
    option_names = [
        "project_name",
        "priority",
        "image_format",
        "frame_padding",
        "validation_severity",
        "validation_category",
        "validation_search",
        "active_tab",
    ]

    for name in option_names:
        full_name = UI_SETTING_PREFIX + name

        try:
            if cmds.optionVar(exists=full_name):
                cmds.optionVar(remove=full_name)
        except Exception:
            pass

    if API is not None:
        API.set_status("Saved UI preferences were reset.")

def create_section_title(parent, label, description=""):
    block = cmds.columnLayout(
        parent=parent,
        adjustableColumn=True,
        rowSpacing=1
    )

    title_row = cmds.rowLayout(
        parent=block,
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(5, 500, 78)
    )

    cmds.text(
        parent=title_row,
        label="",
        width=5,
        height=28,
        backgroundColor=ACCENT
    )

    cmds.text(
        parent=title_row,
        label="  " + label.upper(),
        align="left",
        font="boldLabelFont",
        height=28,
        backgroundColor=PANEL_ALT
    )

    cmds.text(
        parent=title_row,
        label="RH / {}".format(UI_VERSION),
        align="center",
        height=28,
        backgroundColor=PANEL
    )

    if description:
        cmds.text(
            parent=block,
            label="   " + description,
            align="left",
            height=22,
            backgroundColor=PANEL
        )

    cmds.separator(
        parent=block,
        height=5,
        style="none"
    )

    return block

def create_counter_card(parent, control_name, label, background_color):
    cmds.text(
        control_name,
        parent=parent,
        label="{}  0".format(label),
        align="center",
        height=34,
        backgroundColor=background_color
    )

def apply_render_preset(*args):
    if API is None:
        return

    preset = API.get_option(
        "rh_render_preset",
        "Custom"
    )

    presets = {
        "Preview": {
            "width": 640,
            "height": 360,
            "format": "png",
            "padding": 4,
        },
        "HD": {
            "width": 1280,
            "height": 720,
            "format": "png",
            "padding": 4,
        },
        "Full HD": {
            "width": 1920,
            "height": 1080,
            "format": "png",
            "padding": 4,
        },
        "Production EXR": {
            "width": 1920,
            "height": 1080,
            "format": "exr",
            "padding": 4,
        },
    }

    settings = presets.get(preset)

    if not settings:
        API.set_status("Select a render preset first.")
        return

    API.set_int("rh_width", settings["width"])
    API.set_int("rh_height", settings["height"])
    API.set_int("rh_frame_padding", settings["padding"])

    set_option_menu_value(
        "rh_image_format",
        settings["format"]
    )

    update_resolution_meta()
    save_ui_preferences()

    API.set_status(
        "Applied '{}' preset: {} x {}, {}.".format(
            preset,
            settings["width"],
            settings["height"],
            settings["format"].upper()
        )
    )

def load_validation_engine_class():
    if API is None:
        raise RuntimeError(
            "RenderHive UI API is not initialized."
        )

    submitter_dir = os.path.abspath(
        API.get_submitter_dir()
    )

    if submitter_dir in sys.path:
        sys.path.remove(submitter_dir)

    sys.path.insert(0, submitter_dir)

    existing_package = sys.modules.get("validation")

    if existing_package is not None:
        existing_file = getattr(
            existing_package,
            "__file__",
            ""
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
            for module_name in list(sys.modules):
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

    if not os.path.isdir(validation_dir):
        raise RuntimeError(
            "RenderHive validation folder was not found:\n{}".format(
                validation_dir
            )
        )

    check_module_names = []

    for filename in sorted(
        os.listdir(validation_dir)
    ):
        if filename.endswith("_checks.py"):
            check_module_names.append(
                "validation.{}".format(
                    filename[:-3]
                )
            )

    dependency_collector_path = os.path.join(
        submitter_dir,
        "core",
        "dependency_collector.py"
    )

    if os.path.exists(dependency_collector_path):
        try:
            dependency_collector = importlib.import_module(
                "core.dependency_collector"
            )
            importlib.reload(
                dependency_collector
            )
        except Exception as error:
            raise RuntimeError(
                "Could not reload dependency collector: {}".format(
                    error
                )
            )

    for module_name in check_module_names:
        try:
            module = importlib.import_module(
                module_name
            )
            importlib.reload(module)
        except Exception as error:
            raise RuntimeError(
                "Could not load validation module '{}': {}".format(
                    module_name,
                    error
                )
            )

    validator = importlib.import_module(
        "validation.validator"
    )
    importlib.reload(validator)

    return validator.ValidationEngine


def rebuild_validation_category_filter(results):
    if API is None:
        return

    menu = VALIDATION_CATEGORY_FILTER

    if not cmds.optionMenu(menu, exists=True):
        return

    previous = API.get_option(menu, "All")

    items = cmds.optionMenu(
        menu,
        query=True,
        itemListLong=True
    ) or []

    for item in items:
        cmds.deleteUI(item)

    categories = sorted(set(
        result.get("category", "General")
        for result in results
    ))

    cmds.menuItem(
        label="All",
        parent=menu
    )

    for category in categories:
        cmds.menuItem(
            label=category,
            parent=menu
        )

    if previous in (["All"] + categories):
        cmds.optionMenu(
            menu,
            edit=True,
            value=previous
        )


def validation_result_matches_filters(result):
    if API is None:
        return True

    severity_filter = API.get_option(
        VALIDATION_SEVERITY_FILTER,
        "All"
    )

    category_filter = API.get_option(
        VALIDATION_CATEGORY_FILTER,
        "All"
    )

    severity = result.get(
        "severity",
        "INFO"
    )

    category = result.get(
        "category",
        "General"
    )

    if (
        severity_filter != "All"
        and severity != severity_filter
    ):
        return False

    if (
        category_filter != "All"
        and category != category_filter
    ):
        return False

    return True


def refresh_filtered_validation_results(*args):
    global DISPLAYED_VALIDATION_RESULTS

    if API is None:
        return

    search_text = ""

    if cmds.textField(VALIDATION_SEARCH_FIELD, exists=True):
        search_text = cmds.textField(
            VALIDATION_SEARCH_FIELD,
            query=True,
            text=True
        ).strip().lower()

    filtered = []

    for result in API.VALIDATION_RESULTS:
        if not validation_result_matches_filters(result):
            continue

        if search_text:
            haystack = " ".join([
                str(result.get("severity", "")),
                str(result.get("category", "")),
                str(result.get("code", "")),
                str(result.get("node", "")),
                str(result.get("message", "")),
            ]).lower()

            if search_text not in haystack:
                continue

        filtered.append(result)

    DISPLAYED_VALIDATION_RESULTS = filtered

    if not cmds.textScrollList(
        API.VALIDATION_LIST_NAME,
        exists=True
    ):
        return

    cmds.textScrollList(
        API.VALIDATION_LIST_NAME,
        edit=True,
        removeAll=True
    )

    for result in DISPLAYED_VALIDATION_RESULTS:
        cmds.textScrollList(
            API.VALIDATION_LIST_NAME,
            edit=True,
            append=API.format_validation_result(result)
        )

    if API.VALIDATION_RESULTS and not DISPLAYED_VALIDATION_RESULTS:
        cmds.textScrollList(
            API.VALIDATION_LIST_NAME,
            edit=True,
            append="No results match the current filters."
        )

    update_validation_detail()

def update_validation_ui(report):
    if API is None:
        return

    results = report.get("results", [])
    summary = report.get("summary", {})

    rebuild_validation_category_filter(results)
    refresh_filtered_validation_results()

    summary_label = (
        "Errors {ERROR}   /   Warnings {WARNING}   /   "
        "Info {INFO}   /   Passed {PASSED}   /   Total {total}"
    ).format(
        ERROR=summary.get("ERROR", 0),
        WARNING=summary.get("WARNING", 0),
        INFO=summary.get("INFO", 0),
        PASSED=summary.get("PASSED", 0),
        total=summary.get("total", 0)
    )

    if cmds.text(API.VALIDATION_SUMMARY_NAME, exists=True):
        cmds.text(
            API.VALIDATION_SUMMARY_NAME,
            edit=True,
            label=summary_label
        )

    counter_values = {
        VALIDATION_ERROR_COUNT: "ERR  {}".format(summary.get("ERROR", 0)),
        VALIDATION_WARNING_COUNT: "WARN  {}".format(summary.get("WARNING", 0)),
        VALIDATION_INFO_COUNT: "INFO  {}".format(summary.get("INFO", 0)),
        VALIDATION_PASSED_COUNT: "PASS  {}".format(summary.get("PASSED", 0)),
        VALIDATION_TOTAL_COUNT: "ALL  {}".format(summary.get("total", 0)),
    }

    for control_name, label in counter_values.items():
        if cmds.text(control_name, exists=True):
            cmds.text(
                control_name,
                edit=True,
                label=label
            )

    set_validation_health(
        error_count=summary.get("ERROR", 0),
        warning_count=summary.get("WARNING", 0),
        checked=True
    )

def get_selected_validation_result():
    if API is None:
        return None

    if not cmds.textScrollList(
        API.VALIDATION_LIST_NAME,
        exists=True
    ):
        return None

    selected_indexes = cmds.textScrollList(
        API.VALIDATION_LIST_NAME,
        query=True,
        selectIndexedItem=True
    ) or []

    if not selected_indexes:
        return None

    index = int(selected_indexes[0]) - 1

    if (
        index < 0
        or index >= len(
            DISPLAYED_VALIDATION_RESULTS
        )
    ):
        return None

    return DISPLAYED_VALIDATION_RESULTS[index]


def clear_validation_results(*args):
    global DISPLAYED_VALIDATION_RESULTS

    if API is None:
        return

    API.VALIDATION_RESULTS = []
    API.VALIDATION_REPORT = {}
    DISPLAYED_VALIDATION_RESULTS = []

    if cmds.textScrollList(API.VALIDATION_LIST_NAME, exists=True):
        cmds.textScrollList(
            API.VALIDATION_LIST_NAME,
            edit=True,
            removeAll=True
        )

    if cmds.text(API.VALIDATION_SUMMARY_NAME, exists=True):
        cmds.text(
            API.VALIDATION_SUMMARY_NAME,
            edit=True,
            label="No validation has been run."
        )

    counter_values = {
        VALIDATION_ERROR_COUNT: "ERR  0",
        VALIDATION_WARNING_COUNT: "WARN  0",
        VALIDATION_INFO_COUNT: "INFO  0",
        VALIDATION_PASSED_COUNT: "PASS  0",
        VALIDATION_TOTAL_COUNT: "ALL  0",
    }

    for control_name, label in counter_values.items():
        if cmds.text(control_name, exists=True):
            cmds.text(control_name, edit=True, label=label)

    rebuild_validation_category_filter([])
    set_validation_health(checked=False)
    update_validation_detail()
    API.set_status("Validation results cleared.")

def open_validation_reports_folder(*args):
    if API is not None:
        API.open_folder(
            API.get_validation_reports_folder()
        )



def install_runtime_overrides(api):
    global ORIGINAL_SET_STATUS

    api.load_validation_engine_class = load_validation_engine_class
    api.update_validation_ui = update_validation_ui
    api.get_selected_validation_result = get_selected_validation_result
    api.clear_validation_results = clear_validation_results

    if ORIGINAL_SET_STATUS is None:
        ORIGINAL_SET_STATUS = api.set_status

    api.set_status = set_status_with_activity

def build_job_tab(api, tabs, scene_name, project_path):
    tab = cmds.scrollLayout(
        parent=tabs,
        childResizable=True
    )

    column = cmds.columnLayout(
        parent=tab,
        adjustableColumn=True,
        rowSpacing=8
    )

    create_section_title(
        column,
        "Job",
        "The essentials first. Technical paths stay tucked away."
    )

    project_name = (
        os.path.basename(os.path.normpath(project_path))
        if project_path
        else "RenderHive_Demo"
    )

    identity = cmds.frameLayout(
        parent=column,
        label="JOB IDENTITY",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    grid = cmds.rowColumnLayout(
        parent=identity,
        numberOfColumns=2,
        columnWidth=[(1, 118), (2, 440)],
        columnSpacing=[(1, 8), (2, 8)],
        rowSpacing=[(1, 7), (2, 7)]
    )

    cmds.text(parent=grid, label="Project", align="left")
    cmds.textField(
        "rh_project_name",
        parent=grid,
        text=project_name,
        annotation="Project label stored in the RenderHive task."
    )

    cmds.text(parent=grid, label="Job", align="left")
    cmds.textField(
        "rh_job_name",
        parent=grid,
        text=scene_name,
        annotation="Unique job name shown in the queue."
    )

    cmds.text(parent=grid, label="Priority", align="left")
    cmds.intField(
        "rh_priority",
        parent=grid,
        value=50,
        minValue=0,
        maxValue=100,
        annotation="Higher values can be prioritized by the backend later."
    )

    output_frame = cmds.frameLayout(
        parent=column,
        label="OUTPUT LOCATION",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    output_column = cmds.columnLayout(
        parent=output_frame,
        adjustableColumn=True,
        rowSpacing=6
    )

    output_row = cmds.rowLayout(
        parent=output_column,
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(460, 98)
    )

    cmds.textField(
        "rh_output_path",
        parent=output_row,
        text=api.get_default_output_path(),
        annotation="Folder that receives rendered frames."
    )

    cmds.button(
        parent=output_row,
        label="BROWSE",
        width=98,
        height=28,
        backgroundColor=PANEL_ALT,
        command=api.browse_output_path
    )

    quick_row = cmds.rowLayout(
        parent=output_column,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(279, 279)
    )

    cmds.button(
        parent=quick_row,
        label="OPEN OUTPUT",
        height=30,
        backgroundColor=PANEL_ALT,
        annotation="Open the current render output folder.",
        command=api.open_output_folder
    )

    cmds.button(
        parent=quick_row,
        label="SYNC FROM SCENE",
        height=30,
        backgroundColor=ACCENT_DARK,
        annotation="Refresh camera, frame range, resolution and paths.",
        command=api.refresh_from_scene
    )

    context = cmds.frameLayout(
        parent=column,
        label="SCENE CONTEXT",
        collapsable=True,
        collapse=True,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    context_column = cmds.columnLayout(
        parent=context,
        adjustableColumn=True,
        rowSpacing=5
    )

    cmds.text(parent=context_column, label="Scene File", align="left")
    cmds.textField(
        "rh_scene_path",
        parent=context_column,
        text=api.get_scene_path()
    )

    cmds.text(parent=context_column, label="Project Root", align="left")
    cmds.textField(
        "rh_project_path",
        parent=context_column,
        text=project_path
    )

    return tab

def build_render_tab(api, tabs, scene_name, start, end, width, height):
    tab = cmds.scrollLayout(
        parent=tabs,
        childResizable=True
    )

    column = cmds.columnLayout(
        parent=tab,
        adjustableColumn=True,
        rowSpacing=8
    )

    create_section_title(
        column,
        "Render",
        "Compact farm settings with a live resolution readout."
    )

    preset_frame = cmds.frameLayout(
        parent=column,
        label="QUICK PRESET",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    preset_row = cmds.rowLayout(
        parent=preset_frame,
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(110, 338, 110)
    )

    cmds.text(parent=preset_row, label="Preset", align="left")
    preset_menu = cmds.optionMenu("rh_render_preset", parent=preset_row)

    for label in ["Custom", "Preview", "HD", "Full HD", "Production EXR"]:
        cmds.menuItem(parent=preset_menu, label=label)

    cmds.button(
        parent=preset_row,
        label="APPLY",
        width=110,
        height=28,
        backgroundColor=ACCENT_DARK,
        command=apply_render_preset
    )

    setup_frame = cmds.frameLayout(
        parent=column,
        label="FRAME SETUP",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    grid = cmds.rowColumnLayout(
        parent=setup_frame,
        numberOfColumns=4,
        columnWidth=[(1, 92), (2, 180), (3, 92), (4, 194)],
        columnSpacing=[(1, 6), (2, 8), (3, 6), (4, 6)],
        rowSpacing=[(1, 7), (2, 7), (3, 7), (4, 7)]
    )

    cmds.text(parent=grid, label="Start", align="left")
    cmds.intField("rh_frame_start", parent=grid, value=start)

    cmds.text(parent=grid, label="End", align="left")
    cmds.intField("rh_frame_end", parent=grid, value=end)

    cmds.text(parent=grid, label="Renderer", align="left")
    renderer_menu = cmds.optionMenu("rh_renderer", parent=grid)

    for label in ["arnold", "sw", "mayaHardware2"]:
        cmds.menuItem(parent=renderer_menu, label=label)

    current_renderer = api.get_current_renderer()

    if current_renderer in ["arnold", "sw", "mayaHardware2"]:
        cmds.optionMenu("rh_renderer", edit=True, value=current_renderer)

    cmds.text(parent=grid, label="Camera", align="left")
    camera_menu = cmds.optionMenu("rh_camera", parent=grid)
    cmds.menuItem(parent=camera_menu, label="Loading")

    output_frame = cmds.frameLayout(
        parent=column,
        label="IMAGE OUTPUT",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    output_grid = cmds.rowColumnLayout(
        parent=output_frame,
        numberOfColumns=4,
        columnWidth=[(1, 92), (2, 180), (3, 92), (4, 194)],
        columnSpacing=[(1, 6), (2, 8), (3, 6), (4, 6)],
        rowSpacing=[(1, 7), (2, 7), (3, 7), (4, 7)]
    )

    cmds.text(parent=output_grid, label="Name", align="left")
    cmds.textField("rh_image_name", parent=output_grid, text=scene_name)

    cmds.text(parent=output_grid, label="Format", align="left")
    format_menu = cmds.optionMenu("rh_image_format", parent=output_grid)

    for label in ["png", "jpg", "exr", "tif"]:
        cmds.menuItem(parent=format_menu, label=label)

    cmds.text(parent=output_grid, label="Padding", align="left")
    cmds.intField(
        "rh_frame_padding",
        parent=output_grid,
        value=4,
        minValue=1,
        maxValue=12
    )

    cmds.text(parent=output_grid, label="Width", align="left")
    cmds.intField(
        "rh_width",
        parent=output_grid,
        value=width,
        minValue=1,
        changeCommand=update_resolution_meta
    )

    cmds.text(parent=output_grid, label="Height", align="left")
    cmds.intField(
        "rh_height",
        parent=output_grid,
        value=height,
        minValue=1,
        changeCommand=update_resolution_meta
    )

    cmds.text(parent=output_grid, label="Resolution", align="left")
    cmds.text(
        RESOLUTION_META_TEXT,
        parent=output_grid,
        label="{} x {}".format(width, height),
        align="left",
        height=22,
        backgroundColor=PANEL_ALT
    )

    return tab

def build_validation_tab(api, tabs):
    tab = cmds.columnLayout(
        parent=tabs,
        adjustableColumn=True,
        rowSpacing=6
    )

    create_section_title(
        tab,
        "Checks",
        "Filter, inspect and copy precise preflight results."
    )

    counters = cmds.rowLayout(
        parent=tab,
        numberOfColumns=5,
        adjustableColumn=5,
        columnWidth5=(112, 112, 112, 112, 112)
    )

    create_counter_card(counters, VALIDATION_ERROR_COUNT, "ERR", ERROR)
    create_counter_card(counters, VALIDATION_WARNING_COUNT, "WARN", WARNING)
    create_counter_card(counters, VALIDATION_INFO_COUNT, "INFO", BLUE)
    create_counter_card(counters, VALIDATION_PASSED_COUNT, "PASS", SUCCESS)
    create_counter_card(counters, VALIDATION_TOTAL_COUNT, "ALL", MUTED)

    filters = cmds.rowLayout(
        parent=tab,
        numberOfColumns=4,
        adjustableColumn=4,
        columnWidth4=(58, 170, 58, 274)
    )

    cmds.text(parent=filters, label="Level", align="left")
    severity_menu = cmds.optionMenu(
        VALIDATION_SEVERITY_FILTER,
        parent=filters,
        changeCommand=refresh_filtered_validation_results
    )

    for label in ["All", "ERROR", "WARNING", "INFO", "PASSED"]:
        cmds.menuItem(parent=severity_menu, label=label)

    cmds.text(parent=filters, label="Group", align="left")
    category_menu = cmds.optionMenu(
        VALIDATION_CATEGORY_FILTER,
        parent=filters,
        changeCommand=refresh_filtered_validation_results
    )
    cmds.menuItem(parent=category_menu, label="All")

    search_row = cmds.rowLayout(
        parent=tab,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(58, 502)
    )

    cmds.text(parent=search_row, label="Find", align="left")
    cmds.textField(
        VALIDATION_SEARCH_FIELD,
        parent=search_row,
        placeholderText="message, node, code or category",
        changeCommand=refresh_filtered_validation_results,
        annotation="Press Enter or leave the field to apply the search."
    )

    cmds.text(
        api.VALIDATION_SUMMARY_NAME,
        parent=tab,
        label="No validation has been run.",
        align="left",
        height=22,
        backgroundColor=PANEL
    )

    cmds.textScrollList(
        api.VALIDATION_LIST_NAME,
        parent=tab,
        numberOfRows=9,
        allowMultiSelection=False,
        selectCommand=update_validation_detail,
        doubleClickCommand=api.select_validation_node,
        height=176
    )

    detail_frame = cmds.frameLayout(
        parent=tab,
        label="RESULT INSPECTOR",
        collapsable=False,
        marginWidth=8,
        marginHeight=6,
        backgroundColor=PANEL
    )

    detail_column = cmds.columnLayout(
        parent=detail_frame,
        adjustableColumn=True,
        rowSpacing=4
    )

    cmds.text(
        VALIDATION_DETAIL_TITLE,
        parent=detail_column,
        label="RESULT DETAILS",
        align="left",
        font="boldLabelFont",
        height=20
    )

    cmds.scrollField(
        VALIDATION_DETAIL_BODY,
        parent=detail_column,
        text="Select a validation result to inspect it.",
        editable=False,
        wordWrap=True,
        height=70,
        backgroundColor=BG
    )

    buttons = cmds.rowLayout(
        parent=tab,
        numberOfColumns=5,
        adjustableColumn=5,
        columnWidth5=(112, 112, 112, 112, 112)
    )

    cmds.button(
        parent=buttons,
        label="RUN CHECKS",
        height=32,
        backgroundColor=BLUE,
        annotation="Run every installed validation module.",
        command=api.validate_scene_from_ui
    )
    cmds.button(
        parent=buttons,
        label="SELECT",
        height=32,
        command=api.select_validation_node
    )
    cmds.button(
        parent=buttons,
        label="COPY",
        height=32,
        command=copy_selected_validation_details
    )
    cmds.button(
        parent=buttons,
        label="EXPORT",
        height=32,
        command=api.export_validation_report
    )
    cmds.button(
        parent=buttons,
        label="CLEAR",
        height=32,
        command=clear_validation_results
    )

    return tab


def build_tools_tab(api, tabs):
    tab = cmds.scrollLayout(
        parent=tabs,
        childResizable=True
    )

    column = cmds.columnLayout(
        parent=tab,
        adjustableColumn=True,
        rowSpacing=8
    )

    create_section_title(
        column,
        "Tools",
        "Submission activity and maintenance."
    )

    activity_frame = cmds.frameLayout(
        parent=column,
        label="ACTIVITY LOG",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    activity_column = cmds.columnLayout(
        parent=activity_frame,
        adjustableColumn=True,
        rowSpacing=5
    )

    cmds.text(
        parent=activity_column,
        label="Recent RenderHive actions and status messages.",
        align="left",
        height=20,
        backgroundColor=PANEL
    )

    cmds.scrollField(
        ACTIVITY_LOG_FIELD,
        parent=activity_column,
        text="\n".join(ACTIVITY_LOG_ENTRIES),
        editable=False,
        wordWrap=False,
        height=330,
        backgroundColor=BG
    )

    maintenance = cmds.frameLayout(
        parent=column,
        label="MAINTENANCE",
        collapsable=True,
        collapse=True,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    maintenance_column = cmds.columnLayout(
        parent=maintenance,
        adjustableColumn=True,
        rowSpacing=6
    )

    cmds.text(
        parent=maintenance_column,
        label="This section is normally not needed.",
        align="left",
        height=21
    )

    cmds.button(
        parent=maintenance_column,
        label="Uninstall RenderHive",
        height=27,
        backgroundColor=MUTED,
        annotation="Remove RenderHive from the current Maya profile.",
        command=api.uninstall_renderhive_from_maya
    )

    return tab


def build_action_bar(api, root):
    action_bar = cmds.columnLayout(
        parent=root,
        adjustableColumn=True,
        rowSpacing=3,
        height=82,
        backgroundColor=BG
    )

    cmds.separator(
        parent=action_bar,
        height=5,
        style="in"
    )

    centered_row = cmds.rowLayout(
        parent=action_bar,
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(135, 340, 135)
    )

    cmds.text(
        parent=centered_row,
        label="",
        height=38
    )

    cmds.button(
        parent=centered_row,
        label="SUBMIT JOB",
        height=40,
        backgroundColor=ACCENT_DARK,
        annotation=(
            "Submit the current job. This button is the single integration "
            "point for the backend API."
        ),
        command=submit_job
    )

    cmds.text(
        parent=centered_row,
        label="",
        height=38
    )

    cmds.text(
        api.STATUS_TEXT_NAME,
        parent=action_bar,
        label="  READY",
        align="center",
        height=23,
        backgroundColor=PANEL_ALT
    )

    return action_bar

def show_submitter(api):
    global API
    global DISPLAYED_VALIDATION_RESULTS

    API = api
    DISPLAYED_VALIDATION_RESULTS = []

    install_runtime_overrides(api)

    if cmds.window(api.WINDOW_NAME, exists=True):
        cmds.deleteUI(api.WINDOW_NAME)

    scene_name = api.get_scene_name()
    start, end = api.get_frame_range()
    width, height = api.get_resolution()
    project_path = api.get_project_path()
    scene_path = api.get_scene_path()

    window = cmds.window(
        api.WINDOW_NAME,
        title="RenderHive  /  Submitter {}".format(UI_VERSION),
        widthHeight=(WINDOW_WIDTH, WINDOW_HEIGHT),
        sizeable=True,
        closeCommand=on_submitter_close,
        backgroundColor=BG
    )

    root = cmds.formLayout(parent=window, backgroundColor=BG)

    header = cmds.rowLayout(
        parent=root,
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(52, 430, 120),
        height=64,
        backgroundColor=BG
    )

    cmds.text(
        parent=header,
        label="RH",
        align="center",
        font="boldLabelFont",
        width=46,
        height=46,
        backgroundColor=ACCENT_DARK
    )

    header_info = cmds.columnLayout(
        parent=header,
        adjustableColumn=True,
        rowSpacing=0,
        backgroundColor=BG
    )

    cmds.text(
        parent=header_info,
        label="RenderHive",
        font="boldLabelFont",
        align="left",
        height=27
    )

    cmds.text(
        parent=header_info,
        label="{}   /   Maya {}".format(
            scene_name,
            cmds.about(version=True)
        ),
        align="left",
        height=20,
        backgroundColor=PANEL
    )

    badges = cmds.columnLayout(
        parent=header,
        adjustableColumn=True,
        rowSpacing=4,
        backgroundColor=BG
    )

    cmds.text(
        VALIDATION_HEALTH_BADGE,
        parent=badges,
        label="NOT CHECKED",
        align="center",
        height=22,
        backgroundColor=MUTED
    )

    scene_label = "SAVED" if scene_path else "UNSAVED"
    scene_color = SUCCESS if scene_path else WARNING

    cmds.text(
        SCENE_STATE_BADGE,
        parent=badges,
        label=scene_label,
        align="center",
        height=22,
        backgroundColor=scene_color
    )

    tabs = cmds.tabLayout(
        MAIN_TABS_NAME,
        parent=root,
        innerMarginWidth=8,
        innerMarginHeight=8,
        changeCommand=save_active_tab
    )

    job_tab = build_job_tab(api, tabs, scene_name, project_path)
    render_tab = build_render_tab(
        api,
        tabs,
        scene_name,
        start,
        end,
        width,
        height
    )
    validation_tab = build_validation_tab(api, tabs)
    tools_tab = build_tools_tab(api, tabs)

    cmds.tabLayout(
        tabs,
        edit=True,
        tabLabel=[
            (job_tab, "JOB"),
            (render_tab, "RENDER"),
            (validation_tab, "CHECKS"),
            (tools_tab, "TOOLS"),
        ]
    )

    action_bar = build_action_bar(api, root)

    cmds.formLayout(
        root,
        edit=True,
        attachForm=[
            (header, "top", 8),
            (header, "left", 12),
            (header, "right", 12),
            (tabs, "left", 8),
            (tabs, "right", 8),
            (action_bar, "left", 12),
            (action_bar, "right", 12),
            (action_bar, "bottom", 8),
        ],
        attachControl=[
            (tabs, "top", 3, header),
            (tabs, "bottom", 3, action_bar),
        ]
    )

    cmds.showWindow(window)

    try:
        cmds.window(
            window,
            edit=True,
            widthHeight=(WINDOW_WIDTH, WINDOW_HEIGHT)
        )
    except Exception:
        pass

    api.rebuild_camera_menu()
    load_ui_preferences()
    update_resolution_meta()
    refresh_filtered_validation_results()
    set_validation_health(checked=False)
    initialize_activity_log()
    api.set_status("Ready")

    return window
