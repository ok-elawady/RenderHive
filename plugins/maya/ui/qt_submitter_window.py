from __future__ import print_function

import datetime
import hashlib
import importlib
import json
import math
import os
import platform
import sys
import uuid

from .qt_compat import QtCore, QtGui, QtWidgets, wrapInstance

import maya.OpenMayaUI as omui
import maya.cmds as cmds

from .qt_theme import COLORS, build_stylesheet
from core.state_store import StateStore


WINDOW_OBJECT_NAME = "RenderHiveQtSubmitter"
UI_VERSION = "1.9.3"
_WINDOW = None
_API = None
_WIDGETS = {}
_ORIGINAL_BUILD_TASK = None
_ORIGINAL_VALIDATE_TASK = None


# -----------------------------------------------------------------------------
# Maya / API bridge
# -----------------------------------------------------------------------------


def maya_main_window():
    pointer = omui.MQtUtil.mainWindow()
    if pointer is None:
        return None
    return wrapInstance(int(pointer), QtWidgets.QWidget)


def icon_path(filename):
    package_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    return os.path.join(package_root, "icons", filename)


def register(name, widget):
    _WIDGETS[name] = widget
    return widget


def qt_get_text(name, default=""):
    widget = _WIDGETS.get(name)
    if isinstance(widget, QtWidgets.QLineEdit):
        return widget.text()
    return default


def qt_set_text(name, value):
    widget = _WIDGETS.get(name)
    if isinstance(widget, QtWidgets.QLineEdit):
        widget.setText(str(value or ""))


def qt_get_int(name, default=0):
    widget = _WIDGETS.get(name)
    if isinstance(widget, QtWidgets.QSpinBox):
        return int(widget.value())
    return int(default)


def qt_set_int(name, value):
    widget = _WIDGETS.get(name)
    if isinstance(widget, QtWidgets.QSpinBox):
        widget.setValue(int(value))


def qt_get_option(name, default=""):
    widget = _WIDGETS.get(name)

    if isinstance(widget, QtWidgets.QComboBox):
        return widget.currentText()

    if hasattr(widget, "currentText"):
        try:
            return widget.currentText()
        except Exception:
            pass

    return default


def qt_set_status(message):
    message = str(message or "Ready")

    if _WINDOW is not None:
        try:
            _WINDOW.set_status(message)
            _WINDOW.append_activity(message)
        except Exception:
            pass

    print("[RenderHive] {}".format(message))


def qt_refresh_from_scene(*args):
    if _WINDOW is not None:
        _WINDOW.sync_from_scene()


def qt_rebuild_camera_menu():
    combo = _WIDGETS.get("rh_camera")
    if not isinstance(combo, QtWidgets.QComboBox):
        return

    previous = combo.currentText()
    combo.blockSignals(True)
    combo.clear()

    cameras = _API.get_cameras()
    renderable = _API.get_renderable_camera()

    if cameras:
        combo.addItems(cameras)
        preferred = renderable if renderable in cameras else previous
        index = combo.findText(preferred)
        combo.setCurrentIndex(index if index >= 0 else 0)
    else:
        combo.addItem("NoCamera")

    combo.blockSignals(False)


def load_validation_engine_class():
    submitter_dir = os.path.abspath(_API.get_submitter_dir())

    if submitter_dir in sys.path:
        sys.path.remove(submitter_dir)
    sys.path.insert(0, submitter_dir)

    validation_dir = os.path.join(submitter_dir, "validation")

    if not os.path.isdir(validation_dir):
        raise RuntimeError(
            "RenderHive validation folder was not found: {}".format(
                validation_dir
            )
        )

    for filename in sorted(os.listdir(validation_dir)):
        if not filename.endswith("_checks.py"):
            continue

        module_name = "validation.{}".format(filename[:-3])
        module = importlib.import_module(module_name)
        importlib.reload(module)

    collector_path = os.path.join(
        submitter_dir,
        "core",
        "dependency_collector.py",
    )

    if os.path.exists(collector_path):
        collector = importlib.import_module("core.dependency_collector")
        importlib.reload(collector)

    validator = importlib.import_module("validation.validator")
    importlib.reload(validator)
    return validator.ValidationEngine



def load_autofix_module():
    module = importlib.import_module(
        "validation.autofix"
    )
    importlib.reload(module)
    return module


def result_auto_fix_state(result):
    try:
        module = load_autofix_module()
        return {
            "fixable": module.can_fix_result(result),
            "batch_safe": module.is_batch_safe(result),
            "confirmation": module.requires_confirmation(result),
            "label": module.fix_label(result),
        }
    except Exception:
        return {
            "fixable": False,
            "batch_safe": False,
            "confirmation": False,
            "label": "Auto Fix",
        }


def severity_color(severity):
    value = str(severity or "INFO").upper()
    return {
        "ERROR": COLORS["error"],
        "WARNING": COLORS["warning"],
        "PASSED": COLORS["success"],
        "INFO": COLORS["info"],
    }.get(value, COLORS["secondary"])


def severity_symbol(severity):
    return {
        "ERROR": "●",
        "WARNING": "▲",
        "PASSED": "✓",
        "INFO": "●",
    }.get(str(severity or "INFO").upper(), "●")


def rebuild_category_filter(results):
    combo = _WIDGETS.get("category_filter")
    if not isinstance(combo, QtWidgets.QComboBox):
        return

    previous = combo.currentText() or "All"
    categories = sorted(
        set(item.get("category", "General") for item in results)
    )

    combo.blockSignals(True)
    combo.clear()
    combo.addItem("All")
    combo.addItems(categories)

    index = combo.findText(previous)
    combo.setCurrentIndex(index if index >= 0 else 0)
    combo.blockSignals(False)


def update_validation_ui(report):
    results = report.get("results", [])
    summary = report.get("summary", {})

    rebuild_category_filter(results)

    counter_data = {
        "counter_error": ("ERROR", summary.get("ERROR", 0), COLORS["error"]),
        "counter_warning": (
            "WARNING",
            summary.get("WARNING", 0),
            COLORS["warning"],
        ),
        "counter_info": ("INFO", summary.get("INFO", 0), COLORS["info"]),
        "counter_passed": (
            "PASSED",
            summary.get("PASSED", 0),
            COLORS["success"],
        ),
        "counter_total": ("TOTAL", summary.get("total", 0), COLORS["light"]),
    }

    for name, (title, count, color) in counter_data.items():
        button = _WIDGETS.get(name)
        if isinstance(button, QtWidgets.QPushButton):
            button.setText("{}\n{}".format(title, count))
            button.setStyleSheet(
                "QPushButton#CounterCard {"
                "border-top:3px solid %s;"
                "}" % color
            )

    refresh_validation_filters()

    if _WINDOW is not None:
        _WINDOW.update_validation_summary(summary)


def refresh_validation_filters(*args):
    tree = _WIDGETS.get("validation_tree")
    if not isinstance(tree, QtWidgets.QTreeWidget):
        return

    severity_combo = _WIDGETS.get("severity_filter")
    category_combo = _WIDGETS.get("category_filter")

    severity_filter = (
        severity_combo.currentText()
        if isinstance(severity_combo, QtWidgets.QComboBox)
        else "All"
    )
    category_filter = (
        category_combo.currentText()
        if isinstance(category_combo, QtWidgets.QComboBox)
        else "All"
    )

    tree.clear()
    filtered_count = 0

    for result in _API.VALIDATION_RESULTS:
        severity = str(result.get("severity", "INFO")).upper()
        category = result.get("category", "General")

        if severity_filter != "All" and severity != severity_filter:
            continue
        if category_filter != "All" and category != category_filter:
            continue

        filtered_count += 1
        message = result.get("message", "")
        node = result.get("node", "") or "—"

        item = QtWidgets.QTreeWidgetItem(
            [
                "{}  {}".format(severity_symbol(severity), severity),
                category,
                message,
                node,
            ]
        )
        item.setData(0, QtCore.Qt.UserRole, result)
        item.setForeground(0, QtGui.QBrush(QtGui.QColor(severity_color(severity))))
        item.setToolTip(2, message)
        item.setToolTip(3, node)
        tree.addTopLevelItem(item)

    if _API.VALIDATION_RESULTS and filtered_count == 0:
        item = QtWidgets.QTreeWidgetItem(
            ["", "", "No results match the active filters.", ""]
        )
        item.setForeground(2, QtGui.QBrush(QtGui.QColor(COLORS["muted"])))
        tree.addTopLevelItem(item)

    if _WINDOW is not None:
        _WINDOW.clear_validation_details()
        _WINDOW.update_autofix_actions()


def get_selected_validation_result():
    tree = _WIDGETS.get("validation_tree")
    if not isinstance(tree, QtWidgets.QTreeWidget):
        return None

    item = tree.currentItem()
    if item is None:
        return None

    result = item.data(0, QtCore.Qt.UserRole)
    return result if isinstance(result, dict) else None


def clear_validation_results(*args):
    _API.VALIDATION_RESULTS = []
    _API.VALIDATION_REPORT = {}

    update_validation_ui(
        {
            "results": [],
            "summary": {
                "ERROR": 0,
                "WARNING": 0,
                "INFO": 0,
                "PASSED": 0,
                "total": 0,
            },
        }
    )
    qt_set_status("Validation results cleared.")



def qt_get_bool(name, default=False):
    widget = _WIDGETS.get(name)
    if isinstance(widget, QtWidgets.QCheckBox):
        return bool(widget.isChecked())
    return bool(default)


def qt_get_list(name, default=None):
    widget = _WIDGETS.get(name)

    if hasattr(widget, "selected_values"):
        try:
            return list(widget.selected_values())
        except Exception:
            pass

    if isinstance(widget, QtWidgets.QLineEdit):
        return split_worker_list(widget.text())

    return list(default or [])


def qt_set_list(name, values):
    widget = _WIDGETS.get(name)

    if hasattr(widget, "set_selected_values"):
        widget.set_selected_values(values or [])
        return

    if isinstance(widget, QtWidgets.QLineEdit):
        widget.setText(", ".join(values or []))


def qt_refresh_available_workers(*args):
    if _WINDOW is not None:
        _WINDOW.sync_available_workers()


def qt_set_available_workers(workers):
    if _WINDOW is not None:
        _WINDOW.apply_available_workers(workers)


def split_worker_list(value):
    if not value:
        return []

    result = []
    for item in str(value).replace(";", ",").split(","):
        clean = item.strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def validation_summary():
    report = getattr(_API, "VALIDATION_REPORT", {}) or {}
    summary = report.get("summary", {}) or {}

    return {
        "valid": int(summary.get("ERROR", 0)) == 0,
        "errors": int(summary.get("ERROR", 0)),
        "warnings": int(summary.get("WARNING", 0)),
        "info": int(summary.get("INFO", 0)),
        "passed": int(summary.get("PASSED", 0)),
        "total": int(summary.get("total", 0)),
    }


def build_task_v2():
    """Extend the legacy task without breaking the local worker."""

    base_task = _ORIGINAL_BUILD_TASK()
    task = dict(base_task)

    frame_start = int(task.get("frame_start", 1))
    frame_end = int(task.get("frame_end", frame_start))
    frame_step = max(1, qt_get_int("rh_frame_step", 1))
    chunk_size = max(1, qt_get_int("rh_chunk_size", 10))

    if frame_end >= frame_start:
        frame_count = ((frame_end - frame_start) // frame_step) + 1
    else:
        frame_count = 0

    task_count = int(math.ceil(float(frame_count) / float(chunk_size))) if frame_count else 0

    pool_name = qt_get_option("rh_pool", "All Workers")
    if _WINDOW is not None:
        pool_workers = _WINDOW.selected_pool_worker_ids()
        pool_id = _WINDOW.selected_pool_id()
        eligible_workers = _WINDOW.eligible_worker_ids()
        worker_targeting_synced = bool(
            _WINDOW.worker_target_has_sync
        )
        worker_targeting_stale = bool(
            _WINDOW.worker_data_is_stale()
        )
        online_pool_workers = len(
            _WINDOW.online_pool_workers()
        )
    else:
        pool_workers = []
        pool_id = ""
        eligible_workers = []
        worker_targeting_synced = False
        worker_targeting_stale = True
        online_pool_workers = 0

    serialized_pool_name = (
        "All"
        if pool_name == "All Workers"
        else pool_name
    )

    assignment_mode = qt_get_option(
        "rh_worker_assignment_mode",
        "Use All Workers in Pool",
    )
    selected_only = assignment_mode == "Use Selected Workers Only"

    allowed_workers = qt_get_list("rh_allowed_workers", [])
    denied_workers = qt_get_list("rh_denied_workers", [])

    # The UI exposes one targeting strategy at a time. Keep the payload
    # compatible with the existing backend contract while making overlap
    # impossible by construction.
    if selected_only:
        denied_workers = []
    else:
        allowed_workers = []

    dependencies = split_worker_list(qt_get_text("rh_job_dependencies", ""))

    task_id = "RH-{}-{}".format(
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
        uuid.uuid4().hex[:6].upper(),
    )

    task.update(
        {
            "schema_version": "2.0",
            "task_uid": task_id,
            "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "frame_step": frame_step,
            "chunk_size": chunk_size,
            "machine_limit": qt_get_int("rh_machine_limit", 0),
            "concurrent_tasks": qt_get_int("rh_concurrent_tasks", 1),
            "pool": serialized_pool_name,
            "pool_id": pool_id,
            "pool_workers": pool_workers,
            "allowed_workers": allowed_workers,
            "denied_workers": denied_workers,
            "eligible_workers": eligible_workers,
            "eligible_worker_count": len(eligible_workers),
            "online_pool_worker_count": online_pool_workers,
            "worker_targeting_synced": worker_targeting_synced,
            "worker_targeting_stale": worker_targeting_stale,
            "worker_assignment_mode": (
                "selected_only"
                if selected_only
                else "all_in_pool"
            ),
            "start_suspended": qt_get_bool("rh_start_suspended", False),
            "retry_count": qt_get_int("rh_retry_count", 2),
            "task_timeout_minutes": qt_get_int("rh_timeout_minutes", 0),
            "submission_mode": qt_get_option("rh_submission_mode", "Shared Storage"),
            "department": qt_get_text("rh_department", ""),
            "comment": qt_get_text("rh_comment", ""),
            "job_dependencies": dependencies,
            "minimum_ram_gb": qt_get_int("rh_min_ram_gb", 0),
            "minimum_vram_gb": qt_get_int("rh_min_vram_gb", 0),
        }
    )

    task["job"] = {
        "uid": task_id,
        "name": task.get("job_name", ""),
        "project": task.get("project_name", ""),
        "department": task.get("department", ""),
        "comment": task.get("comment", ""),
        "priority": int(task.get("priority", 50)),
        "start_suspended": task.get("start_suspended", False),
        "dependencies": dependencies,
    }

    task["frames"] = {
        "start": frame_start,
        "end": frame_end,
        "step": frame_step,
        "count": frame_count,
        "chunk_size": chunk_size,
        "task_count": task_count,
    }

    task["farm"] = {
        "pool": task.get("pool", "All"),
        "pool_id": task.get("pool_id", ""),
        "pool_workers": pool_workers,
        "machine_limit": task.get("machine_limit", 0),
        "concurrent_tasks": task.get("concurrent_tasks", 1),
        "allowed_workers": allowed_workers,
        "denied_workers": denied_workers,
        "worker_selection": {
            "pool_name": task.get("pool", "All"),
            "pool_id": task.get("pool_id", ""),
            "pool_workers": pool_workers,
            "allowed_workers": allowed_workers,
            "denied_workers": denied_workers,
            "assignment_mode": task.get(
                "worker_assignment_mode",
                "all_in_pool",
            ),
            "eligible_workers": eligible_workers,
            "eligible_worker_count": len(eligible_workers),
            "online_pool_worker_count": online_pool_workers,
            "synced": worker_targeting_synced,
            "stale": worker_targeting_stale,
            "empty_pool_means_all": True,
            "empty_allowed_means_entire_pool": True,
            "empty_denied_means_none": True,
        },
        "hardware": {
            "minimum_ram_gb": task.get("minimum_ram_gb", 0),
            "minimum_vram_gb": task.get("minimum_vram_gb", 0),
        },
    }

    task["failure_policy"] = {
        "retry_count": task.get("retry_count", 2),
        "task_timeout_minutes": task.get("task_timeout_minutes", 0),
    }

    task["submission"] = {
        "mode": task.get("submission_mode", "Shared Storage"),
        "scene_path": task.get("scene_path", ""),
        "project_path": task.get("project_path", ""),
        "output_path": task.get("output_path", ""),
    }

    task["software_info"] = {
        "dcc": "maya",
        "maya_version": str(cmds.about(version=True)),
        "renderer": task.get("renderer", ""),
        "host_os": platform.system(),
    }

    task["validation"] = validation_summary()

    return task


def validate_task_v2(task):
    errors = list(_ORIGINAL_VALIDATE_TASK(task))

    if int(task.get("frame_step", 1)) < 1:
        errors.append("Frame step must be at least 1.")

    if int(task.get("chunk_size", 1)) < 1:
        errors.append("Chunk size must be at least 1.")

    if int(task.get("machine_limit", 0)) < 0:
        errors.append("Machine limit cannot be negative.")

    if int(task.get("concurrent_tasks", 1)) < 1:
        errors.append("Concurrent tasks must be at least 1.")

    allowed = set(task.get("allowed_workers", []))
    denied = set(task.get("denied_workers", []))
    overlap = sorted(allowed.intersection(denied))

    if overlap:
        errors.append(
            "Workers cannot be both allowed and denied: {}".format(
                ", ".join(overlap)
            )
        )

    assignment_mode = str(
        task.get("worker_assignment_mode") or "all_in_pool"
    )

    if assignment_mode == "selected_only" and not allowed:
        errors.append(
            "Select at least one worker when using Selected Workers Only."
        )

    pool_workers = set(task.get("pool_workers", []))
    if pool_workers and allowed:
        outside_pool = sorted(allowed.difference(pool_workers))
        if outside_pool:
            errors.append(
                "Selected workers must exist inside the selected pool: {}".format(
                    ", ".join(outside_pool)
                )
            )

    if pool_workers and denied:
        outside_pool = sorted(denied.difference(pool_workers))
        if outside_pool:
            errors.append(
                "Excluded workers must exist inside the selected pool: {}".format(
                    ", ".join(outside_pool)
                )
            )

    return errors

def install_api_bridge(api):
    global _ORIGINAL_BUILD_TASK
    global _ORIGINAL_VALIDATE_TASK

    api.get_text = qt_get_text
    api.set_text = qt_set_text
    api.get_int = qt_get_int
    api.set_int = qt_set_int
    api.get_option = qt_get_option
    api.set_status = qt_set_status
    api.refresh_from_scene = qt_refresh_from_scene
    api.rebuild_camera_menu = qt_rebuild_camera_menu
    api.load_validation_engine_class = load_validation_engine_class
    api.update_validation_ui = update_validation_ui
    api.get_selected_validation_result = get_selected_validation_result
    api.clear_validation_results = clear_validation_results
    api.refresh_available_workers = qt_refresh_available_workers
    api.set_available_workers = qt_set_available_workers

    package_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    if package_root in sys.path:
        sys.path.remove(package_root)
    sys.path.insert(0, package_root)

    # The plugin folder can be updated while Maya still has older API
    # submodules cached. Purge the complete generic ``api`` package before
    # importing the bridge so api.client, api.config and api.payload always
    # come from this active RenderHive installation.
    for module_name in list(sys.modules):
        if (
            module_name == "api"
            or module_name.startswith("api.")
        ):
            del sys.modules[module_name]

    importlib.invalidate_caches()

    api_bridge = importlib.import_module(
        "api.maya_bridge"
    )
    api_bridge.install(api)

    if not hasattr(api, "_renderhive_legacy_build_task"):
        api._renderhive_legacy_build_task = api.build_task

    if not hasattr(api, "_renderhive_legacy_validate_task"):
        api._renderhive_legacy_validate_task = api.validate_task

    _ORIGINAL_BUILD_TASK = api._renderhive_legacy_build_task
    _ORIGINAL_VALIDATE_TASK = api._renderhive_legacy_validate_task

    api.build_task = build_task_v2
    api.validate_task = validate_task_v2


# -----------------------------------------------------------------------------
# Reusable widgets
# -----------------------------------------------------------------------------


def worker_identifier(worker):
    if not isinstance(worker, dict):
        return str(worker or "").strip()

    return str(
        worker.get("id")
        or worker.get("worker_id")
        or worker.get("hostname")
        or worker.get("name")
        or ""
    ).strip()


def worker_display_name(worker):
    if not isinstance(worker, dict):
        return str(worker or "").strip()

    return str(
        worker.get("hostname")
        or worker.get("machine_name")
        or worker.get("label")
        or worker.get("display_name")
        or worker.get("name")
        or worker_identifier(worker)
        or "Unnamed Worker"
    ).strip()


def worker_status(worker):
    if not isinstance(worker, dict):
        return ""

    return str(
        worker.get("status")
        or worker.get("state")
        or ""
    ).strip().upper()


def worker_is_online(worker):
    status = worker_status(worker)

    if status in (
        "OFFLINE",
        "DISCONNECTED",
        "DISABLED",
    ):
        return False

    if isinstance(worker, dict):
        available = worker.get("available")
        if available is False:
            return False

    return status in (
        "",
        "ONLINE",
        "IDLE",
        "AVAILABLE",
        "RENDERING",
        "BUSY",
        "WORKING",
    )


def _safe_number(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def worker_memory_gb(worker):
    if not isinstance(worker, dict):
        return None

    direct_gb = _safe_number(
        worker.get("ram_gb")
        or worker.get("memory_gb")
    )
    if direct_gb is not None:
        return direct_gb

    memory_mb = _safe_number(
        worker.get("memory_mb")
        or worker.get("ram_mb")
    )
    if memory_mb is not None:
        return memory_mb / 1024.0

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        direct_gb = _safe_number(
            system_info.get("ram_gb")
            or system_info.get("memory_gb")
        )
        if direct_gb is not None:
            return direct_gb

        memory_mb = _safe_number(
            system_info.get("memory_mb")
            or system_info.get("ram_mb")
            or system_info.get("total_memory_mb")
        )
        if memory_mb is not None:
            return memory_mb / 1024.0

    return None


def worker_vram_gb(worker):
    if not isinstance(worker, dict):
        return None

    direct_gb = _safe_number(
        worker.get("vram_gb")
        or worker.get("gpu_vram_gb")
    )
    if direct_gb is not None:
        return direct_gb

    direct_mb = _safe_number(
        worker.get("vram_mb")
        or worker.get("gpu_memory_mb")
    )
    if direct_mb is not None:
        return direct_mb / 1024.0

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        direct_gb = _safe_number(
            system_info.get("vram_gb")
            or system_info.get("gpu_vram_gb")
        )
        if direct_gb is not None:
            return direct_gb

        direct_mb = _safe_number(
            system_info.get("vram_mb")
            or system_info.get("gpu_memory_mb")
            or system_info.get("total_vram_mb")
        )
        if direct_mb is not None:
            return direct_mb / 1024.0

    return None


def worker_gpu_text(worker):
    if not isinstance(worker, dict):
        return "—"

    values = (
        worker.get("gpu_models")
        or worker.get("gpus")
        or worker.get("gpu_model")
        or []
    )

    if isinstance(values, str):
        values = [values]

    if isinstance(values, (list, tuple)):
        labels = []
        for value in values:
            if isinstance(value, dict):
                label = str(
                    value.get("name")
                    or value.get("model")
                    or ""
                ).strip()
            else:
                label = str(value or "").strip()

            if label and label not in labels:
                labels.append(label)

        if labels:
            return ", ".join(labels)

    system_info = worker.get("system_info")
    if isinstance(system_info, dict):
        value = (
            system_info.get("gpu_models")
            or system_info.get("gpus")
            or system_info.get("gpu")
        )
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (list, tuple)):
            labels = [str(item).strip() for item in value if str(item).strip()]
            if labels:
                return ", ".join(labels)

    return "—"


def format_gb(value):
    number = _safe_number(value)
    if number is None:
        return "—"

    if abs(number - round(number)) < 0.05:
        return "{} GB".format(int(round(number)))

    return "{:.1f} GB".format(number)


class WorkerStatusChip(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super(WorkerStatusChip, self).__init__(str(text), parent)
        self.setObjectName("WorkerStatusChip")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.set_state(text or "Not Synced", COLORS["muted"])

    def set_state(self, text, color):
        color = str(color or COLORS["muted"])
        self.setText(str(text or "—"))
        self.setStyleSheet(
            "QLabel#WorkerStatusChip {"
            "background-color:%s;"
            "border:1px solid %s;"
            "color:%s;"
            "border-radius:9px;"
            "padding:3px 8px;"
            "font-size:10px;"
            "font-weight:600;"
            "}" % (COLORS["surface2"], color, color)
        )


class SegmentedChoice(QtWidgets.QFrame):
    currentTextChanged = QtCore.Signal(str)

    def __init__(self, options, parent=None):
        super(SegmentedChoice, self).__init__(parent)
        self.setObjectName("SegmentedControl")
        self._options = [str(value) for value in options]
        self._buttons = []
        self._current = self._options[0] if self._options else ""

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)

        for index, option in enumerate(self._options):
            button = QtWidgets.QPushButton(option)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.clicked.connect(
                lambda checked=False, value=option: self.setCurrentText(value)
            )
            self._group.addButton(button, index)
            self._buttons.append(button)
            layout.addWidget(button, 1)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def currentText(self):
        return self._current

    def setCurrentText(self, value):
        value = str(value or "")
        if value not in self._options:
            return False

        changed = value != self._current
        self._current = value

        for option, button in zip(self._options, self._buttons):
            button.blockSignals(True)
            button.setChecked(option == value)
            button.blockSignals(False)

        if changed:
            self.currentTextChanged.emit(value)

        return True

    def findText(self, value):
        try:
            return self._options.index(str(value))
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        try:
            value = self._options[int(index)]
        except Exception:
            return
        self.setCurrentText(value)

    def isEditable(self):
        return False


class CollapsibleSection(QtWidgets.QWidget):
    toggled = QtCore.Signal(bool)

    def __init__(self, title, parent=None):
        super(CollapsibleSection, self).__init__(parent)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.header = QtWidgets.QToolButton()
        self.header.setObjectName("CollapsibleHeader")
        self.header.setText(str(title))
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.setToolButtonStyle(
            QtCore.Qt.ToolButtonTextBesideIcon
        )
        self.header.setArrowType(QtCore.Qt.RightArrow)
        self.header.toggled.connect(self.setExpanded)
        root.addWidget(self.header)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 0, 0, 0)
        self.content_layout.setSpacing(7)
        self.content.setVisible(False)
        root.addWidget(self.content)

    def setExpanded(self, expanded):
        expanded = bool(expanded)
        self.header.blockSignals(True)
        self.header.setChecked(expanded)
        self.header.setArrowType(
            QtCore.Qt.DownArrow
            if expanded
            else QtCore.Qt.RightArrow
        )
        self.header.blockSignals(False)
        self.content.setVisible(expanded)
        self.toggled.emit(expanded)

    def isExpanded(self):
        return bool(self.header.isChecked())


class WorkerSelectionDialog(QtWidgets.QDialog):
    def __init__(self, title, workers, selected_values, parent=None):
        super(WorkerSelectionDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(720, 500)
        self._workers = list(workers or [])
        self._selected = set(selected_values or [])
        self._items = []

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(9)

        heading = QtWidgets.QLabel(title)
        heading.setObjectName("PageTitle")
        root.addWidget(heading)

        hint = QtWidgets.QLabel(
            "Select eligible workers from the active pool. "
            "Offline workers remain visible but cannot be selected."
        )
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by worker, status or hardware…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_items)
        root.addWidget(self.search)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels([
            "Worker",
            "Status",
            "RAM",
            "GPU",
        ])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )
        self.tree.setUniformRowHeights(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.Stretch,
        )
        self.tree.header().setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeToContents,
        )
        self.tree.header().setSectionResizeMode(
            2,
            QtWidgets.QHeaderView.ResizeToContents,
        )
        self.tree.header().setSectionResizeMode(
            3,
            QtWidgets.QHeaderView.Stretch,
        )
        root.addWidget(self.tree, 1)

        for worker in self._workers:
            worker_id = worker_identifier(worker)
            if not worker_id:
                continue

            status = worker_status(worker) or "UNKNOWN"
            online = worker_is_online(worker)
            item = QtWidgets.QTreeWidgetItem([
                worker_display_name(worker),
                status.replace("_", " ").title(),
                format_gb(worker_memory_gb(worker)),
                worker_gpu_text(worker),
            ])
            item.setData(0, QtCore.Qt.UserRole, worker_id)
            item.setFlags(
                item.flags() | QtCore.Qt.ItemIsUserCheckable
            )
            item.setCheckState(
                0,
                QtCore.Qt.Checked
                if online and worker_id in self._selected
                else QtCore.Qt.Unchecked,
            )

            if not online:
                item.setFlags(
                    item.flags() & ~QtCore.Qt.ItemIsEnabled
                )
                item.setToolTip(
                    0,
                    "This worker is offline and cannot receive the job.",
                )

            status_color = (
                COLORS["info"]
                if status in ("RENDERING", "BUSY", "WORKING")
                else (
                    COLORS["success"]
                    if online
                    else COLORS["muted"]
                )
            )
            item.setForeground(
                1,
                QtGui.QBrush(QtGui.QColor(status_color)),
            )

            worker_ip = str(worker.get("ip_address") or "").strip()
            last_ping = str(worker.get("last_ping") or "").strip()
            tooltip = []
            if worker_ip:
                tooltip.append("IP: {}".format(worker_ip))
            if last_ping:
                tooltip.append("Last ping: {}".format(last_ping))
            if tooltip:
                item.setToolTip(0, " | ".join(tooltip))

            self.tree.addTopLevelItem(item)
            self._items.append(item)

        if not self._items:
            item = QtWidgets.QTreeWidgetItem([
                "No workers were returned by the API.",
                "—",
                "—",
                "—",
            ])
            item.setFlags(QtCore.Qt.NoItemFlags)
            item.setForeground(
                0,
                QtGui.QBrush(QtGui.QColor(COLORS["muted"])),
            )
            self.tree.addTopLevelItem(item)

        utility = QtWidgets.QHBoxLayout()

        select_all = QtWidgets.QPushButton("Select Eligible")
        select_all.clicked.connect(self.select_all)

        clear = QtWidgets.QPushButton("Clear")
        clear.setObjectName("GhostButton")
        clear.clicked.connect(self.clear_all)

        utility.addWidget(select_all)
        utility.addWidget(clear)
        utility.addStretch()
        root.addLayout(utility)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Cancel
            | QtWidgets.QDialogButtonBox.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def filter_items(self, value):
        query = str(value or "").strip().lower()

        for item in self._items:
            searchable = " ".join(
                item.text(column)
                for column in range(item.columnCount())
            ).lower()
            item.setHidden(
                bool(query and query not in searchable)
            )

    def select_all(self):
        for item in self._items:
            if (
                not item.isHidden()
                and bool(item.flags() & QtCore.Qt.ItemIsEnabled)
            ):
                item.setCheckState(0, QtCore.Qt.Checked)

    def clear_all(self):
        for item in self._items:
            item.setCheckState(0, QtCore.Qt.Unchecked)

    def selected_values(self):
        values = []

        for item in self._items:
            if (
                bool(item.flags() & QtCore.Qt.ItemIsEnabled)
                and item.checkState(0) == QtCore.Qt.Checked
            ):
                value = item.data(0, QtCore.Qt.UserRole)
                if value and value not in values:
                    values.append(str(value))

        return values


class WorkerMultiSelect(QtWidgets.QPushButton):
    selectionChanged = QtCore.Signal()

    def __init__(self, title, empty_text, parent=None):
        super(WorkerMultiSelect, self).__init__(parent)
        self._title = str(title)
        self._empty_text = str(empty_text)
        self._workers = []
        self._selected_values = []
        self.setMinimumHeight(30)
        self.setToolTip(
            "Open the worker selector. The button text summarizes the current "
            "selection, not the number of synced workers. Empty means: {}."
            .format(self._empty_text)
        )
        self.clicked.connect(self.open_selector)
        self.update_summary()

    def set_workers(self, workers):
        self._workers = list(workers or [])
        available_ids = {
            worker_identifier(worker)
            for worker in self._workers
            if worker_identifier(worker)
            and worker_is_online(worker)
        }

        # Keep saved scene selections while the API is unavailable or before
        # the first worker sync finishes. Once workers are available, discard
        # IDs that no longer exist on the backend.
        if available_ids:
            self._selected_values = [
                value
                for value in self._selected_values
                if value in available_ids
            ]

        self.update_summary()

    def selected_values(self):
        return list(self._selected_values)

    def set_selected_values(self, values):
        clean = []
        for value in values or []:
            value = str(value).strip()
            if value and value not in clean:
                clean.append(value)

        if clean == self._selected_values:
            self.update_summary()
            return

        self._selected_values = clean
        self.update_summary()
        self.selectionChanged.emit()

    def open_selector(self):
        dialog = WorkerSelectionDialog(
            self._title,
            self._workers,
            self._selected_values,
            parent=self.window(),
        )

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        self._selected_values = dialog.selected_values()
        self.update_summary()
        self.selectionChanged.emit()

    def update_summary(self):
        count = len(self._selected_values)

        if count == 0:
            # Pool membership used to display "No Workers Selected", which
            # looked like the worker sync had failed even when workers were
            # available. Show the available count for that selector while
            # keeping the deliberate empty meanings for Allowed / Denied.
            if (
                self._empty_text == "No Workers Selected"
                and self._workers
            ):
                self.setText(
                    "Select Pool Members ({} available)".format(
                        len(self._workers)
                    )
                )
            else:
                self.setText(self._empty_text)
            return

        labels = {}
        for worker in self._workers:
            worker_id = worker_identifier(worker)
            labels[worker_id] = worker_display_name(worker)

        if count == 1:
            self.setText(labels.get(
                self._selected_values[0],
                self._selected_values[0],
            ))
        else:
            self.setText("{} workers selected".format(count))


class WorkerPoolManagerDialog(QtWidgets.QDialog):
    """Create, edit and delete reusable named worker pools."""

    RESERVED_NAMES = {"all", "all workers"}

    def __init__(self, workers, pools, parent=None):
        super(WorkerPoolManagerDialog, self).__init__(parent)
        self._workers = list(workers or [])
        self._pools = {
            str(name): list(values or [])
            for name, values in (pools or {}).items()
            if str(name).strip()
        }
        self._loaded_name = ""

        self.setWindowTitle("Manage Worker Pools")
        self.setModal(True)
        self.resize(650, 470)
        self.build_ui()
        self.refresh_pool_list()

    def build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QtWidgets.QLabel("Reusable Worker Pools")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        hint = QtWidgets.QLabel(
            "Create a named group such as FX, Lighting or GPU. "
            "The pool is saved locally and can be reused for later submissions."
        )
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        root.addWidget(hint)

        center = QtWidgets.QHBoxLayout()
        center.setSpacing(10)

        left = QtWidgets.QVBoxLayout()
        left_label = QtWidgets.QLabel("Saved Pools")
        left_label.setObjectName("FieldLabel")
        left.addWidget(left_label)

        self.pool_list = QtWidgets.QListWidget()
        self.pool_list.setAlternatingRowColors(True)
        self.pool_list.currentItemChanged.connect(self.load_selected_pool)
        left.addWidget(self.pool_list, 1)

        left_buttons = QtWidgets.QHBoxLayout()
        new_button = QtWidgets.QPushButton("New")
        new_button.clicked.connect(self.new_pool)
        delete_button = QtWidgets.QPushButton("Delete")
        delete_button.setObjectName("GhostButton")
        delete_button.clicked.connect(self.delete_pool)
        left_buttons.addWidget(new_button)
        left_buttons.addWidget(delete_button)
        left.addLayout(left_buttons)
        center.addLayout(left, 1)

        editor = QtWidgets.QFrame()
        editor.setObjectName("Card")
        editor_layout = QtWidgets.QVBoxLayout(editor)
        editor_layout.setContentsMargins(12, 12, 12, 12)
        editor_layout.setSpacing(8)

        name_label = QtWidgets.QLabel("Pool Name")
        name_label.setObjectName("FieldLabel")
        editor_layout.addWidget(name_label)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Example: FX")
        self.name_edit.setClearButtonEnabled(True)
        editor_layout.addWidget(self.name_edit)

        members_label = QtWidgets.QLabel("Pool Members")
        members_label.setObjectName("FieldLabel")
        editor_layout.addWidget(members_label)

        self.members = WorkerMultiSelect(
            "Pool Members",
            "No Workers Selected",
        )
        self.members.set_workers(self._workers)
        editor_layout.addWidget(self.members)

        available_lines = []
        for worker in self._workers:
            worker_label = str(
                worker.get("hostname")
                or worker.get("machine_name")
                or worker.get("label")
                or worker.get("display_name")
                or worker.get("name")
                or worker.get("id")
                or "Unnamed Worker"
            )
            worker_status = str(
                worker.get("status") or ""
            ).strip()

            if worker_status:
                available_lines.append(
                    "• {}  —  {}".format(
                        worker_label,
                        worker_status,
                    )
                )
            else:
                available_lines.append(
                    "• {}".format(worker_label)
                )

        if available_lines:
            available_text = (
                "Synced Workers Available for This Pool:\n"
                + "\n".join(available_lines)
            )
        else:
            available_text = (
                "No synced workers are currently available. "
                "Close this window and use Sync Workers first."
            )

        self.available_workers_label = QtWidgets.QLabel(
            available_text
        )
        self.available_workers_label.setObjectName("SecondaryText")
        self.available_workers_label.setWordWrap(True)
        self.available_workers_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )
        editor_layout.addWidget(self.available_workers_label)

        details = QtWidgets.QLabel(
            "Click Select Pool Members, choose one or more synced workers, "
            "then save the pool. Allowed Workers will be limited to this pool."
        )
        details.setObjectName("MutedText")
        details.setWordWrap(True)
        editor_layout.addWidget(details)
        editor_layout.addStretch()

        save_button = QtWidgets.QPushButton("Save Pool")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.save_pool)
        editor_layout.addWidget(save_button)

        center.addWidget(editor, 2)
        root.addLayout(center, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def refresh_pool_list(self, select_name=""):
        self.pool_list.blockSignals(True)
        self.pool_list.clear()

        for name in sorted(self._pools, key=lambda value: value.lower()):
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, name)
            self.pool_list.addItem(item)

        self.pool_list.blockSignals(False)

        target = select_name or self._loaded_name
        if target:
            matches = self.pool_list.findItems(
                target,
                QtCore.Qt.MatchExactly,
            )
            if matches:
                self.pool_list.setCurrentItem(matches[0])
                return

        if self.pool_list.count():
            self.pool_list.setCurrentRow(0)
        else:
            self.new_pool()

    def load_selected_pool(self, current, previous=None):
        if current is None:
            return

        name = str(current.data(QtCore.Qt.UserRole) or current.text())
        self._loaded_name = name
        self.name_edit.setText(name)
        self.members.set_selected_values(self._pools.get(name, []))

    def new_pool(self):
        self.pool_list.clearSelection()
        self._loaded_name = ""
        self.name_edit.clear()
        self.members.set_selected_values([])
        self.name_edit.setFocus()

    def save_pool(self):
        name = self.name_edit.text().strip()
        members = self.members.selected_values()

        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive",
                "Enter a pool name first.",
            )
            return

        if name.lower() in self.RESERVED_NAMES:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive",
                "This name is reserved. Choose another pool name.",
            )
            return

        if not members:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive",
                "Select at least one worker for the pool.",
            )
            return

        existing_lower = {
            value.lower(): value
            for value in self._pools
        }
        conflict = existing_lower.get(name.lower())

        if conflict and conflict != self._loaded_name:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive",
                "A pool with this name already exists.",
            )
            return

        if self._loaded_name and self._loaded_name != name:
            self._pools.pop(self._loaded_name, None)

        self._pools[name] = members
        self._loaded_name = name
        self.refresh_pool_list(select_name=name)

    def delete_pool(self):
        item = self.pool_list.currentItem()
        if item is None:
            return

        name = str(item.data(QtCore.Qt.UserRole) or item.text())
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete Worker Pool",
            "Delete the '{}' pool?".format(name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if answer != QtWidgets.QMessageBox.Yes:
            return

        self._pools.pop(name, None)
        self._loaded_name = ""
        self.refresh_pool_list()

    def pools(self):
        return {
            name: list(values)
            for name, values in self._pools.items()
        }


class ApiWorkerPoolManagerDialog(QtWidgets.QDialog):
    """Read-only browser for worker pools supplied by the RenderHive API."""

    def __init__(self, api, workers, pools, parent=None):
        super(ApiWorkerPoolManagerDialog, self).__init__(parent)
        self.api = api
        self._workers = list(workers or [])
        self._pools = list(pools or [])
        self._loaded_id = ""
        self._loaded_name = ""

        self.setWindowTitle("Worker Pools")
        self.setModal(True)
        self.resize(720, 500)
        self.build_ui()
        self.refresh_pool_list()

    def build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QtWidgets.QLabel("Worker Pools")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        hint = QtWidgets.QLabel(
            "Select a backend pool and review its workers."
        )
        hint.setObjectName("MutedText")
        root.addWidget(hint)

        center = QtWidgets.QHBoxLayout()
        center.setSpacing(10)

        left = QtWidgets.QVBoxLayout()
        left_label = QtWidgets.QLabel("Available Pools")
        left_label.setObjectName("FieldLabel")
        left.addWidget(left_label)

        self.pool_list = QtWidgets.QListWidget()
        self.pool_list.setAlternatingRowColors(True)
        self.pool_list.setMinimumWidth(220)
        self.pool_list.currentItemChanged.connect(
            self.load_selected_pool
        )
        self.pool_list.itemDoubleClicked.connect(
            lambda *_: self.use_selected_pool()
        )
        left.addWidget(self.pool_list, 1)

        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.setObjectName("GhostButton")
        refresh_button.clicked.connect(self.reload_data)
        left.addWidget(refresh_button)

        center.addLayout(left, 1)

        details = QtWidgets.QFrame()
        details.setObjectName("Card")
        details_layout = QtWidgets.QVBoxLayout(details)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(8)

        details_title = QtWidgets.QLabel("Pool Details")
        details_title.setObjectName("SectionTitle")
        details_layout.addWidget(details_title)

        name_label = QtWidgets.QLabel("Name")
        name_label.setObjectName("FieldLabel")
        details_layout.addWidget(name_label)

        self.name_value = QtWidgets.QLabel("—")
        self.name_value.setObjectName("SecondaryText")
        self.name_value.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )
        details_layout.addWidget(self.name_value)

        description_label = QtWidgets.QLabel("Description")
        description_label.setObjectName("FieldLabel")
        details_layout.addWidget(description_label)

        self.description_value = QtWidgets.QLabel("—")
        self.description_value.setObjectName("MutedText")
        self.description_value.setWordWrap(True)
        self.description_value.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )
        self.description_value.setMinimumHeight(42)
        self.description_value.setAlignment(
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop
        )
        details_layout.addWidget(self.description_value)

        workers_header = QtWidgets.QHBoxLayout()

        workers_label = QtWidgets.QLabel("Workers")
        workers_label.setObjectName("FieldLabel")
        workers_header.addWidget(workers_label)
        workers_header.addStretch()

        self.member_count = QtWidgets.QLabel("0")
        self.member_count.setObjectName("MetaChip")
        workers_header.addWidget(self.member_count)

        details_layout.addLayout(workers_header)

        self.members_tree = QtWidgets.QTreeWidget()
        self.members_tree.setColumnCount(4)
        self.members_tree.setHeaderLabels([
            "Worker",
            "Status",
            "RAM",
            "GPU",
        ])
        self.members_tree.setRootIsDecorated(False)
        self.members_tree.setAlternatingRowColors(True)
        self.members_tree.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )
        self.members_tree.setMinimumHeight(210)
        self.members_tree.header().setStretchLastSection(False)
        self.members_tree.header().setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.Stretch,
        )
        self.members_tree.header().setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeToContents,
        )
        self.members_tree.header().setSectionResizeMode(
            2,
            QtWidgets.QHeaderView.ResizeToContents,
        )
        self.members_tree.header().setSectionResizeMode(
            3,
            QtWidgets.QHeaderView.Stretch,
        )
        details_layout.addWidget(self.members_tree, 1)

        center.addWidget(details, 2)
        root.addLayout(center, 1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()

        use_button = QtWidgets.QPushButton("Use Selected Pool")
        use_button.setObjectName("PrimaryButton")
        use_button.clicked.connect(self.use_selected_pool)
        buttons.addWidget(use_button)

        close_button = QtWidgets.QPushButton("Close")
        close_button.setObjectName("GhostButton")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(close_button)

        root.addLayout(buttons)

    @staticmethod
    def _pool_id(pool):
        return (
            str(pool.get("id") or "")
            if isinstance(pool, dict)
            else ""
        )

    @staticmethod
    def _pool_name(pool):
        return (
            str(pool.get("name") or "")
            if isinstance(pool, dict)
            else ""
        )

    def pools(self):
        return list(self._pools)

    def workers(self):
        return list(self._workers)

    def selected_pool_id(self):
        return str(self._loaded_id or "")

    def selected_pool_name(self):
        return str(self._loaded_name or "")

    def pool_by_id(self, pool_id):
        for pool in self._pools:
            if self._pool_id(pool) == str(pool_id):
                return pool
        return None

    def refresh_pool_list(self, select_id=""):
        self.pool_list.blockSignals(True)
        self.pool_list.clear()

        ordered = sorted(
            [
                pool
                for pool in self._pools
                if self._pool_name(pool)
            ],
            key=lambda pool: self._pool_name(pool).lower(),
        )

        for pool in ordered:
            item = QtWidgets.QListWidgetItem(
                self._pool_name(pool)
            )
            item.setData(
                QtCore.Qt.UserRole,
                self._pool_id(pool),
            )

            description = str(
                pool.get("description") or ""
            )
            if description:
                item.setToolTip(description)

            self.pool_list.addItem(item)

        self.pool_list.blockSignals(False)

        target = str(
            select_id or self._loaded_id
        )

        if target:
            for row in range(
                self.pool_list.count()
            ):
                item = self.pool_list.item(row)

                if str(
                    item.data(QtCore.Qt.UserRole)
                    or ""
                ) == target:
                    self.pool_list.setCurrentRow(row)
                    return

        if self.pool_list.count():
            self.pool_list.setCurrentRow(0)
        else:
            self.clear_details()

    def pool_members(self, pool_id):
        values = []

        for worker in self._workers:
            if not isinstance(worker, dict):
                continue

            worker_pools = worker.get("pools") or []

            for pool in worker_pools:
                if isinstance(pool, dict):
                    candidate_id = str(
                        pool.get("id") or ""
                    )
                    candidate_name = str(
                        pool.get("name") or ""
                    )
                else:
                    candidate_id = str(pool or "")
                    candidate_name = ""

                selected_pool = self.pool_by_id(
                    pool_id
                ) or {}
                selected_name = self._pool_name(
                    selected_pool
                )

                if (
                    candidate_id == str(pool_id)
                    or (
                        selected_name
                        and candidate_name == selected_name
                    )
                ):
                    values.append(worker)
                    break

        values.sort(
            key=lambda worker: str(
                worker.get("hostname")
                or worker.get("label")
                or worker.get("name")
                or worker.get("id")
                or ""
            ).lower()
        )
        return values

    def worker_display_name(self, worker):
        return str(
            worker.get("hostname")
            or worker.get("label")
            or worker.get("machine_name")
            or worker.get("display_name")
            or worker.get("name")
            or worker.get("id")
            or "Unnamed Worker"
        )

    def refresh_members(self):
        self.members_tree.clear()

        members = self.pool_members(
            self._loaded_id
        )

        for worker in members:
            status = str(
                worker.get("status")
                or worker.get("state")
                or "Unknown"
            ).strip()

            item = QtWidgets.QTreeWidgetItem([
                self.worker_display_name(worker),
                status,
                format_gb(worker_memory_gb(worker)),
                worker_gpu_text(worker),
            ])

            status_lower = status.lower()

            if status_lower in (
                "online",
                "idle",
                "available",
            ):
                item.setForeground(
                    1,
                    QtGui.QBrush(
                        QtGui.QColor(
                            COLORS["success"]
                        )
                    ),
                )
            elif status_lower in (
                "rendering",
                "busy",
                "working",
            ):
                item.setForeground(
                    1,
                    QtGui.QBrush(
                        QtGui.QColor(
                            COLORS["info"]
                        )
                    ),
                )
            elif status_lower in (
                "offline",
                "disabled",
                "disconnected",
            ):
                item.setForeground(
                    1,
                    QtGui.QBrush(
                        QtGui.QColor(
                            COLORS["muted"]
                        )
                    ),
                )

            self.members_tree.addTopLevelItem(item)

        self.member_count.setText(
            str(len(members))
        )

        if not members:
            item = QtWidgets.QTreeWidgetItem([
                "No workers assigned",
                "—",
                "—",
                "—",
            ])
            item.setForeground(
                0,
                QtGui.QBrush(
                    QtGui.QColor(
                        COLORS["muted"]
                    )
                ),
            )
            self.members_tree.addTopLevelItem(item)

    def clear_details(self):
        self._loaded_id = ""
        self._loaded_name = ""
        self.name_value.setText("—")
        self.description_value.setText("—")
        self.members_tree.clear()
        self.member_count.setText("0")

        item = QtWidgets.QTreeWidgetItem([
            "No pools available",
            "—",
            "—",
            "—",
        ])
        item.setForeground(
            0,
            QtGui.QBrush(
                QtGui.QColor(
                    COLORS["muted"]
                )
            ),
        )
        self.members_tree.addTopLevelItem(item)

    def load_selected_pool(
        self,
        current,
        previous=None,
    ):
        if current is None:
            self.clear_details()
            return

        pool_id = str(
            current.data(QtCore.Qt.UserRole)
            or ""
        )
        pool = self.pool_by_id(pool_id) or {}

        self._loaded_id = pool_id
        self._loaded_name = str(
            pool.get("name") or current.text()
        )

        self.name_value.setText(
            self._loaded_name or "—"
        )
        self.description_value.setText(
            str(
                pool.get("description")
                or "No description."
            )
        )
        self.refresh_members()

    def reload_data(self):
        selected_id = self._loaded_id

        try:
            QtWidgets.QApplication.setOverrideCursor(
                QtCore.Qt.WaitCursor
            )

            provider = getattr(
                self.api,
                "get_worker_targeting_snapshot",
                None,
            )

            if callable(provider):
                payload = provider() or {}
                self._workers = list(
                    payload.get("workers") or []
                )
                self._pools = list(
                    payload.get("pools") or []
                )
            else:
                pool_provider = getattr(
                    self.api,
                    "get_api_pools",
                    None,
                )
                worker_provider = getattr(
                    self.api,
                    "get_available_workers",
                    None,
                )

                if callable(pool_provider):
                    self._pools = list(
                        pool_provider() or []
                    )

                if callable(worker_provider):
                    self._workers = list(
                        worker_provider() or []
                    )

        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "RenderHive Pools",
                "Could not refresh worker pools:\n\n{}".format(
                    error
                ),
            )
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.refresh_pool_list(
            select_id=selected_id
        )

    def use_selected_pool(self):
        if not self._loaded_id or not self._loaded_name:
            QtWidgets.QMessageBox.information(
                self,
                "RenderHive Pools",
                "Select a pool first.",
            )
            return

        self.accept()


class WorkerSyncThread(QtCore.QThread):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, provider, parent=None):
        super(WorkerSyncThread, self).__init__(parent)
        self.provider = provider

    def run(self):
        try:
            self.succeeded.emit(self.provider())
        except Exception as error:
            self.failed.emit(str(error))


class LabeledField(QtWidgets.QWidget):
    def __init__(self, label, widget, parent=None):
        super(LabeledField, self).__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        title = QtWidgets.QLabel(label)
        title.setObjectName("FieldLabel")
        layout.addWidget(title)
        layout.addWidget(widget)


class Card(QtWidgets.QFrame):
    def __init__(self, title, subtitle="", parent=None):
        super(Card, self).__init__(parent)
        self.setObjectName("Card")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(11, 10, 11, 11)
        self.layout.setSpacing(7)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("SectionTitle")
        header.addWidget(title_label)
        header.addStretch()

        self.layout.addLayout(header)

        if subtitle:
            subtitle_label = QtWidgets.QLabel(subtitle)
            subtitle_label.setObjectName("MutedText")
            subtitle_label.setWordWrap(True)
            self.layout.addWidget(subtitle_label)


class PageHeader(QtWidgets.QWidget):
    def __init__(self, title, subtitle, parent=None):
        super(PageHeader, self).__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 2)
        layout.setSpacing(2)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)

        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setObjectName("MutedText")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)



# -----------------------------------------------------------------------------
# Task review dialog
# -----------------------------------------------------------------------------




# -----------------------------------------------------------------------------
# Main window
# -----------------------------------------------------------------------------


class RenderHiveSubmitter(QtWidgets.QDialog):
    def __init__(self, api, parent=None):
        super(RenderHiveSubmitter, self).__init__(parent or maya_main_window())
        self.api = api
        self.settings = QtCore.QSettings("RenderHive", "MayaSubmitter")
        self.state_store = StateStore()
        self._state_migration_report = self.state_store.migrate_from_qsettings(
            self.settings
        )
        self.nav_buttons = []
        self.page_stack = None
        self.available_workers = []
        self.worker_sync_thread = None
        self.worker_target_last_sync = None
        self.worker_target_has_sync = False
        self.worker_target_sync_error = ""
        self.api_test_thread = None
        self.api_submit_thread = None
        self.worker_pools = self.load_worker_pools()
        self.api_pools = []
        self.pool_records = {}
        self.using_api_pools = False
        self._pending_pool_scene_name = ""

        # Per-Maya-scene submitter state. The values are stored outside the
        # .ma/.mb file so saving submitter choices never dirties the scene.
        self._scene_state_restoring = False
        self._active_scene_state_key = ""
        self._active_scene_identity = ""
        self._last_scene_state_payload = ""
        self._pending_scene_state = None
        self._pending_scene_state_payload = ""
        self._pending_worker_scene_state = {}

        # Fast timer: detects scene switches and value changes only.
        # It never writes directly to disk.
        self.scene_state_timer = QtCore.QTimer(self)
        self.scene_state_timer.setInterval(500)
        self.scene_state_timer.timeout.connect(
            self.monitor_scene_state
        )

        # Single-shot debounce: one SQLite write after the user stops
        # changing fields, instead of polling writes every 750 ms.
        self.scene_state_save_timer = QtCore.QTimer(self)
        self.scene_state_save_timer.setSingleShot(True)
        self.scene_state_save_timer.setInterval(1500)
        self.scene_state_save_timer.timeout.connect(
            self.flush_scene_state
        )

        self.worker_stale_timer = QtCore.QTimer(self)
        self.worker_stale_timer.setInterval(30000)
        self.worker_stale_timer.timeout.connect(
            self.update_worker_sync_chips
        )

        self.setObjectName("RenderHiveWindow")
        self.setWindowTitle("RenderHive")
        self.setMinimumSize(680, 600)
        self.resize(720, 690)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(build_stylesheet())

        self.build_ui()
        self.load_api_settings()
        self.restore_ui_state()
        self.initialize_scene_state()
        self.report_state_storage_ready()
        self.scene_state_timer.start()
        self.worker_stale_timer.start()
        QtCore.QTimer.singleShot(0, self.sync_available_workers)

    def closeEvent(self, event):
        global _WINDOW

        self.settings.setValue("geometry_v08", self.saveGeometry())
        if self.page_stack is not None:
            self.settings.setValue("page_v08", self.page_stack.currentIndex())

        resources = _WIDGETS.get("resource_requirements_section")
        if isinstance(resources, CollapsibleSection):
            self.settings.setValue(
                "worker_resources_expanded_v193",
                resources.isExpanded(),
            )

        self.scene_state_timer.stop()
        self.scene_state_save_timer.stop()
        self.worker_stale_timer.stop()
        self.save_scene_state(force=True)
        self.save_worker_pools()

        _WINDOW = None
        super(RenderHiveSubmitter, self).closeEvent(event)

    def restore_ui_state(self):
        geometry = self.settings.value("geometry_v08")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass

        page_index = int(self.settings.value("page_v08", 0))
        if self.page_stack is not None:
            page_index = max(0, min(page_index, self.page_stack.count() - 1))
            self.select_page(page_index)

        resources = _WIDGETS.get("resource_requirements_section")
        if isinstance(resources, CollapsibleSection):
            saved = self.settings.value(
                "worker_resources_expanded_v193",
                False,
            )
            expanded = saved in (
                True,
                1,
                "1",
                "true",
                "True",
            )
            resources.setExpanded(expanded)

    def scene_identity_and_key(self):
        scene_path = cmds.file(
            query=True,
            sceneName=True,
        ) or ""

        if scene_path:
            identity = os.path.normcase(
                os.path.abspath(scene_path)
            ).replace("\\", "/")
        else:
            # There can only be one active untitled scene in a Maya session.
            identity = "__untitled_scene__"

        digest = hashlib.sha1(
            identity.encode("utf-8")
        ).hexdigest()

        return (
            identity,
            "scene_submitter_state_v174_{}".format(digest),
        )

    def scene_state_field_names(self):
        return {
            "text": (
                "rh_project_name",
                "rh_job_name",
                "rh_department",
                "rh_comment",
                "rh_job_dependencies",
                "rh_scene_path",
                "rh_project_path",
                "rh_output_path",
                "rh_image_name",
            ),
            "integer": (
                "rh_priority",
                "rh_chunk_size",
                "rh_machine_limit",
                "rh_concurrent_tasks",
                "rh_min_ram_gb",
                "rh_min_vram_gb",
                "rh_retry_count",
                "rh_timeout_minutes",
                "rh_frame_start",
                "rh_frame_end",
                "rh_frame_step",
                "rh_frame_padding",
                "rh_width",
                "rh_height",
            ),
            "boolean": (
                "rh_start_suspended",
            ),
            "option": (
                "rh_pool",
                "rh_worker_assignment_mode",
                "rh_submission_mode",
                "rh_renderer",
                "rh_camera",
                "rh_image_format",
                "render_preset",
            ),
            "list": (
                "rh_allowed_workers",
                "rh_denied_workers",
            ),
        }

    def capture_scene_state(self):
        fields = self.scene_state_field_names()
        state = {
            "scene_identity": self._active_scene_identity,
            "text": {},
            "integer": {},
            "boolean": {},
            "option": {},
            "list": {},
        }

        for name in fields["text"]:
            widget = _WIDGETS.get(name)
            if isinstance(widget, QtWidgets.QLineEdit):
                state["text"][name] = widget.text()

        for name in fields["integer"]:
            widget = _WIDGETS.get(name)
            if isinstance(widget, QtWidgets.QSpinBox):
                state["integer"][name] = int(widget.value())

        for name in fields["boolean"]:
            widget = _WIDGETS.get(name)
            if isinstance(widget, QtWidgets.QCheckBox):
                state["boolean"][name] = bool(widget.isChecked())

        for name in fields["option"]:
            widget = _WIDGETS.get(name)
            if isinstance(widget, QtWidgets.QComboBox):
                state["option"][name] = widget.currentText()
            elif hasattr(widget, "currentText"):
                try:
                    state["option"][name] = widget.currentText()
                except Exception:
                    pass

        for name in fields["list"]:
            state["list"][name] = qt_get_list(name, [])

        return state

    def load_scene_state(self, key):
        return self.state_store.load_scene_state(key)

    def apply_scene_state(self, state):
        if not isinstance(state, dict):
            return False

        self._scene_state_restoring = True

        try:
            for name, value in (state.get("text") or {}).items():
                widget = _WIDGETS.get(name)
                if isinstance(widget, QtWidgets.QLineEdit):
                    widget.setText(str(value or ""))

            for name, value in (state.get("integer") or {}).items():
                widget = _WIDGETS.get(name)
                if isinstance(widget, QtWidgets.QSpinBox):
                    try:
                        widget.setValue(int(value))
                    except Exception:
                        pass

            for name, value in (state.get("boolean") or {}).items():
                widget = _WIDGETS.get(name)
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))

            options = state.get("option") or {}

            # Pool membership controls which workers are available in the
            # Allowed and Denied selectors, so restore it before those lists.
            saved_pool = str(options.get("rh_pool") or "All Workers")
            self._pending_pool_scene_name = saved_pool
            self.refresh_pool_combo(preferred=saved_pool)

            for name, value in options.items():
                if name == "rh_pool":
                    continue

                widget = _WIDGETS.get(name)

                value = str(value or "")

                if isinstance(widget, QtWidgets.QComboBox):
                    index = widget.findText(value)

                    if index >= 0:
                        widget.setCurrentIndex(index)
                    elif widget.isEditable() and value:
                        widget.setEditText(value)

                elif hasattr(widget, "setCurrentText"):
                    try:
                        widget.setCurrentText(value)
                    except Exception:
                        pass

            lists = state.get("list") or {}
            self._pending_worker_scene_state = {
                "rh_allowed_workers": list(
                    lists.get("rh_allowed_workers") or []
                ),
                "rh_denied_workers": list(
                    lists.get("rh_denied_workers") or []
                ),
            }
            self.apply_pending_worker_scene_state()

            assignment_widget = _WIDGETS.get(
                "rh_worker_assignment_mode"
            )
            saved_assignment = str(
                options.get("rh_worker_assignment_mode") or ""
            )

            # v1.9.1 scenes did not store an explicit strategy. Preserve the
            # user's intent by inferring Selected Only when an Allowed list
            # already exists; otherwise default to all pool members.
            if (
                assignment_widget is not None
                and hasattr(assignment_widget, "setCurrentText")
                and not saved_assignment
            ):
                inferred = (
                    "Use Selected Workers Only"
                    if lists.get("rh_allowed_workers")
                    else "Use All Workers in Pool"
                )
                assignment_widget.setCurrentText(inferred)

            self.on_worker_assignment_mode_changed(
                self.worker_assignment_mode()
            )

            return True

        finally:
            self._scene_state_restoring = False

    def apply_pending_worker_scene_state(self):
        if not self._pending_worker_scene_state:
            return

        for name in (
            "rh_allowed_workers",
            "rh_denied_workers",
        ):
            if name in self._pending_worker_scene_state:
                qt_set_list(
                    name,
                    self._pending_worker_scene_state.get(name) or [],
                )

    @staticmethod
    def serialize_scene_state(state):
        return json.dumps(
            state,
            sort_keys=True,
            separators=(",", ":"),
        )

    def schedule_scene_state_save(self):
        if self._scene_state_restoring:
            return False

        if not self._active_scene_state_key:
            return False

        state = self.capture_scene_state()
        payload = self.serialize_scene_state(state)

        if payload == self._last_scene_state_payload:
            self._pending_scene_state = None
            self._pending_scene_state_payload = ""
            self.scene_state_save_timer.stop()
            return False

        # Restart the debounce only when the actual UI payload changed.
        # Repeated monitor ticks with identical values do not delay the save.
        if payload != self._pending_scene_state_payload:
            self._pending_scene_state = state
            self._pending_scene_state_payload = payload
            self.scene_state_save_timer.start()

        return True

    def flush_scene_state(self, force=False):
        if self._scene_state_restoring:
            return False

        if not self._active_scene_state_key:
            return False

        if force or self._pending_scene_state is None:
            state = self.capture_scene_state()
            payload = self.serialize_scene_state(state)
        else:
            state = self._pending_scene_state
            payload = self._pending_scene_state_payload

        if not force and payload == self._last_scene_state_payload:
            self._pending_scene_state = None
            self._pending_scene_state_payload = ""
            return False

        self.state_store.save_scene_state(
            self._active_scene_state_key,
            self._active_scene_identity,
            state,
        )

        self.scene_state_save_timer.stop()
        self._last_scene_state_payload = payload
        self._pending_scene_state = None
        self._pending_scene_state_payload = ""
        return True

    def save_scene_state(self, force=False):
        if force:
            return self.flush_scene_state(force=True)

        return self.schedule_scene_state_save()

    def initialize_scene_state(self):
        identity, key = self.scene_identity_and_key()
        self._active_scene_identity = identity
        self._active_scene_state_key = key
        self._last_scene_state_payload = ""
        self._pending_scene_state = None
        self._pending_scene_state_payload = ""

        # Populate camera, renderer, output and frame information from Maya
        # first, then overlay any saved choices for this exact scene. Suppress
        # persistence during the initial sync so an existing saved state is
        # never overwritten by scene defaults before it is restored.
        self._scene_state_restoring = True
        try:
            self.sync_from_scene(record_activity=False)
        finally:
            self._scene_state_restoring = False

        state = self.load_scene_state(key)

        if state:
            self.apply_scene_state(state)
            self._last_scene_state_payload = self.serialize_scene_state(
                self.capture_scene_state()
            )
            self.append_activity(
                "Restored submitter settings from SQLite for this Maya scene."
            )
        else:
            self.save_scene_state(force=True)
            self.append_activity(
                "Created SQLite submitter settings for this Maya scene."
            )

    def monitor_scene_state(self):
        if self._scene_state_restoring:
            return

        identity, key = self.scene_identity_and_key()

        if key != self._active_scene_state_key:
            # The UI still contains the previous scene values at this point.
            # Flush them under the old key before switching identities.
            self.save_scene_state(force=True)

            self._active_scene_identity = identity
            self._active_scene_state_key = key
            self._last_scene_state_payload = ""
            self._pending_scene_state = None
            self._pending_scene_state_payload = ""
            self._pending_worker_scene_state = {}
            self._pending_pool_scene_name = ""
            self.scene_state_save_timer.stop()

            self._scene_state_restoring = True
            try:
                self.sync_from_scene(record_activity=False)
            finally:
                self._scene_state_restoring = False

            state = self.load_scene_state(key)

            if state:
                self.apply_scene_state(state)
                self._last_scene_state_payload = self.serialize_scene_state(
                    self.capture_scene_state()
                )
                self.set_status(
                    "Restored settings for the opened Maya scene.",
                    level="success",
                )
                self.append_activity(
                    "Scene changed: SQLite submitter settings restored."
                )
            else:
                self.save_scene_state(force=True)
                self.set_status(
                    "Loaded defaults for the opened Maya scene.",
                    level="info",
                )
                self.append_activity(
                    "Scene changed: new SQLite submitter settings created."
                )

            return

        self.schedule_scene_state_save()

    def report_state_storage_ready(self):
        report = self._state_migration_report or {}
        migrated_scenes = int(report.get("scene_states", 0))
        migrated_settings = int(report.get("app_settings", 0))

        if migrated_scenes or migrated_settings:
            self.append_activity(
                "Migrated {} scene state(s) and {} local setting(s) "
                "from QSettings to SQLite.".format(
                    migrated_scenes,
                    migrated_settings,
                )
            )
        else:
            self.append_activity(
                "SQLite restore storage ready: {}".format(
                    self.state_store.database_path
                )
            )

    def open_state_storage_folder(self):
        try:
            folder = os.path.dirname(self.state_store.database_path)

            if hasattr(os, "startfile"):
                os.startfile(folder)
            else:
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(folder)
                )

            self.append_activity(
                "Opened SQLite state folder: {}".format(folder)
            )
        except Exception as error:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive State Storage",
                "Could not open the state folder:\n\n{}".format(error),
            )

    def build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        root.addWidget(self.build_header())

        center = QtWidgets.QHBoxLayout()
        center.setSpacing(7)
        center.addWidget(self.build_sidebar())

        self.page_stack = QtWidgets.QStackedWidget()
        self.page_stack.addWidget(self.build_job_page())
        self.page_stack.addWidget(self.build_render_page())
        self.page_stack.addWidget(self.build_checks_page())
        self.page_stack.addWidget(self.build_more_page())
        center.addWidget(self.page_stack, 1)

        root.addLayout(center, 1)
        root.addWidget(self.build_footer())

    def build_header(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("HeaderCard")

        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(7)

        logo = QtWidgets.QLabel()
        logo.setObjectName("HeaderLogo")
        logo.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        logo.setStyleSheet("background: transparent; border: none;")
        logo.setFixedSize(48, 48)
        pixmap = QtGui.QPixmap(icon_path("renderhive_header_logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    48,
                    48,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        layout.addWidget(logo)

        brand_column = QtWidgets.QVBoxLayout()
        brand_column.setSpacing(0)

        brand_row = QtWidgets.QHBoxLayout()
        brand_row.setSpacing(0)

        render_label = QtWidgets.QLabel("RENDER")
        render_label.setObjectName("BrandMain")
        hive_label = QtWidgets.QLabel("HIVE")
        hive_label.setObjectName("BrandAccent")

        brand_row.addWidget(render_label)
        brand_row.addWidget(hive_label)
        brand_row.addStretch()
        brand_column.addLayout(brand_row)

        subtitle = QtWidgets.QLabel("MAYA RENDER MANAGEMENT")
        subtitle.setObjectName("BrandSubtitle")
        brand_column.addWidget(subtitle)

        scene_label = register("header_scene", QtWidgets.QLabel("Scene: —"))
        scene_label.setObjectName("MutedText")
        brand_column.addWidget(scene_label)

        layout.addLayout(brand_column, 1)

        meta_column = QtWidgets.QVBoxLayout()
        meta_column.setSpacing(5)
        meta_column.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        version = QtWidgets.QLabel("UI v{}".format(UI_VERSION))
        version.setObjectName("MetaChip")
        version.setAlignment(QtCore.Qt.AlignCenter)
        meta_column.addWidget(version, 0, QtCore.Qt.AlignRight)

        renderer_chip = register("header_renderer", QtWidgets.QLabel("Renderer: —"))
        renderer_chip.setObjectName("MetaChip")
        renderer_chip.setAlignment(QtCore.Qt.AlignCenter)
        meta_column.addWidget(renderer_chip, 0, QtCore.Qt.AlignRight)

        layout.addLayout(meta_column)
        return frame

    def build_sidebar(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Sidebar")
        frame.setFixedWidth(92)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        button_group = QtWidgets.QButtonGroup(self)
        button_group.setExclusive(True)

        pages = [
            ("Job", "Job setup"),
            ("Render", "Render settings"),
            ("Checks", "Scene validation"),
            ("Tools", "Activity and maintenance"),
        ]

        for index, (title, tooltip) in enumerate(pages):
            button = QtWidgets.QPushButton(title)
            button.setToolTip(tooltip)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page=index: self.select_page(page)
            )
            button_group.addButton(button)
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch()

        maya_chip = QtWidgets.QLabel("Maya {}".format(cmds.about(version=True)))
        maya_chip.setObjectName("MetaChip")
        maya_chip.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(maya_chip)

        return frame

    def select_page(self, index):
        if self.page_stack is not None:
            self.page_stack.setCurrentIndex(index)

        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def scroll_page(self, title, subtitle):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(0, 1, 4, 1)
        layout.setSpacing(7)
        layout.addWidget(PageHeader(title, subtitle))

        scroll.setWidget(content)
        return scroll, layout

    # ------------------------------------------------------------------
    # Job page
    # ------------------------------------------------------------------

    def build_job_page(self):
        page, body = self.scroll_page(
            "Job Setup",
            "Control scheduling, worker targeting and packaging before the task reaches the farm.",
        )

        identity = Card("Identity", "Core information used by the queue and reports.")
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        project = register("rh_project_name", QtWidgets.QLineEdit())
        project.setPlaceholderText("Project name")
        job = register("rh_job_name", QtWidgets.QLineEdit())
        job.setPlaceholderText("Job name")
        priority = register("rh_priority", QtWidgets.QSpinBox())
        priority.setRange(1, 100)
        priority.setValue(50)
        department = register("rh_department", QtWidgets.QLineEdit())
        department.setPlaceholderText("Lighting, FX, LookDev…")
        comment = register("rh_comment", QtWidgets.QLineEdit())
        comment.setPlaceholderText("Optional note for the farm operator")

        grid.addWidget(LabeledField("Project", project), 0, 0)
        grid.addWidget(LabeledField("Job", job), 0, 1)
        grid.addWidget(LabeledField("Priority", priority), 1, 0)
        grid.addWidget(LabeledField("Department", department), 1, 1)
        grid.addWidget(LabeledField("Comment", comment), 2, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        identity.layout.addLayout(grid)
        body.addWidget(identity)

        scheduling = Card(
            "Scheduling & Distribution",
            "These values are submitted to the RenderHive scheduler.",
        )
        schedule_grid = QtWidgets.QGridLayout()
        schedule_grid.setHorizontalSpacing(10)
        schedule_grid.setVerticalSpacing(8)

        chunk_size = register("rh_chunk_size", QtWidgets.QSpinBox())
        chunk_size.setRange(1, 10000)
        chunk_size.setValue(1)
        chunk_size.setToolTip("Number of frames assigned to each farm task. Note: Chunking > 1 is not fully supported in the MVP yet.")

        machine_limit = register("rh_machine_limit", QtWidgets.QSpinBox())
        machine_limit.setRange(0, 10000)
        machine_limit.setValue(0)
        machine_limit.setSpecialValueText("Unlimited")

        concurrent = register("rh_concurrent_tasks", QtWidgets.QSpinBox())
        concurrent.setRange(1, 64)
        concurrent.setValue(1)

        start_suspended = register("rh_start_suspended", QtWidgets.QCheckBox("Start job suspended"))
        start_suspended.setToolTip("The RenderHive API can queue this job without starting it immediately.")

        schedule_grid.addWidget(LabeledField("Chunk Size", chunk_size), 0, 0)
        schedule_grid.addWidget(LabeledField("Machine Limit", machine_limit), 0, 1)
        schedule_grid.addWidget(LabeledField("Concurrent Tasks / Worker", concurrent), 1, 0)
        schedule_grid.addWidget(start_suspended, 1, 1)
        schedule_grid.setColumnStretch(0, 1)
        schedule_grid.setColumnStretch(1, 1)
        scheduling.layout.addLayout(schedule_grid)
        body.addWidget(scheduling)

        targeting = Card(
            "Worker Targeting",
            "Select a pool, then choose how this job can use its workers.",
        )

        worker_status_row = QtWidgets.QHBoxLayout()
        worker_status_row.setSpacing(6)

        api_chip = register(
            "worker_api_chip",
            WorkerStatusChip("Not Synced"),
        )
        worker_chip = register(
            "worker_count_chip",
            WorkerStatusChip("0 Workers"),
        )
        pool_chip = register(
            "worker_pool_count_chip",
            WorkerStatusChip("0 Pools"),
        )
        sync_chip = register(
            "worker_sync_time_chip",
            WorkerStatusChip("Never"),
        )

        sync_workers = register(
            "sync_workers_button",
            QtWidgets.QPushButton("Refresh"),
        )
        sync_workers.setObjectName("InfoButton")
        sync_workers.setToolTip(
            "Refresh workers and pools from RenderHive."
        )
        sync_workers.clicked.connect(
            self.sync_available_workers
        )

        worker_status_row.addWidget(api_chip)
        worker_status_row.addWidget(worker_chip)
        worker_status_row.addWidget(pool_chip)
        worker_status_row.addWidget(sync_chip)
        worker_status_row.addStretch()
        worker_status_row.addWidget(sync_workers)
        targeting.layout.addLayout(worker_status_row)

        target_grid = QtWidgets.QGridLayout()
        target_grid.setHorizontalSpacing(10)
        target_grid.setVerticalSpacing(8)

        pool_row = QtWidgets.QHBoxLayout()
        pool_row.setSpacing(7)

        pool = register(
            "rh_pool",
            QtWidgets.QComboBox(),
        )
        pool.setToolTip(
            "Choose a worker pool provided by the RenderHive backend."
        )
        pool.currentTextChanged.connect(
            self.on_pool_changed
        )

        browse_pools = QtWidgets.QPushButton("Browse Pools")
        browse_pools.setObjectName("InfoButton")
        browse_pools.setToolTip(
            "Review backend pools and select one for this job."
        )
        browse_pools.clicked.connect(
            self.manage_worker_pools
        )

        pool_row.addWidget(pool, 1)
        pool_row.addWidget(browse_pools)
        pool_widget = QtWidgets.QWidget()
        pool_widget.setLayout(pool_row)

        assignment = register(
            "rh_worker_assignment_mode",
            SegmentedChoice([
                "Use All Workers in Pool",
                "Use Selected Workers Only",
            ]),
        )
        assignment.setToolTip(
            "Use every pool member with optional exclusions, or target only "
            "specific workers."
        )
        assignment.currentTextChanged.connect(
            self.on_worker_assignment_mode_changed
        )

        assignment_hint = register(
            "worker_assignment_hint",
            QtWidgets.QLabel(""),
        )
        assignment_hint.setObjectName("MutedText")
        assignment_hint.setWordWrap(True)

        allowed = register(
            "rh_allowed_workers",
            WorkerMultiSelect(
                "Selected Workers",
                "Select Workers",
            ),
        )
        allowed.setToolTip(
            "Only the selected workers can receive this job."
        )
        allowed.selectionChanged.connect(
            self.on_allowed_workers_changed
        )

        denied = register(
            "rh_denied_workers",
            WorkerMultiSelect(
                "Excluded Workers",
                "None",
            ),
        )
        denied.setToolTip(
            "All pool members can receive this job except the selected workers."
        )
        denied.selectionChanged.connect(
            self.on_denied_workers_changed
        )

        selected_field = register(
            "worker_selected_field",
            LabeledField("Selected Workers", allowed),
        )
        excluded_field = register(
            "worker_excluded_field",
            LabeledField("Excluded Workers", denied),
        )

        target_grid.addWidget(
            LabeledField("Pool", pool_widget),
            0, 0, 1, 2,
        )
        target_grid.addWidget(
            LabeledField("Worker Assignment", assignment),
            1, 0, 1, 2,
        )
        target_grid.addWidget(
            assignment_hint,
            2, 0, 1, 2,
        )
        target_grid.addWidget(
            selected_field,
            3, 0, 1, 2,
        )
        target_grid.addWidget(
            excluded_field,
            4, 0, 1, 2,
        )
        target_grid.setColumnStretch(0, 1)
        target_grid.setColumnStretch(1, 1)
        targeting.layout.addLayout(target_grid)

        eligibility = register(
            "worker_eligibility_summary",
            QtWidgets.QLabel(
                "No worker data has been synchronized yet."
            ),
        )
        eligibility.setObjectName("EligibilitySummary")
        eligibility.setWordWrap(True)
        targeting.layout.addWidget(eligibility)

        resources = register(
            "resource_requirements_section",
            CollapsibleSection(
                "Advanced Resource Requirements"
            ),
        )

        resource_hint = QtWidgets.QLabel(
            "Optional minimum hardware requirements for eligible workers."
        )
        resource_hint.setObjectName("MutedText")
        resource_hint.setWordWrap(True)
        resources.content_layout.addWidget(resource_hint)

        resource_grid = QtWidgets.QGridLayout()
        resource_grid.setHorizontalSpacing(10)
        resource_grid.setVerticalSpacing(8)

        min_ram = register("rh_min_ram_gb", QtWidgets.QSpinBox())
        min_ram.setRange(0, 2048)
        min_ram.setSpecialValueText("Any")
        min_ram.setSuffix(" GB")
        min_ram.valueChanged.connect(
            self.update_worker_targeting_summary
        )

        min_vram = register("rh_min_vram_gb", QtWidgets.QSpinBox())
        min_vram.setRange(0, 256)
        min_vram.setSpecialValueText("Any")
        min_vram.setSuffix(" GB")
        min_vram.valueChanged.connect(
            self.update_worker_targeting_summary
        )

        resource_grid.addWidget(
            LabeledField("Minimum RAM", min_ram),
            0, 0,
        )
        resource_grid.addWidget(
            LabeledField("Minimum VRAM", min_vram),
            0, 1,
        )
        resource_grid.setColumnStretch(0, 1)
        resource_grid.setColumnStretch(1, 1)
        resources.content_layout.addLayout(resource_grid)
        targeting.layout.addWidget(resources)

        self.update_worker_assignment_ui()
        self.update_worker_targeting_summary()
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()
        body.addWidget(targeting)

        delivery = Card("Submission & Failure Handling")
        delivery_grid = QtWidgets.QGridLayout()
        delivery_grid.setHorizontalSpacing(10)
        delivery_grid.setVerticalSpacing(8)

        submission_mode = register("rh_submission_mode", QtWidgets.QComboBox())
        submission_mode.addItems(["Shared Storage", "Smart Package", "Full Package"])

        retry_count = register("rh_retry_count", QtWidgets.QSpinBox())
        retry_count.setRange(0, 20)
        retry_count.setValue(2)

        timeout = register("rh_timeout_minutes", QtWidgets.QSpinBox())
        timeout.setRange(0, 100000)
        timeout.setSpecialValueText("No Timeout")
        timeout.setSuffix(" min")

        dependencies = register("rh_job_dependencies", QtWidgets.QLineEdit())
        dependencies.setPlaceholderText("Job IDs separated by commas")

        delivery_grid.addWidget(LabeledField("Submission Mode", submission_mode), 0, 0)
        delivery_grid.addWidget(LabeledField("Retry Count", retry_count), 0, 1)
        delivery_grid.addWidget(LabeledField("Task Timeout", timeout), 1, 0)
        delivery_grid.addWidget(LabeledField("Job Dependencies", dependencies), 1, 1)
        delivery_grid.setColumnStretch(0, 1)
        delivery_grid.setColumnStretch(1, 1)
        delivery.layout.addLayout(delivery_grid)
        body.addWidget(delivery)

        paths = Card("Paths", "Portable paths keep the job usable on other workers.")

        scene_path = register("rh_scene_path", QtWidgets.QLineEdit())
        project_path = register("rh_project_path", QtWidgets.QLineEdit())
        output_path = register("rh_output_path", QtWidgets.QLineEdit())

        for widget in (scene_path, project_path, output_path):
            widget.setClearButtonEnabled(True)

        paths.layout.addWidget(LabeledField("Scene", scene_path))
        paths.layout.addWidget(LabeledField("Project Root", project_path))

        output_row = QtWidgets.QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(7)
        output_row.addWidget(output_path, 1)

        browse = QtWidgets.QPushButton("Browse")
        browse.clicked.connect(self.api.browse_output_path)
        output_row.addWidget(browse)

        output_widget = QtWidgets.QWidget()
        output_widget.setLayout(output_row)
        paths.layout.addWidget(LabeledField("Output", output_widget))

        utility_row = QtWidgets.QHBoxLayout()
        utility_row.setSpacing(7)

        open_output = QtWidgets.QPushButton("Open Output")
        open_output.setObjectName("GhostButton")
        open_output.clicked.connect(
            self.api.open_output_folder
        )

        sync_scene = QtWidgets.QPushButton("Sync From Scene")
        sync_scene.setObjectName("InfoButton")
        sync_scene.setToolTip(
            "Refresh scene, project, output, frame range, camera and renderer values."
        )
        sync_scene.clicked.connect(self.sync_from_scene)

        utility_row.addWidget(open_output)
        utility_row.addStretch()
        utility_row.addWidget(sync_scene)
        paths.layout.addLayout(utility_row)

        body.addWidget(paths)
        body.addStretch()
        return page

    # ------------------------------------------------------------------
    # Render page
    # ------------------------------------------------------------------

    def build_render_page(self):
        page, body = self.scroll_page(
            "Render Settings",
            "Choose the frame range, renderer, camera and final output settings.",
        )

        preset_card = Card("Quick Preset", "Apply a safe starting point, then fine-tune below.")
        preset_row = QtWidgets.QHBoxLayout()

        preset = register("render_preset", QtWidgets.QComboBox())
        preset.addItems(
            [
                "Custom",
                "Preview",
                "HD",
                "Full HD",
                "Production EXR",
            ]
        )

        apply_button = QtWidgets.QPushButton("Apply Preset")
        apply_button.setObjectName("PrimaryButton")
        apply_button.clicked.connect(self.apply_preset)

        preset_row.addWidget(preset, 1)
        preset_row.addWidget(apply_button)
        preset_card.layout.addLayout(preset_row)
        body.addWidget(preset_card)

        render_card = Card("Frames & Renderer")
        render_grid = QtWidgets.QGridLayout()
        render_grid.setHorizontalSpacing(10)
        render_grid.setVerticalSpacing(8)

        frame_start = register("rh_frame_start", QtWidgets.QSpinBox())
        frame_end = register("rh_frame_end", QtWidgets.QSpinBox())
        frame_step = register("rh_frame_step", QtWidgets.QSpinBox())
        for widget in (frame_start, frame_end):
            widget.setRange(-1000000, 1000000)
        frame_step.setRange(1, 1000)
        frame_step.setValue(1)

        renderer = register("rh_renderer", QtWidgets.QComboBox())
        renderer.addItems(["arnold", "sw", "mayaHardware2"])

        camera = register("rh_camera", QtWidgets.QComboBox())
        camera.addItem("Loading")

        render_grid.addWidget(LabeledField("Frame Start", frame_start), 0, 0)
        render_grid.addWidget(LabeledField("Frame End", frame_end), 0, 1)
        render_grid.addWidget(LabeledField("Frame Step", frame_step), 1, 0)
        render_grid.addWidget(LabeledField("Renderer", renderer), 1, 1)
        render_grid.addWidget(LabeledField("Camera", camera), 2, 0, 1, 2)
        render_grid.setColumnStretch(0, 1)
        render_grid.setColumnStretch(1, 1)
        render_card.layout.addLayout(render_grid)
        body.addWidget(render_card)

        output_card = Card("Output")
        output_grid = QtWidgets.QGridLayout()
        output_grid.setHorizontalSpacing(10)
        output_grid.setVerticalSpacing(8)

        image_name = register("rh_image_name", QtWidgets.QLineEdit())
        image_name.setPlaceholderText("Output image prefix")

        image_format = register("rh_image_format", QtWidgets.QComboBox())
        image_format.addItems(["png", "jpg", "exr", "tif"])

        padding = register("rh_frame_padding", QtWidgets.QSpinBox())
        padding.setRange(1, 12)
        padding.setValue(4)

        width = register("rh_width", QtWidgets.QSpinBox())
        height = register("rh_height", QtWidgets.QSpinBox())
        for widget in (width, height):
            widget.setRange(1, 65536)

        output_grid.addWidget(LabeledField("Image Name", image_name), 0, 0, 1, 2)
        output_grid.addWidget(LabeledField("Format", image_format), 1, 0)
        output_grid.addWidget(LabeledField("Padding", padding), 1, 1)
        output_grid.addWidget(LabeledField("Width", width), 2, 0)
        output_grid.addWidget(LabeledField("Height", height), 2, 1)
        output_grid.setColumnStretch(0, 1)
        output_grid.setColumnStretch(1, 1)
        output_card.layout.addLayout(output_grid)
        body.addWidget(output_card)

        body.addStretch()
        return page

    # ------------------------------------------------------------------
    # Validation page
    # ------------------------------------------------------------------

    def build_checks_page(self):
        page = QtWidgets.QWidget()
        body = QtWidgets.QVBoxLayout(page)
        body.setContentsMargins(2, 2, 5, 2)
        body.setSpacing(9)

        body.addWidget(
            PageHeader(
                "Scene Validation",
                "Errors block submission. Warnings remain visible without stopping the job.",
            )
        )

        counters = QtWidgets.QHBoxLayout()
        counters.setSpacing(6)

        counter_specs = [
            ("counter_error", "ERROR", "ERROR"),
            ("counter_warning", "WARNING", "WARNING"),
            ("counter_info", "INFO", "INFO"),
            ("counter_passed", "PASSED", "PASSED"),
            ("counter_total", "TOTAL", "All"),
        ]

        for name, title, filter_value in counter_specs:
            button = register(name, QtWidgets.QPushButton("{}\n0".format(title)))
            button.setObjectName("CounterCard")
            button.clicked.connect(
                lambda checked=False, value=filter_value: self.set_severity_filter(value)
            )
            counters.addWidget(button, 1)

        body.addLayout(counters)

        filter_card = Card("Filter Results")
        filter_row = QtWidgets.QHBoxLayout()

        severity = register("severity_filter", QtWidgets.QComboBox())
        severity.addItems(["All", "ERROR", "WARNING", "INFO", "PASSED"])

        category = register("category_filter", QtWidgets.QComboBox())
        category.addItem("All")

        severity.currentIndexChanged.connect(refresh_validation_filters)
        category.currentIndexChanged.connect(refresh_validation_filters)

        filter_row.addWidget(LabeledField("Severity", severity), 1)
        filter_row.addWidget(LabeledField("Category", category), 1)
        filter_card.layout.addLayout(filter_row)
        body.addWidget(filter_card)

        results_card = Card("Results")
        tree = register("validation_tree", QtWidgets.QTreeWidget())
        tree.setColumnCount(4)
        tree.setHeaderLabels(["Status", "Category", "Message", "Node"])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        tree.setUniformRowHeights(True)
        tree.setMinimumHeight(205)
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        tree.header().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        tree.itemSelectionChanged.connect(self.show_validation_details)
        tree.itemDoubleClicked.connect(lambda *_: self.api.select_validation_node())
        results_card.layout.addWidget(tree)
        body.addWidget(results_card, 1)

        details = register("validation_details_card", QtWidgets.QFrame())
        details.setObjectName("DetailsCard")
        details_layout = QtWidgets.QVBoxLayout(details)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_layout.setSpacing(4)

        details_top = QtWidgets.QHBoxLayout()
        details_title = QtWidgets.QLabel("Selected Result")
        details_title.setObjectName("SectionTitle")
        details_top.addWidget(details_title)
        details_top.addStretch()

        details_badge = register("details_badge", QtWidgets.QLabel("NONE"))
        details_badge.setObjectName("MetaChip")
        details_top.addWidget(details_badge)
        details_layout.addLayout(details_top)

        details_message = register("details_message", QtWidgets.QLabel("Select a validation result to inspect it."))
        details_message.setObjectName("SecondaryText")
        details_message.setWordWrap(True)
        details_layout.addWidget(details_message)

        details_meta = register("details_meta", QtWidgets.QLabel(""))
        details_meta.setObjectName("MutedText")
        details_meta.setWordWrap(True)
        details_layout.addWidget(details_meta)
        body.addWidget(details)
        details.setVisible(False)

        fix_row = QtWidgets.QHBoxLayout()
        fix_row.setSpacing(7)

        validate = QtWidgets.QPushButton("Validate Scene")
        validate.setObjectName("PrimaryButton")
        validate.setToolTip(
            "Run every installed RenderHive validation check."
        )
        validate.clicked.connect(self.validate_scene)

        fix_selected = register(
            "fix_selected_validation",
            QtWidgets.QPushButton("Fix Selected"),
        )
        fix_selected.setObjectName("InfoButton")
        fix_selected.setToolTip(
            "Apply the registered auto-fix for the selected result."
        )
        fix_selected.clicked.connect(
            self.fix_selected_validation
        )

        fix_all = register(
            "fix_all_safe_validation",
            QtWidgets.QPushButton("Fix All Safe"),
        )
        fix_all.setObjectName("PrimaryButton")
        fix_all.setToolTip(
            "Apply every unique batch-safe auto-fix and validate again."
        )
        fix_all.clicked.connect(
            self.fix_all_safe_validations
        )

        fix_row.addWidget(validate)
        fix_row.addWidget(fix_selected)
        fix_row.addWidget(fix_all)
        body.addLayout(fix_row)

        utility_row = QtWidgets.QHBoxLayout()
        utility_row.setSpacing(7)

        select_node = QtWidgets.QPushButton("Select Node")
        select_node.clicked.connect(
            self.api.select_validation_node
        )

        export = QtWidgets.QPushButton("Export Report")
        export.clicked.connect(
            self.api.export_validation_report
        )

        clear = QtWidgets.QPushButton("Clear")
        clear.setObjectName("GhostButton")
        clear.clicked.connect(
            clear_validation_results
        )

        utility_row.addWidget(select_node)
        utility_row.addWidget(export)
        utility_row.addStretch()
        utility_row.addWidget(clear)
        body.addLayout(utility_row)

        self.update_autofix_actions()

        return page

    def set_severity_filter(self, value):
        combo = _WIDGETS.get("severity_filter")
        if isinstance(combo, QtWidgets.QComboBox):
            index = combo.findText(value)
            combo.setCurrentIndex(index if index >= 0 else 0)


    def show_validation_details(self):
        result = get_selected_validation_result()

        badge = _WIDGETS.get("details_badge")
        message_label = _WIDGETS.get("details_message")
        meta_label = _WIDGETS.get("details_meta")

        if not result:
            self.clear_validation_details()
            return

        details_card = _WIDGETS.get(
            "validation_details_card"
        )
        if isinstance(
            details_card,
            QtWidgets.QWidget
        ):
            details_card.setVisible(True)

        severity = str(
            result.get("severity", "INFO")
        ).upper()
        category = result.get(
            "category",
            "General"
        )
        node = result.get("node", "") or "None"
        message = result.get("message", "")
        auto_fix = result_auto_fix_state(result)

        if auto_fix["fixable"]:
            if auto_fix["batch_safe"]:
                fix_text = "Yes / Batch Safe"
            else:
                fix_text = "Yes / Selected Only"
        else:
            fix_text = "No"

        if isinstance(
            badge,
            QtWidgets.QLabel
        ):
            badge.setText(severity)
            badge.setStyleSheet(
                "QLabel { color:%s; border-color:%s; }"
                % (
                    severity_color(severity),
                    severity_color(severity)
                )
            )

        if isinstance(
            message_label,
            QtWidgets.QLabel
        ):
            message_label.setText(message)

        if isinstance(
            meta_label,
            QtWidgets.QLabel
        ):
            meta_label.setText(
                "Category: {}    Node: {}    Auto-fixable: {}"
                .format(
                    category,
                    node,
                    fix_text,
                )
            )

        self.update_autofix_actions()

    def clear_validation_details(self):
        details_card = _WIDGETS.get("validation_details_card")
        if isinstance(details_card, QtWidgets.QWidget):
            details_card.setVisible(False)

        badge = _WIDGETS.get("details_badge")
        message_label = _WIDGETS.get("details_message")
        meta_label = _WIDGETS.get("details_meta")

        if isinstance(badge, QtWidgets.QLabel):
            badge.setText("NONE")
            badge.setStyleSheet("")

        if isinstance(message_label, QtWidgets.QLabel):
            message_label.setText("Select a validation result to inspect it.")

        if isinstance(meta_label, QtWidgets.QLabel):
            meta_label.setText("")

        self.update_autofix_actions()


    def update_autofix_actions(self):
        selected_button = _WIDGETS.get(
            "fix_selected_validation"
        )
        all_button = _WIDGETS.get(
            "fix_all_safe_validation"
        )

        selected = get_selected_validation_result()
        selected_state = result_auto_fix_state(
            selected
        )

        if isinstance(
            selected_button,
            QtWidgets.QPushButton
        ):
            selected_button.setEnabled(
                bool(selected_state["fixable"])
            )

            if selected_state["fixable"]:
                selected_button.setText(
                    selected_state["label"]
                )
            else:
                selected_button.setText(
                    "Fix Selected"
                )

        batch_count = 0

        try:
            module = load_autofix_module()
            batch_count = len(
                module.collect_batch_safe(
                    self.api.VALIDATION_RESULTS
                )
            )
        except Exception:
            batch_count = 0

        if isinstance(
            all_button,
            QtWidgets.QPushButton
        ):
            all_button.setEnabled(
                batch_count > 0
            )
            all_button.setText(
                "Fix All Safe ({})".format(
                    batch_count
                )
                if batch_count
                else "Fix All Safe"
            )

    def fix_selected_validation(self):
        result = get_selected_validation_result()

        if not result:
            self.set_status(
                "Select a validation result first.",
                level="warning",
            )
            return

        try:
            module = load_autofix_module()
        except Exception as error:
            self.set_status(
                "Auto Fix unavailable: {}".format(error),
                level="error",
            )
            return

        if not module.can_fix_result(result):
            self.set_status(
                "The selected result has no registered safe auto-fix.",
                level="warning",
            )
            return

        if module.requires_confirmation(result):
            answer = QtWidgets.QMessageBox.question(
                self,
                "RenderHive Auto Fix",
                (
                    "{} cannot be undone. Continue?"
                ).format(
                    module.fix_label(result)
                ),
                QtWidgets.QMessageBox.Yes
                | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )

            if answer != QtWidgets.QMessageBox.Yes:
                return

        def apply_selected():
            outcome = module.apply_fix(result)

            if not outcome.get("success"):
                raise RuntimeError(
                    outcome.get(
                        "message",
                        "Auto Fix failed."
                    )
                )

            message = outcome.get(
                "message",
                "Auto Fix completed."
            )
            self.append_activity(
                "Auto Fix: {}".format(message)
            )

            # Re-run validation immediately so the UI reflects the change.
            self.api.validate_scene_from_ui()
            return outcome

        outcome = self.safe_action(
            "Applying auto-fix",
            apply_selected,
        )

        if outcome and outcome.get("success"):
            self.set_status(
                outcome.get(
                    "message",
                    "Auto Fix completed."
                ),
                level="success",
            )

    def fix_all_safe_validations(self):
        try:
            module = load_autofix_module()
            results = module.collect_batch_safe(
                self.api.VALIDATION_RESULTS
            )
        except Exception as error:
            self.set_status(
                "Auto Fix unavailable: {}".format(error),
                level="error",
            )
            return

        if not results:
            self.set_status(
                "No batch-safe validation fixes are available.",
                level="warning",
            )
            return

        answer = QtWidgets.QMessageBox.question(
            self,
            "RenderHive Fix All Safe",
            (
                "Apply {} unique safe fix(es)?\n\n"
                "Maya attribute changes will be grouped into one Undo step."
            ).format(len(results)),
            QtWidgets.QMessageBox.Yes
            | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )

        if answer != QtWidgets.QMessageBox.Yes:
            return

        def apply_all():
            outcomes = module.apply_many(results)

            successes = [
                item
                for item in outcomes
                if item.get("success")
            ]
            failures = [
                item
                for item in outcomes
                if not item.get("success")
            ]

            for outcome in outcomes:
                prefix = (
                    "Auto Fix"
                    if outcome.get("success")
                    else "Auto Fix Failed"
                )
                self.append_activity(
                    "{}: {}".format(
                        prefix,
                        outcome.get(
                            "message",
                            "Unknown result."
                        )
                    )
                )

            self.api.validate_scene_from_ui()

            if failures:
                failure_text = "\n".join(
                    "• {}".format(
                        item.get(
                            "message",
                            "Unknown failure."
                        )
                    )
                    for item in failures
                )

                QtWidgets.QMessageBox.warning(
                    self,
                    "RenderHive Auto Fix",
                    (
                        "{} fix(es) completed and {} failed:\n\n{}"
                    ).format(
                        len(successes),
                        len(failures),
                        failure_text,
                    ),
                )

            return {
                "successes": successes,
                "failures": failures,
            }

        summary = self.safe_action(
            "Applying safe fixes",
            apply_all,
        )

        if summary:
            self.set_status(
                "Auto Fix completed: {} fixed, {} failed.".format(
                    len(summary["successes"]),
                    len(summary["failures"]),
                ),
                level=(
                    "success"
                    if not summary["failures"]
                    else "warning"
                ),
            )

    def update_validation_summary(self, summary):
        error_count = summary.get("ERROR", 0)
        warning_count = summary.get("WARNING", 0)

        if error_count:
            self.set_status(
                "Validation finished with {} error(s).".format(error_count),
                level="error",
            )
        elif warning_count:
            self.set_status(
                "Validation passed with {} warning(s).".format(warning_count),
                level="warning",
            )
        else:
            self.set_status("Validation passed.", level="success")

    # ------------------------------------------------------------------
    # More page
    # ------------------------------------------------------------------


    def build_more_page(self):
        page, body = self.scroll_page(
            "Tools",
            "Authenticated API connection, recent activity and maintenance options.",
        )

        backend_card = Card(
            "API Connection",
            "Uses the RenderHive OpenAPI job endpoints and Token authentication.",
        )

        backend_url = register(
            "rh_api_url",
            QtWidgets.QLineEdit(),
        )
        backend_url.setPlaceholderText("http://127.0.0.1:8000")
        backend_url.setClearButtonEnabled(True)

        backend_token = register(
            "rh_api_token",
            QtWidgets.QLineEdit(),
        )
        backend_token.setPlaceholderText("Paste API token")
        backend_token.setEchoMode(QtWidgets.QLineEdit.Password)
        backend_token.setClearButtonEnabled(True)

        token_row = QtWidgets.QHBoxLayout()
        token_row.setContentsMargins(0, 0, 0, 0)
        token_row.setSpacing(7)
        token_row.addWidget(backend_token, 1)

        show_token = QtWidgets.QToolButton()
        show_token.setText("Show")
        show_token.setCheckable(True)
        show_token.setToolTip("Show or hide the API token")
        show_token.toggled.connect(
            lambda checked: backend_token.setEchoMode(
                QtWidgets.QLineEdit.Normal
                if checked
                else QtWidgets.QLineEdit.Password
            )
        )
        token_row.addWidget(show_token)

        token_widget = QtWidgets.QWidget()
        token_widget.setLayout(token_row)

        api_enabled = register(
            "rh_api_enabled",
            QtWidgets.QCheckBox("Use RenderHive API for Submit Job"),
        )
        api_enabled.setToolTip(
            "When disabled, Submit Job continues to use the Local Worker flow."
        )

        backend_card.layout.addWidget(
            LabeledField("API Base URL", backend_url)
        )
        backend_card.layout.addWidget(
            LabeledField("API Token", token_widget)
        )
        backend_card.layout.addWidget(api_enabled)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(7)

        save_button = QtWidgets.QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.save_api_settings)

        test_button = register(
            "test_api_button",
            QtWidgets.QPushButton("Test Connection"),
        )
        test_button.setObjectName("InfoButton")
        test_button.clicked.connect(self.test_api_connection)

        open_button = QtWidgets.QPushButton("Open API Config")
        open_button.setObjectName("GhostButton")
        open_button.clicked.connect(self.open_api_config)

        buttons.addWidget(save_button)
        buttons.addWidget(test_button)
        buttons.addWidget(open_button)
        buttons.addStretch()
        backend_card.layout.addLayout(buttons)

        backend_status = register(
            "api_connection_status",
            QtWidgets.QLabel("API settings are not loaded yet."),
        )
        backend_status.setObjectName("MutedText")
        backend_status.setWordWrap(True)
        backend_card.layout.addWidget(backend_status)

        api_note = QtWidgets.QLabel(
            "Jobs: /api/jobs/   •   Workers: /api/workers/   •   Pools: /api/pools/"
        )
        api_note.setObjectName("MutedText")
        api_note.setWordWrap(True)
        backend_card.layout.addWidget(api_note)

        body.addWidget(backend_card)

        activity = Card(
            "Activity Log",
            "Recent RenderHive actions and status messages.",
        )

        activity_log = register(
            "activity_log",
            QtWidgets.QPlainTextEdit(),
        )
        activity_log.setObjectName("ActivityLog")
        activity_log.setReadOnly(True)
        activity_log.setMaximumBlockCount(250)
        activity_log.setMinimumHeight(215)
        activity.layout.addWidget(activity_log)
        body.addWidget(activity, 1)

        maintenance_row = QtWidgets.QHBoxLayout()
        maintenance_row.addStretch()

        menu_button = QtWidgets.QToolButton()
        menu_button.setObjectName("MaintenanceButton")
        menu_button.setText("•••")
        menu_button.setToolTip("Maintenance")
        menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        menu = QtWidgets.QMenu(menu_button)

        state_folder_action = menu.addAction(
            "Open Restore Data Folder"
        )
        state_folder_action.triggered.connect(
            self.open_state_storage_folder
        )

        menu.addSeparator()

        uninstall_action = menu.addAction("Uninstall RenderHive…")
        uninstall_action.triggered.connect(
            self.api.uninstall_renderhive_from_maya
        )
        menu_button.setMenu(menu)
        maintenance_row.addWidget(menu_button)

        body.addLayout(maintenance_row)
        body.addStretch()
        return page


    def build_footer(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("FooterBar")

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        submit_row = QtWidgets.QHBoxLayout()
        submit_row.setSpacing(0)
        submit_row.addStretch()

        submit = register(
            "submit_job_button",
            QtWidgets.QPushButton("Submit Job"),
        )
        submit.setObjectName("SubmitButton")
        submit.setMinimumWidth(340)
        submit.setMaximumWidth(420)
        submit.setMinimumHeight(38)
        submit.setToolTip(
            "Submit the current Maya job. "
            "Submit the current validated job to the RenderHive API."
        )
        submit.clicked.connect(self.submit_job)

        submit_row.addWidget(submit)
        submit_row.addStretch()
        layout.addLayout(submit_row)

        progress = register(
            "progress",
            QtWidgets.QProgressBar(),
        )
        progress.setRange(0, 0)
        progress.setVisible(False)
        layout.addWidget(progress)

        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(7)

        status_dot = register(
            "status_dot",
            QtWidgets.QLabel(),
        )
        status_dot.setObjectName("StatusDot")
        status_row.addWidget(status_dot)

        status_text = register(
            "status",
            QtWidgets.QLabel("Ready"),
        )
        status_text.setObjectName("StatusText")
        status_row.addWidget(status_text, 1)

        status_row.addWidget(
            QtWidgets.QLabel("RenderHive")
        )
        layout.addLayout(status_row)

        return frame

    def set_busy(self, busy):
        progress = _WIDGETS.get("progress")
        if isinstance(progress, QtWidgets.QProgressBar):
            progress.setVisible(bool(busy))

    def infer_status_level(self, message):
        value = message.lower()

        if "error" in value or "failed" in value:
            return "error"
        if "warning" in value:
            return "warning"
        if "complete" in value or "passed" in value or "saved" in value:
            return "success"
        if "validat" in value or "sync" in value or "running" in value:
            return "info"
        return "success"

    def set_status(self, message, level=None):
        status_text = _WIDGETS.get("status")
        status_dot = _WIDGETS.get("status_dot")

        level = level or self.infer_status_level(message)
        color = {
            "error": COLORS["error"],
            "warning": COLORS["warning"],
            "info": COLORS["info"],
            "success": COLORS["success"],
        }.get(level, COLORS["success"])

        if isinstance(status_text, QtWidgets.QLabel):
            status_text.setText(message)

        if isinstance(status_dot, QtWidgets.QLabel):
            status_dot.setStyleSheet(
                "QLabel#StatusDot { background-color:%s; }" % color
            )

    def append_activity(self, message):
        log = _WIDGETS.get("activity_log")
        if not isinstance(log, QtWidgets.QPlainTextEdit):
            return

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log.appendPlainText("{}  {}".format(timestamp, message))

    def safe_action(self, label, callback):
        try:
            self.set_busy(True)
            self.set_status("{}…".format(label), level="info")
            QtWidgets.QApplication.processEvents()
            return callback()
        except Exception as error:
            self.set_status("{} failed: {}".format(label, error), level="error")
            QtWidgets.QMessageBox.critical(
                self,
                "RenderHive",
                "{} failed:\n\n{}".format(label, error),
            )
            return None
        finally:
            self.set_busy(False)

    def load_worker_pools(self):
        data = self.state_store.load_app_state(
            "worker_pools_v13",
            default={},
        )

        if not isinstance(data, dict):
            data = {}

        pools = {}
        for name, values in (data or {}).items():
            clean_name = str(name).strip()
            if not clean_name:
                continue

            clean_values = []
            for value in values or []:
                value = str(value).strip()
                if value and value not in clean_values:
                    clean_values.append(value)

            # Keep empty pool names too. Backend pools can exist before any
            # Worker has been assigned to them.
            pools[clean_name] = clean_values

        return pools

    def save_worker_pools(self):
        # This SQLite cache is a fallback for offline startup. The backend is
        # still authoritative whenever the API is enabled and reachable.
        self.state_store.save_app_state(
            "worker_pools_v13",
            self.worker_pools,
        )

        pool = _WIDGETS.get("rh_pool")
        if isinstance(pool, QtWidgets.QComboBox):
            self.state_store.save_app_state(
                "selected_pool_v13",
                pool.currentText(),
            )

    @staticmethod
    def normalize_pools(payload):
        if isinstance(payload, dict):
            for key in ("pools", "items", "data", "results"):
                candidate = payload.get(key)
                if isinstance(candidate, (list, tuple)):
                    payload = candidate
                    break
            else:
                payload = []

        if not isinstance(payload, (list, tuple)):
            payload = []

        pools = []
        seen = set()
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            pool_id = str(entry.get("id") or "").strip()
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            key = pool_id or name.lower()
            if key in seen:
                continue
            seen.add(key)
            pools.append({
                "id": pool_id,
                "name": name,
                "description": str(entry.get("description") or ""),
                "created_at": entry.get("created_at"),
                "updated_at": entry.get("updated_at"),
            })

        pools.sort(key=lambda item: item["name"].lower())
        return pools

    def refresh_pool_combo(self, preferred=""):
        combo = _WIDGETS.get("rh_pool")
        if not isinstance(combo, QtWidgets.QComboBox):
            return

        current = (
            preferred
            or self._pending_pool_scene_name
            or combo.currentText()
            or str(
                self.state_store.load_app_state(
                    "selected_pool_v13",
                    default="All Workers",
                )
            )
        )

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All Workers")
        combo.addItems(sorted(self.worker_pools.keys(), key=lambda value: value.lower()))

        index = combo.findText(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

        if index >= 0 and current == self._pending_pool_scene_name:
            self._pending_pool_scene_name = ""

        self.on_pool_changed(combo.currentText())

    def selected_pool_id(self):
        combo = _WIDGETS.get("rh_pool")
        name = combo.currentText() if isinstance(combo, QtWidgets.QComboBox) else ""
        record = self.pool_records.get(name) or {}
        return str(record.get("id") or "")

    def selected_pool_worker_ids(self):
        combo = _WIDGETS.get("rh_pool")
        pool_name = (
            combo.currentText()
            if isinstance(combo, QtWidgets.QComboBox)
            else "All Workers"
        )

        if not pool_name or pool_name == "All Workers":
            return [
                str(worker.get("id") or "")
                for worker in self.available_workers
                if str(worker.get("id") or "")
            ]

        return list(self.worker_pools.get(pool_name, []))

    def active_pool_workers(self):
        selected_ids = set(self.selected_pool_worker_ids())
        combo = _WIDGETS.get("rh_pool")
        pool_name = (
            combo.currentText()
            if isinstance(combo, QtWidgets.QComboBox)
            else "All Workers"
        )

        if pool_name == "All Workers":
            return list(self.available_workers)

        return [
            worker
            for worker in self.available_workers
            if str(worker.get("id") or "") in selected_ids
        ]

    def worker_assignment_mode(self):
        widget = _WIDGETS.get("rh_worker_assignment_mode")

        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()

        if hasattr(widget, "currentText"):
            try:
                return widget.currentText()
            except Exception:
                pass

        return "Use All Workers in Pool"

    def worker_data_is_stale(self, max_age_seconds=300):
        if self.worker_target_last_sync is None:
            return True

        age = (
            datetime.datetime.now()
            - self.worker_target_last_sync
        ).total_seconds()

        return age > float(max_age_seconds)

    def online_pool_workers(self):
        return [
            worker
            for worker in self.active_pool_workers()
            if worker_is_online(worker)
        ]

    def eligible_workers(self):
        workers = self.online_pool_workers()
        mode = self.worker_assignment_mode()
        allowed = set(
            qt_get_list("rh_allowed_workers", [])
        )
        denied = set(
            qt_get_list("rh_denied_workers", [])
        )

        if mode == "Use Selected Workers Only":
            workers = [
                worker
                for worker in workers
                if worker_identifier(worker) in allowed
            ]
        else:
            workers = [
                worker
                for worker in workers
                if worker_identifier(worker) not in denied
            ]

        minimum_ram = qt_get_int("rh_min_ram_gb", 0)
        minimum_vram = qt_get_int("rh_min_vram_gb", 0)
        eligible = []

        for worker in workers:
            memory_gb = worker_memory_gb(worker)
            vram_gb = worker_vram_gb(worker)

            if minimum_ram:
                if memory_gb is None or memory_gb < minimum_ram:
                    continue

            if minimum_vram:
                if vram_gb is None or vram_gb < minimum_vram:
                    continue

            eligible.append(worker)

        return eligible

    def eligible_worker_ids(self):
        return [
            worker_identifier(worker)
            for worker in self.eligible_workers()
            if worker_identifier(worker)
        ]

    def update_worker_sync_chips(self):
        api_chip = _WIDGETS.get("worker_api_chip")
        worker_chip = _WIDGETS.get("worker_count_chip")
        pool_chip = _WIDGETS.get("worker_pool_count_chip")
        time_chip = _WIDGETS.get("worker_sync_time_chip")

        total_workers = len(self.available_workers)
        online_workers = len([
            worker
            for worker in self.available_workers
            if worker_is_online(worker)
        ])
        pool_count = len(self.api_pools)

        syncing = (
            self.worker_sync_thread is not None
            and self.worker_sync_thread.isRunning()
        )

        if isinstance(api_chip, WorkerStatusChip):
            if syncing:
                api_chip.set_state(
                    "Connecting…",
                    COLORS["info"],
                )
            elif self.worker_target_sync_error:
                api_chip.set_state(
                    "API Offline",
                    COLORS["error"],
                )
            elif self.worker_target_has_sync:
                api_chip.set_state(
                    "API Online",
                    COLORS["success"],
                )
            else:
                api_chip.set_state(
                    "Not Synced",
                    COLORS["warning"],
                )

        if isinstance(worker_chip, WorkerStatusChip):
            label = (
                "{} Online / {}".format(
                    online_workers,
                    total_workers,
                )
                if total_workers
                else "0 Workers"
            )
            worker_chip.set_state(
                label,
                COLORS["success"]
                if online_workers
                else COLORS["warning"],
            )

        if isinstance(pool_chip, WorkerStatusChip):
            pool_chip.set_state(
                "{} Pool{}".format(
                    pool_count,
                    "" if pool_count == 1 else "s",
                ),
                COLORS["info"]
                if pool_count
                else COLORS["muted"],
            )

        if isinstance(time_chip, WorkerStatusChip):
            if self.worker_target_last_sync is None:
                time_chip.set_state(
                    "Never",
                    COLORS["muted"],
                )
            else:
                prefix = (
                    "Cached"
                    if self.worker_target_sync_error
                    else (
                        "Stale"
                        if self.worker_data_is_stale()
                        else "Synced"
                    )
                )
                color = (
                    COLORS["warning"]
                    if prefix in ("Cached", "Stale")
                    else COLORS["secondary"]
                )
                time_chip.set_state(
                    "{} {}".format(
                        prefix,
                        self.worker_target_last_sync.strftime("%H:%M"),
                    ),
                    color,
                )

    def update_worker_targeting_summary(self, *args):
        label = _WIDGETS.get("worker_eligibility_summary")
        if not isinstance(label, QtWidgets.QLabel):
            return

        members = self.active_pool_workers()
        online = [
            worker
            for worker in members
            if worker_is_online(worker)
        ]
        eligible = self.eligible_workers()

        member_count = len(members)
        online_count = len(online)
        eligible_count = len(eligible)

        summary = (
            "{} member{} · {} online · {} eligible".format(
                member_count,
                "" if member_count == 1 else "s",
                online_count,
                eligible_count,
            )
        )

        if not self.worker_target_has_sync:
            detail = "Refresh workers before submitting."
            color = COLORS["warning"]
        elif self.worker_target_sync_error:
            detail = "Showing the last successful worker snapshot."
            color = COLORS["warning"]
        elif eligible_count == 0:
            detail = "No online workers match the current targeting rules."
            color = COLORS["error"]
        else:
            detail = "Ready for submission."
            color = COLORS["success"]

        label.setText("{}  —  {}".format(summary, detail))
        label.setStyleSheet(
            "QLabel#EligibilitySummary {"
            "background-color:%s;"
            "border:1px solid %s;"
            "border-radius:6px;"
            "color:%s;"
            "padding:7px 9px;"
            "font-weight:600;"
            "}" % (
                COLORS["surface2"],
                color,
                color,
            )
        )

    def update_worker_assignment_ui(self):
        selected_only = (
            self.worker_assignment_mode()
            == "Use Selected Workers Only"
        )

        selected_field = _WIDGETS.get("worker_selected_field")
        excluded_field = _WIDGETS.get("worker_excluded_field")
        hint = _WIDGETS.get("worker_assignment_hint")

        if isinstance(selected_field, QtWidgets.QWidget):
            selected_field.setVisible(selected_only)

        if isinstance(excluded_field, QtWidgets.QWidget):
            excluded_field.setVisible(not selected_only)

        if isinstance(hint, QtWidgets.QLabel):
            if selected_only:
                hint.setText(
                    "Only the selected online workers can receive this job."
                )
            else:
                hint.setText(
                    "All online workers in the pool can receive this job, "
                    "except workers excluded below."
                )

        self.update_worker_targeting_summary()

    def on_worker_assignment_mode_changed(self, mode=""):
        selected_only = (
            str(mode) == "Use Selected Workers Only"
        )

        # Clear the inactive strategy. This keeps Allowed and Denied mutually
        # exclusive in the UI, restored scene state and final task payload.
        if selected_only:
            qt_set_list("rh_denied_workers", [])
        else:
            qt_set_list("rh_allowed_workers", [])

        self.update_worker_assignment_ui()

    def on_allowed_workers_changed(self):
        allowed = set(qt_get_list("rh_allowed_workers", []))
        denied = qt_get_list("rh_denied_workers", [])
        clean_denied = [
            value
            for value in denied
            if value not in allowed
        ]

        if clean_denied != denied:
            qt_set_list("rh_denied_workers", clean_denied)

        self.update_worker_targeting_summary()

    def on_denied_workers_changed(self):
        denied = set(qt_get_list("rh_denied_workers", []))
        allowed = qt_get_list("rh_allowed_workers", [])
        clean_allowed = [
            value
            for value in allowed
            if value not in denied
        ]

        if clean_allowed != allowed:
            qt_set_list("rh_allowed_workers", clean_allowed)

        self.update_worker_targeting_summary()

    def on_pool_changed(self, pool_name=""):
        workers = self.active_pool_workers()

        for widget_name in ("rh_allowed_workers", "rh_denied_workers"):
            widget = _WIDGETS.get(widget_name)
            if isinstance(widget, WorkerMultiSelect):
                widget.set_workers(workers)

        # Reconcile old or restored data after a pool change. A worker cannot
        # remain selected once it leaves the active pool, and it can never be
        # both selected and excluded.
        self.on_allowed_workers_changed()
        self.on_denied_workers_changed()
        self.on_worker_assignment_mode_changed(
            self.worker_assignment_mode()
        )

        self.update_worker_targeting_summary()

    def manage_worker_pools(self):
        if not self.api_enabled():
            QtWidgets.QMessageBox.information(
                self,
                "RenderHive Pools",
                "Enable the RenderHive API to load worker pools.",
            )
            return

        provider_available = (
            hasattr(
                self.api,
                "get_worker_targeting_snapshot",
            )
            or hasattr(
                self.api,
                "get_api_pools",
            )
        )

        if not provider_available:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive Pools",
                "The current API connection does not provide worker pools.",
            )
            return

        dialog = ApiWorkerPoolManagerDialog(
            self.api,
            self.available_workers,
            self.api_pools,
            parent=self,
        )

        result = dialog.exec_()
        selected_name = dialog.selected_pool_name()

        # Keep the main Job page in sync with any data refreshed inside
        # the browser, even when the dialog was closed without selection.
        self.apply_available_workers(
            dialog.workers(),
            pools=dialog.pools(),
        )

        if (
            result == QtWidgets.QDialog.Accepted
            and selected_name
        ):
            self.refresh_pool_combo(
                preferred=selected_name
            )
            self.append_activity(
                "Worker pool selected: {}.".format(
                    selected_name
                )
            )
        else:
            self.append_activity(
                "Backend worker pools refreshed."
            )


    def worker_provider(self):
        snapshot = getattr(self.api, "get_worker_targeting_snapshot", None)
        if callable(snapshot):
            return snapshot

        method_names = (
            "get_available_workers",
            "list_available_workers",
            "get_workers",
            "list_workers",
        )

        for method_name in method_names:
            method = getattr(self.api, method_name, None)
            if callable(method):
                return method

        for attribute_name in (
            "AVAILABLE_WORKERS",
            "available_workers",
        ):
            value = getattr(self.api, attribute_name, None)
            if value is not None:
                return lambda workers=value: workers

        return None

    def normalize_workers(self, payload):
        if isinstance(payload, dict):
            for key in ("workers", "items", "data", "results"):
                candidate = payload.get(key)
                if isinstance(candidate, (list, tuple)):
                    payload = candidate
                    break
            else:
                payload = []

        if not isinstance(payload, (list, tuple)):
            payload = []

        workers = []
        seen = set()

        for entry in payload:
            if isinstance(entry, str):
                worker_id = entry.strip()
                hostname = worker_id
                label = worker_id
                status = "ONLINE"
                available = True
                raw = {}
            elif isinstance(entry, dict):
                raw = dict(entry)
                backend_id = str(
                    entry.get("id")
                    or entry.get("worker_id")
                    or ""
                ).strip()
                hostname = str(
                    entry.get("hostname")
                    or entry.get("machine_name")
                    or entry.get("display_name")
                    or entry.get("name")
                    or ""
                ).strip()
                worker_id = backend_id or hostname
                label = hostname or (
                    "Worker {}".format(backend_id)
                    if backend_id
                    else "Unnamed Worker"
                )
                status = str(
                    entry.get("status")
                    or entry.get("state")
                    or ""
                ).strip().upper()

                available_value = entry.get("available")
                if available_value is None:
                    available_value = entry.get("online")

                available = (
                    status not in (
                        "OFFLINE",
                        "DISCONNECTED",
                        "DISABLED",
                    )
                    if available_value is None
                    else bool(available_value)
                )
            else:
                continue

            if not worker_id or worker_id in seen:
                continue

            worker_pools = []
            if isinstance(entry, dict):
                for pool in entry.get("pools") or []:
                    if isinstance(pool, dict):
                        pool_id = str(pool.get("id") or "").strip()
                        pool_name = str(pool.get("name") or "").strip()
                        if pool_id or pool_name:
                            worker_pools.append({
                                "id": pool_id,
                                "name": pool_name,
                                "description": str(
                                    pool.get("description") or ""
                                ),
                            })

            normalized = {
                "id": worker_id,
                "hostname": hostname or label,
                "label": label or worker_id,
                "status": status or (
                    "ONLINE"
                    if available
                    else "OFFLINE"
                ),
                "available": bool(available),
                "pools": worker_pools,
                "ip_address": (
                    str(raw.get("ip_address") or "")
                    if isinstance(raw, dict)
                    else ""
                ),
                "cores": (
                    raw.get("cores")
                    if isinstance(raw, dict)
                    else None
                ),
                "memory_mb": (
                    raw.get("memory_mb")
                    if isinstance(raw, dict)
                    else None
                ),
                "ram_gb": (
                    raw.get("ram_gb")
                    if isinstance(raw, dict)
                    else None
                ),
                "vram_gb": (
                    raw.get("vram_gb")
                    if isinstance(raw, dict)
                    else None
                ),
                "gpu_models": (
                    raw.get("gpu_models") or []
                    if isinstance(raw, dict)
                    else []
                ),
                "system_info": (
                    raw.get("system_info") or {}
                    if isinstance(raw, dict)
                    else {}
                ),
                "last_ping": (
                    str(raw.get("last_ping") or "")
                    if isinstance(raw, dict)
                    else ""
                ),
                "tags": (
                    list(raw.get("tags") or [])
                    if isinstance(raw, dict)
                    else []
                ),
            }

            seen.add(worker_id)
            workers.append(normalized)

        workers.sort(
            key=lambda item: item["label"].lower()
        )
        return workers

    def sync_available_workers(self, *args):
        provider = self.worker_provider()
        button = _WIDGETS.get("sync_workers_button")

        if provider is None:
            self.worker_target_sync_error = (
                "The current API does not expose worker targeting endpoints."
            )
            self.update_worker_sync_chips()
            self.update_worker_targeting_summary()
            return

        if self.worker_sync_thread is not None:
            if self.worker_sync_thread.isRunning():
                return

        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(False)
            button.setText("Refreshing…")

        self.worker_target_sync_error = ""
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()

        self.worker_sync_thread = WorkerSyncThread(
            provider,
            parent=self,
        )
        self.worker_sync_thread.succeeded.connect(
            self.on_workers_synced
        )
        self.worker_sync_thread.failed.connect(
            self.on_worker_sync_failed
        )
        self.worker_sync_thread.finished.connect(
            self.on_worker_sync_finished
        )
        self.worker_sync_thread.start()

    def on_workers_synced(self, payload):
        pools_payload = None
        workers_payload = payload

        if isinstance(payload, dict) and (
            "workers" in payload or "pools" in payload
        ):
            workers_payload = payload.get("workers") or []
            pools_payload = payload.get("pools") or []

        workers = self.normalize_workers(workers_payload)
        pools = (
            self.normalize_pools(pools_payload)
            if pools_payload is not None
            else None
        )

        self.worker_target_last_sync = datetime.datetime.now()
        self.worker_target_has_sync = True
        self.worker_target_sync_error = ""

        self.apply_available_workers(
            workers,
            pools=pools,
        )
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()

        online_count = len([
            worker
            for worker in workers
            if worker_is_online(worker)
        ])

        self.append_activity(
            "Worker target sync completed: {} online / {} total, "
            "{} backend pool(s).".format(
                online_count,
                len(workers),
                len(self.api_pools),
            )
        )

    def on_worker_sync_failed(self, error):
        self.worker_target_sync_error = str(error or "Unknown error")
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()

        cached_note = (
            " Showing the last successful snapshot."
            if self.available_workers or self.api_pools
            else ""
        )

        self.set_status(
            "Worker sync failed.{}".format(cached_note),
            level="warning",
        )
        self.append_activity(
            "Worker sync failed: {}{}".format(
                error,
                cached_note,
            )
        )

    def on_worker_sync_finished(self):
        button = _WIDGETS.get("sync_workers_button")

        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(True)
            button.setText("Refresh")

        if self.worker_sync_thread is not None:
            self.worker_sync_thread.deleteLater()
            self.worker_sync_thread = None

    def apply_available_workers(self, workers, pools=None):
        normalized = self.normalize_workers(workers)
        self.available_workers = normalized

        if pools is not None:
            normalized_pools = self.normalize_pools(pools)
            self.api_pools = normalized_pools
            self.pool_records = {
                pool["name"]: dict(pool)
                for pool in normalized_pools
            }

            memberships = {
                pool["name"]: []
                for pool in normalized_pools
            }
            names_by_id = {
                str(pool.get("id") or ""): pool["name"]
                for pool in normalized_pools
                if str(pool.get("id") or "")
            }

            for worker in normalized:
                worker_id = str(worker.get("id") or "")
                for pool in worker.get("pools") or []:
                    pool_id = str(pool.get("id") or "")
                    pool_name = str(pool.get("name") or "") or names_by_id.get(pool_id, "")
                    if pool_name and pool_name in memberships and worker_id:
                        if worker_id not in memberships[pool_name]:
                            memberships[pool_name].append(worker_id)

            self.worker_pools = memberships
            self.using_api_pools = True
            self.save_worker_pools()

        self.refresh_pool_combo(preferred=self._pending_pool_scene_name)
        self.apply_pending_worker_scene_state()
        self.update_worker_sync_chips()
        self.update_worker_targeting_summary()
        self.save_scene_state(force=True)


    def validate_scene(self):
        return self.safe_action("Validating scene", self.api.validate_scene_from_ui)


    def api_enabled(self):
        widget = _WIDGETS.get("rh_api_enabled")
        if isinstance(widget, QtWidgets.QCheckBox):
            return bool(widget.isChecked())

        try:
            return bool(
                self.api.get_api_config().get("enabled", False)
            )
        except Exception:
            return False

    def load_api_settings(self):
        try:
            config = self.api.get_api_config()
        except Exception as error:
            self.set_api_status(
                "Could not load API settings: {}".format(error),
                level="error",
            )
            return

        url_widget = _WIDGETS.get("rh_api_url")
        token_widget = _WIDGETS.get("rh_api_token")
        enabled_widget = _WIDGETS.get("rh_api_enabled")

        if isinstance(url_widget, QtWidgets.QLineEdit):
            url_widget.setText(str(config.get("base_url", "")))

        if isinstance(token_widget, QtWidgets.QLineEdit):
            token_widget.setText(
                str(config.get("auth", {}).get("token", ""))
            )

        if isinstance(enabled_widget, QtWidgets.QCheckBox):
            enabled_widget.setChecked(bool(config.get("enabled", False)))

        has_token = bool(config.get("auth", {}).get("token"))
        if config.get("enabled", False) and has_token:
            self.set_api_status(
                "RenderHive API enabled with Token authentication. Test the connection before submitting.",
                level="info",
            )
        elif config.get("enabled", False):
            self.set_api_status(
                "RenderHive API enabled, but the token is empty.",
                level="warning",
            )
        else:
            self.set_api_status(
                "RenderHive API is disabled. Enable it before submission.",
                level="warning",
            )

    def api_settings_payload(self):
        url_widget = _WIDGETS.get("rh_api_url")
        token_widget = _WIDGETS.get("rh_api_token")
        enabled_widget = _WIDGETS.get("rh_api_enabled")

        base_url = (
            url_widget.text().strip()
            if isinstance(url_widget, QtWidgets.QLineEdit)
            else ""
        )
        token = (
            token_widget.text().strip()
            if isinstance(token_widget, QtWidgets.QLineEdit)
            else ""
        )
        enabled = (
            bool(enabled_widget.isChecked())
            if isinstance(enabled_widget, QtWidgets.QCheckBox)
            else False
        )

        return {
            "base_url": base_url,
            "enabled": enabled,
            "auth": {
                "type": "token",
                "token": token,
            },
        }

    def save_api_settings(self):
        try:
            config = self.api.save_api_config(
                self.api_settings_payload()
            )
        except Exception as error:
            self.set_api_status(
                "Could not save API settings: {}".format(error),
                level="error",
            )
            QtWidgets.QMessageBox.critical(
                self,
                "RenderHive API",
                "Could not save API settings:\n\n{}".format(error),
            )
            return None

        self.set_api_status(
            "Settings saved: {}".format(config.get("base_url", "")),
            level="success",
        )
        self.append_activity("API settings saved.")
        return config

    def set_api_status(self, message, level="info"):
        label = _WIDGETS.get("api_connection_status")
        color = {
            "error": COLORS["error"],
            "warning": COLORS["warning"],
            "info": COLORS["info"],
            "success": COLORS["success"],
        }.get(level, COLORS["secondary"])

        if isinstance(label, QtWidgets.QLabel):
            label.setText(str(message))
            label.setStyleSheet(
                "QLabel { color:%s; }" % color
            )

    def open_api_config(self):
        try:
            path = self.api.get_api_config_path()

            if hasattr(os, "startfile"):
                os.startfile(path)
            else:
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(path)
                )

            self.append_activity(
                "Opened API config: {}".format(path)
            )
        except Exception as error:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive API",
                "Could not open API config:\n\n{}".format(error),
            )

    def test_api_connection(self):
        if (
            self.api_test_thread is not None
            and self.api_test_thread.isRunning()
        ):
            return

        if not self.save_api_settings():
            return

        button = _WIDGETS.get("test_api_button")
        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(False)
            button.setText("Testing…")

        self.set_api_status(
            "Testing API connection…",
            level="info",
        )
        self.set_status(
            "Testing API connection…",
            level="info",
        )

        self.api_test_thread = WorkerSyncThread(
            self.api.test_api_connection,
            parent=self,
        )
        self.api_test_thread.succeeded.connect(
            self.on_api_test_succeeded
        )
        self.api_test_thread.failed.connect(
            self.on_api_test_failed
        )
        self.api_test_thread.finished.connect(
            self.on_api_test_finished
        )
        self.api_test_thread.start()

    def on_api_test_succeeded(self, response):
        status_code = (
            response.get("status_code", 200)
            if isinstance(response, dict)
            else 200
        )

        self.set_api_status(
            "RenderHive API is online. HTTP {}.".format(status_code),
            level="success",
        )
        self.set_status(
            "API connection successful.",
            level="success",
        )
        self.append_activity(
            "API connection test succeeded."
        )

        if self.api_enabled():
            QtCore.QTimer.singleShot(
                0,
                self.sync_available_workers
            )

    def on_api_test_failed(self, error):
        self.set_api_status(
            "API connection failed: {}".format(error),
            level="error",
        )
        self.set_status(
            "API connection failed.",
            level="error",
        )
        self.append_activity(
            "API connection test failed: {}".format(error)
        )

    def on_api_test_finished(self):
        button = _WIDGETS.get("test_api_button")
        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(True)
            button.setText("Test Connection")

        if self.api_test_thread is not None:
            self.api_test_thread.deleteLater()
            self.api_test_thread = None

    def prepare_api_task(self):
        ok, message = self.api.save_scene_if_needed()

        if not ok:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive Submission",
                message,
            )
            return None

        report = self.api.validate_scene_from_ui()
        if not report:
            return None

        error_count = int(
            report.get("summary", {}).get("ERROR", 0)
        )

        if error_count:
            QtWidgets.QMessageBox.critical(
                self,
                "RenderHive Submission Blocked",
                (
                    "The scene contains {} validation error(s).\n\n"
                    "Fix them before submitting the job."
                ).format(error_count),
            )
            return None

        if (
            self.worker_target_has_sync
            and self.worker_data_is_stale()
        ):
            answer = QtWidgets.QMessageBox.question(
                self,
                "Worker Data Is Stale",
                (
                    "Worker and pool data was last synchronized more than "
                    "5 minutes ago.\n\n"
                    "Submit using the cached snapshot?"
                ),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )

            if answer != QtWidgets.QMessageBox.Yes:
                self.set_status(
                    "Submission cancelled: refresh worker targeting.",
                    level="warning",
                )
                return None

        eligible = self.eligible_workers()

        if not eligible:
            answer = QtWidgets.QMessageBox.question(
                self,
                "No Eligible Workers",
                (
                    "No online workers match the selected pool, assignment "
                    "and hardware requirements.\n\n"
                    "The Job can still be submitted, but it may remain PENDING "
                    "until a compatible Worker becomes available.\n\n"
                    "Submit it anyway?"
                ),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )

            if answer != QtWidgets.QMessageBox.Yes:
                self.set_status(
                    "Submission cancelled: no eligible workers.",
                    level="warning",
                )
                return None

        task = self.api.build_task()
        errors = self.api.validate_task(task)

        if errors:
            QtWidgets.QMessageBox.critical(
                self,
                "RenderHive Task Validation",
                "\n".join("• {}".format(error) for error in errors),
            )
            return None

        return task

    def submit_job(self):
        if not self.api_enabled():
            self.set_status(
                "RenderHive API is disabled.",
                level="warning",
            )
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive API",
                (
                    "Enable 'Use RenderHive API for Submit Job' "
                    "inside Tools before submitting."
                ),
            )
            return None

        if (
            self.api_submit_thread is not None
            and self.api_submit_thread.isRunning()
        ):
            return

        if not self.save_api_settings():
            return

        task = self.prepare_api_task()
        if not task:
            return

        button = _WIDGETS.get("submit_job_button")
        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(False)
            button.setText("Submitting…")

        self.set_busy(True)
        self.set_status(
            "Submitting job to API…",
            level="info",
        )
        self.append_activity(
            "API submission started: {}.".format(
                task.get("task_uid", task.get("job_name", "maya_job"))
            )
        )

        self.api_submit_thread = WorkerSyncThread(
            lambda: self.api.submit_job_to_api(task),
            parent=self,
        )
        self.api_submit_thread.succeeded.connect(
            self.on_api_submit_succeeded
        )
        self.api_submit_thread.failed.connect(
            self.on_api_submit_failed
        )
        self.api_submit_thread.finished.connect(
            self.on_api_submit_finished
        )
        self.api_submit_thread.start()

    def on_api_submit_succeeded(self, response):
        response = (
            response
            if isinstance(response, dict)
            else {"message": str(response)}
        )
        job_data = response.get("job")
        if not isinstance(job_data, dict):
            job_data = {}

        job_id = (
            response.get("job_id")
            or response.get("id")
            or response.get("uid")
            or job_data.get("job_id")
            or job_data.get("id")
            or job_data.get("uid")
            or "Unknown"
        )
        status = (
            response.get("state")
            or response.get("status")
            or job_data.get("state")
            or job_data.get("status")
            or "PENDING"
        )
        job_display_name = str(
            response.get("visible_name")
            or job_data.get("visible_name")
            or response.get("name")
            or job_data.get("name")
            or "Submitted Job"
        ).strip()
        message = (
            response.get("message")
            or "Job submitted successfully."
        )

        if response.get("_renderhive_resolved_from_list"):
            self.append_activity(
                "Created Job reference was resolved from the Jobs API response list."
            )

        self.set_status(
            "Job submitted: {} ({})".format(job_display_name, status),
            level="success",
        )
        self.set_api_status(
            "Last submission: {} — {}".format(job_display_name, status),
            level="success",
        )
        self.append_activity(
            "API accepted job '{}' with status {}. Reference: {}.".format(
                job_display_name,
                status,
                job_id,
            )
        )

        QtWidgets.QMessageBox.information(
            self,
            "RenderHive Submission",
            (
                "{}\n\n"
                "Job: {}\n"
                "Status: {}\n"
                "Backend Reference: {}"
            ).format(
                message,
                job_display_name,
                status,
                job_id,
            ),
        )

    def on_api_submit_failed(self, error):
        self.set_status(
            "API submission failed.",
            level="error",
        )
        self.set_api_status(
            "Submission failed: {}".format(error),
            level="error",
        )
        self.append_activity(
            "API submission failed: {}".format(error)
        )
        QtWidgets.QMessageBox.critical(
            self,
            "RenderHive Submission Failed",
            str(error),
        )

    def on_api_submit_finished(self):
        button = _WIDGETS.get("submit_job_button")
        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(True)
            button.setText("Submit Job")

        self.set_busy(False)

        if self.api_submit_thread is not None:
            self.api_submit_thread.deleteLater()
            self.api_submit_thread = None



    def sync_from_scene(self, *args, **kwargs):
        record_activity = bool(
            kwargs.get("record_activity", True)
        )

        qt_set_text("rh_scene_path", self.api.get_scene_path())
        qt_set_text("rh_project_path", self.api.get_project_path())
        qt_set_text("rh_output_path", self.api.get_default_output_path())
        qt_set_text("rh_job_name", self.api.get_scene_name())

        project_path = self.api.get_project_path()
        project_name = (
            os.path.basename(os.path.normpath(project_path))
            if project_path
            else "RenderHive_Demo"
        )

        if not qt_get_text("rh_project_name"):
            qt_set_text("rh_project_name", project_name)

        start, end = self.api.get_frame_range()
        qt_set_int("rh_frame_start", start)
        qt_set_int("rh_frame_end", end)

        width, height = self.api.get_resolution()
        qt_set_int("rh_width", width)
        qt_set_int("rh_height", height)
        qt_set_text("rh_image_name", self.api.get_scene_name())

        renderer = self.api.get_current_renderer()
        renderer_combo = _WIDGETS.get("rh_renderer")
        if isinstance(renderer_combo, QtWidgets.QComboBox):
            index = renderer_combo.findText(renderer)
            if index >= 0:
                renderer_combo.setCurrentIndex(index)

        qt_rebuild_camera_menu()

        header_scene = _WIDGETS.get("header_scene")
        if isinstance(header_scene, QtWidgets.QLabel):
            header_scene.setText(
                "Scene: {}".format(self.api.get_scene_name() or "Untitled")
            )

        header_renderer = _WIDGETS.get("header_renderer")
        if isinstance(header_renderer, QtWidgets.QLabel):
            header_renderer.setText("Renderer: {}".format(renderer or "Unknown"))

        if record_activity:
            self.set_status("Synced from scene.", level="info")
            self.append_activity("Scene values synchronized.")

        if self._active_scene_state_key:
            self.save_scene_state(force=True)

    def apply_preset(self):
        preset = _WIDGETS["render_preset"].currentText()
        values = {
            "Preview": (640, 360, "png"),
            "HD": (1280, 720, "png"),
            "Full HD": (1920, 1080, "png"),
            "Production EXR": (1920, 1080, "exr"),
        }.get(preset)

        if not values:
            self.set_status("Select a preset first.", level="warning")
            return

        width, height, image_format = values
        qt_set_int("rh_width", width)
        qt_set_int("rh_height", height)

        combo = _WIDGETS.get("rh_image_format")
        if isinstance(combo, QtWidgets.QComboBox):
            index = combo.findText(image_format)
            if index >= 0:
                combo.setCurrentIndex(index)

        self.set_status("Applied {} preset.".format(preset), level="success")
        self.append_activity("Render preset applied: {}.".format(preset))


def show_submitter(api):
    global _WINDOW, _API, _WIDGETS

    _API = api
    _WIDGETS = {}
    install_api_bridge(api)

    if _WINDOW is not None:
        try:
            _WINDOW.close()
            _WINDOW.deleteLater()
        except Exception:
            pass

    _WINDOW = RenderHiveSubmitter(api)
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW
