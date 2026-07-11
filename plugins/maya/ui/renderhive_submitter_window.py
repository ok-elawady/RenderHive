from __future__ import print_function

import importlib
import os
import sys

import maya.cmds as cmds


UI_VERSION = "0.5"
UI_SETTING_PREFIX = "renderHive_"

VALIDATION_SEVERITY_FILTER = "rh_validation_severity_filter"
VALIDATION_CATEGORY_FILTER = "rh_validation_category_filter"

VALIDATION_ERROR_COUNT = "rh_validation_error_count"
VALIDATION_WARNING_COUNT = "rh_validation_warning_count"
VALIDATION_INFO_COUNT = "rh_validation_info_count"
VALIDATION_PASSED_COUNT = "rh_validation_passed_count"
VALIDATION_TOTAL_COUNT = "rh_validation_total_count"

API = None
DISPLAYED_VALIDATION_RESULTS = []

# RenderHive compact modern theme
BG = (0.090, 0.102, 0.118)
PANEL = (0.125, 0.141, 0.161)
PANEL_ALT = (0.155, 0.174, 0.196)
PANEL_SOFT = (0.185, 0.202, 0.222)
ACCENT = (0.000, 0.620, 0.570)
ACCENT_DARK = (0.000, 0.390, 0.360)
BLUE = (0.100, 0.340, 0.560)
SUCCESS = (0.080, 0.350, 0.205)
WARNING = (0.440, 0.300, 0.075)
ERROR = (0.430, 0.115, 0.125)
MUTED = (0.235, 0.250, 0.270)

WINDOW_WIDTH = 680
WINDOW_HEIGHT = 710



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


def on_submitter_close(*args):
    save_ui_preferences()


def create_section_title(parent, label, description=""):
    block = cmds.columnLayout(
        parent=parent,
        adjustableColumn=True,
        rowSpacing=1
    )

    title_row = cmds.rowLayout(
        parent=block,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(6, 590)
    )

    cmds.text(
        parent=title_row,
        label="",
        width=6,
        height=28,
        backgroundColor=ACCENT
    )

    cmds.text(
        parent=title_row,
        label="  " + label,
        align="left",
        font="boldLabelFont",
        height=28,
        backgroundColor=PANEL_ALT
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

    DISPLAYED_VALIDATION_RESULTS = [
        result
        for result in API.VALIDATION_RESULTS
        if validation_result_matches_filters(
            result
        )
    ]

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
            append=API.format_validation_result(
                result
            )
        )

    if (
        API.VALIDATION_RESULTS
        and not DISPLAYED_VALIDATION_RESULTS
    ):
        cmds.textScrollList(
            API.VALIDATION_LIST_NAME,
            edit=True,
            append=(
                "No validation results match "
                "the current filters."
            )
        )


def update_validation_ui(report):
    if API is None:
        return

    results = report.get("results", [])
    summary = report.get("summary", {})

    rebuild_validation_category_filter(results)
    refresh_filtered_validation_results()

    summary_label = (
        "Errors: {ERROR}    Warnings: {WARNING}    "
        "Info: {INFO}    Passed: {PASSED}    Total: {total}"
    ).format(
        ERROR=summary.get("ERROR", 0),
        WARNING=summary.get("WARNING", 0),
        INFO=summary.get("INFO", 0),
        PASSED=summary.get("PASSED", 0),
        total=summary.get("total", 0)
    )

    if cmds.text(
        API.VALIDATION_SUMMARY_NAME,
        exists=True
    ):
        cmds.text(
            API.VALIDATION_SUMMARY_NAME,
            edit=True,
            label=summary_label
        )

    counter_values = {
        VALIDATION_ERROR_COUNT: "ERROR\n{}".format(
            summary.get("ERROR", 0)
        ),
        VALIDATION_WARNING_COUNT: "WARNING\n{}".format(
            summary.get("WARNING", 0)
        ),
        VALIDATION_INFO_COUNT: "INFO\n{}".format(
            summary.get("INFO", 0)
        ),
        VALIDATION_PASSED_COUNT: "PASSED\n{}".format(
            summary.get("PASSED", 0)
        ),
        VALIDATION_TOTAL_COUNT: "TOTAL\n{}".format(
            summary.get("total", 0)
        ),
    }

    for control_name, label in counter_values.items():
        if cmds.text(control_name, exists=True):
            cmds.text(
                control_name,
                edit=True,
                label=label
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

    if cmds.textScrollList(
        API.VALIDATION_LIST_NAME,
        exists=True
    ):
        cmds.textScrollList(
            API.VALIDATION_LIST_NAME,
            edit=True,
            removeAll=True
        )

    if cmds.text(
        API.VALIDATION_SUMMARY_NAME,
        exists=True
    ):
        cmds.text(
            API.VALIDATION_SUMMARY_NAME,
            edit=True,
            label=(
                "Errors: 0    Warnings: 0    "
                "Info: 0    Passed: 0    Total: 0"
            )
        )

    counter_values = {
        VALIDATION_ERROR_COUNT: "ERROR\n0",
        VALIDATION_WARNING_COUNT: "WARNING\n0",
        VALIDATION_INFO_COUNT: "INFO\n0",
        VALIDATION_PASSED_COUNT: "PASSED\n0",
        VALIDATION_TOTAL_COUNT: "TOTAL\n0",
    }

    for control_name, label in counter_values.items():
        if cmds.text(control_name, exists=True):
            cmds.text(
                control_name,
                edit=True,
                label=label
            )

    rebuild_validation_category_filter([])
    API.set_status(
        "Validation results cleared."
    )


def open_validation_reports_folder(*args):
    if API is not None:
        API.open_folder(
            API.get_validation_reports_folder()
        )


def install_runtime_overrides(api):
    api.load_validation_engine_class = (
        load_validation_engine_class
    )
    api.update_validation_ui = (
        update_validation_ui
    )
    api.get_selected_validation_result = (
        get_selected_validation_result
    )
    api.clear_validation_results = (
        clear_validation_results
    )


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
        "Name the task and confirm the scene locations."
    )

    project_name = (
        os.path.basename(os.path.normpath(project_path))
        if project_path
        else "RenderHive_Demo"
    )

    identity = cmds.frameLayout(
        parent=column,
        label="Identity",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    grid = cmds.rowColumnLayout(
        parent=identity,
        numberOfColumns=2,
        columnWidth=[(1, 130), (2, 470)],
        columnSpacing=[(1, 8), (2, 8)],
        rowSpacing=[(1, 6), (2, 6)]
    )

    cmds.text(parent=grid, label="Project", align="left")
    cmds.textField("rh_project_name", parent=grid, text=project_name)

    cmds.text(parent=grid, label="Job", align="left")
    cmds.textField("rh_job_name", parent=grid, text=scene_name)

    cmds.text(parent=grid, label="Priority", align="left")
    cmds.intField(
        "rh_priority",
        parent=grid,
        value=50,
        minValue=0,
        maxValue=100
    )

    paths = cmds.frameLayout(
        parent=column,
        label="Paths",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    paths_column = cmds.columnLayout(
        parent=paths,
        adjustableColumn=True,
        rowSpacing=5
    )

    cmds.text(parent=paths_column, label="Scene", align="left")
    cmds.textField(
        "rh_scene_path",
        parent=paths_column,
        text=api.get_scene_path()
    )

    cmds.text(parent=paths_column, label="Project Root", align="left")
    cmds.textField(
        "rh_project_path",
        parent=paths_column,
        text=project_path
    )

    cmds.text(parent=paths_column, label="Output", align="left")

    output_row = cmds.rowLayout(
        parent=paths_column,
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(500, 100)
    )

    cmds.textField(
        "rh_output_path",
        parent=output_row,
        text=api.get_default_output_path()
    )

    cmds.button(
        parent=output_row,
        label="Browse",
        width=100,
        command=api.browse_output_path
    )

    quick_row = cmds.rowLayout(
        parent=paths_column,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(300, 300)
    )

    cmds.button(
        parent=quick_row,
        label="Open Output",
        height=30,
        backgroundColor=PANEL_ALT,
        command=api.open_output_folder
    )

    cmds.button(
        parent=quick_row,
        label="Sync From Scene",
        height=30,
        backgroundColor=PANEL_ALT,
        command=api.refresh_from_scene
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
        "A compact task-level view of the render settings."
    )

    preset_frame = cmds.frameLayout(
        parent=column,
        label="Quick Preset",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    preset_row = cmds.rowLayout(
        parent=preset_frame,
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(120, 360, 120)
    )

    cmds.text(parent=preset_row, label="Preset", align="left")
    preset_menu = cmds.optionMenu("rh_render_preset", parent=preset_row)

    for label in ["Custom", "Preview", "HD", "Full HD", "Production EXR"]:
        cmds.menuItem(parent=preset_menu, label=label)

    cmds.button(
        parent=preset_row,
        label="Apply",
        width=120,
        backgroundColor=ACCENT_DARK,
        command=apply_render_preset
    )

    setup_frame = cmds.frameLayout(
        parent=column,
        label="Setup",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    grid = cmds.rowColumnLayout(
        parent=setup_frame,
        numberOfColumns=4,
        columnWidth=[(1, 105), (2, 190), (3, 105), (4, 190)],
        columnSpacing=[(1, 6), (2, 10), (3, 6), (4, 6)],
        rowSpacing=[(1, 6), (2, 6), (3, 6), (4, 6)]
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
        label="Output",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    output_grid = cmds.rowColumnLayout(
        parent=output_frame,
        numberOfColumns=4,
        columnWidth=[(1, 105), (2, 190), (3, 105), (4, 190)],
        columnSpacing=[(1, 6), (2, 10), (3, 6), (4, 6)],
        rowSpacing=[(1, 6), (2, 6), (3, 6), (4, 6)]
    )

    cmds.text(parent=output_grid, label="Image Name", align="left")
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
    cmds.intField("rh_width", parent=output_grid, value=width, minValue=1)

    cmds.text(parent=output_grid, label="Height", align="left")
    cmds.intField("rh_height", parent=output_grid, value=height, minValue=1)

    cmds.text(parent=output_grid, label="", align="left")
    cmds.text(parent=output_grid, label="Stored in task JSON", align="left")

    return tab

def build_validation_tab(api, tabs):
    tab = cmds.columnLayout(
        parent=tabs,
        adjustableColumn=True,
        rowSpacing=7
    )

    create_section_title(
        tab,
        "Checks",
        "Errors block submission; warnings remain visible for review."
    )

    counters = cmds.rowLayout(
        parent=tab,
        numberOfColumns=5,
        adjustableColumn=5,
        columnWidth5=(118, 118, 118, 118, 118)
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
        columnWidth4=(70, 180, 70, 275)
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

    cmds.text(
        api.VALIDATION_SUMMARY_NAME,
        parent=tab,
        label="Errors: 0    Warnings: 0    Info: 0    Passed: 0    Total: 0",
        align="left",
        height=22,
        backgroundColor=PANEL
    )

    cmds.textScrollList(
        api.VALIDATION_LIST_NAME,
        parent=tab,
        numberOfRows=14,
        allowMultiSelection=False,
        doubleClickCommand=api.select_validation_node,
        height=270
    )

    buttons = cmds.rowLayout(
        parent=tab,
        numberOfColumns=4,
        adjustableColumn=4,
        columnWidth4=(148, 148, 148, 148)
    )

    cmds.button(
        parent=buttons,
        label="Run Checks",
        height=34,
        backgroundColor=BLUE,
        command=api.validate_scene_from_ui
    )
    cmds.button(parent=buttons, label="Select", height=34, command=api.select_validation_node)
    cmds.button(parent=buttons, label="Export", height=34, command=api.export_validation_report)
    cmds.button(parent=buttons, label="Clear", height=34, command=clear_validation_results)

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
        "More",
        "Task files, diagnostics and low-frequency maintenance actions."
    )

    task_frame = cmds.frameLayout(
        parent=column,
        label="Task Files",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    task_column = cmds.columnLayout(
        parent=task_frame,
        adjustableColumn=True,
        rowSpacing=6
    )

    task_row = cmds.rowLayout(
        parent=task_column,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(300, 300)
    )

    cmds.button(parent=task_row, label="Save As...", height=32, command=api.save_task_json_as)
    cmds.button(parent=task_row, label="Auto Save", height=32, command=api.save_task_json_auto)
    cmds.button(parent=task_column, label="Open Tasks Folder", height=30, command=api.open_tasks_folder)

    diagnostics_frame = cmds.frameLayout(
        parent=column,
        label="Diagnostics",
        collapsable=False,
        marginWidth=10,
        marginHeight=8,
        backgroundColor=PANEL
    )

    diagnostics_column = cmds.columnLayout(
        parent=diagnostics_frame,
        adjustableColumn=True,
        rowSpacing=6
    )

    diagnostics_row = cmds.rowLayout(
        parent=diagnostics_column,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(300, 300)
    )

    cmds.button(parent=diagnostics_row, label="Generate Log", height=32, command=api.generate_diagnostics_log)
    cmds.button(parent=diagnostics_row, label="Open Logs", height=32, command=api.open_diagnostics_folder)
    cmds.button(parent=diagnostics_column, label="Open Validation Reports", height=30, command=open_validation_reports_folder)

    maintenance = cmds.frameLayout(
        parent=column,
        label="Maintenance",
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
        label="Advanced profile maintenance. Normally you do not need this section.",
        align="left",
        height=24
    )

    cmds.button(
        parent=maintenance_column,
        label="Remove RenderHive from this Maya profile",
        height=28,
        backgroundColor=MUTED,
        command=api.uninstall_renderhive_from_maya
    )

    return tab

def build_action_bar(api, root):
    action_bar = cmds.columnLayout(
        parent=root,
        adjustableColumn=True,
        rowSpacing=4,
        height=84,
        backgroundColor=BG
    )

    cmds.separator(parent=action_bar, height=6, style="in")

    row = cmds.rowLayout(
        parent=action_bar,
        numberOfColumns=3,
        adjustableColumn=3,
        columnWidth3=(135, 165, 330)
    )

    cmds.button(
        parent=row,
        label="Sync",
        height=36,
        backgroundColor=PANEL_ALT,
        command=api.refresh_from_scene
    )

    cmds.button(
        parent=row,
        label="Validate",
        height=36,
        backgroundColor=BLUE,
        command=api.validate_scene_from_ui
    )

    cmds.button(
        parent=row,
        label="Run Local Worker",
        height=36,
        backgroundColor=ACCENT_DARK,
        command=api.run_local_worker
    )

    cmds.text(
        api.STATUS_TEXT_NAME,
        parent=action_bar,
        label="  READY",
        align="left",
        height=24,
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

    window = cmds.window(
        api.WINDOW_NAME,
        title="RenderHive  |  Submitter v{}".format(UI_VERSION),
        widthHeight=(WINDOW_WIDTH, WINDOW_HEIGHT),
        sizeable=True,
        closeCommand=on_submitter_close,
        backgroundColor=BG
    )

    root = cmds.formLayout(parent=window, backgroundColor=BG)

    header = cmds.rowLayout(
        parent=root,
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(58, 570),
        height=66,
        backgroundColor=BG
    )

    cmds.text(
        parent=header,
        label="RH",
        align="center",
        font="boldLabelFont",
        width=52,
        height=52,
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
        height=28
    )

    cmds.text(
        parent=header_info,
        label="{}  |  Maya {}".format(scene_name, cmds.about(version=True)),
        align="left",
        height=20,
        backgroundColor=PANEL
    )

    tabs = cmds.tabLayout(
        parent=root,
        innerMarginWidth=8,
        innerMarginHeight=8
    )

    job_tab = build_job_tab(api, tabs, scene_name, project_path)
    render_tab = build_render_tab(api, tabs, scene_name, start, end, width, height)
    validation_tab = build_validation_tab(api, tabs)
    tools_tab = build_tools_tab(api, tabs)

    cmds.tabLayout(
        tabs,
        edit=True,
        tabLabel=[
            (job_tab, "JOB"),
            (render_tab, "RENDER"),
            (validation_tab, "CHECKS"),
            (tools_tab, "MORE"),
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
            (tabs, "top", 4, header),
            (tabs, "bottom", 4, action_bar),
        ]
    )

    cmds.showWindow(window)

    try:
        cmds.window(window, edit=True, widthHeight=(WINDOW_WIDTH, WINDOW_HEIGHT))
    except Exception:
        pass

    api.rebuild_camera_menu()
    load_ui_preferences()
    refresh_filtered_validation_results()
    api.set_status("Ready")

    return window

