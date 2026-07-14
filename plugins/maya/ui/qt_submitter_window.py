from __future__ import print_function

import datetime
import importlib
import json
import math
import os
import platform
import sys
import uuid

from PySide2 import QtCore, QtGui, QtWidgets
from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui
import maya.cmds as cmds

from .qt_theme import COLORS, build_stylesheet


WINDOW_OBJECT_NAME = "RenderHiveQtSubmitter"
UI_VERSION = "1.0.1"
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

    allowed_workers = split_worker_list(qt_get_text("rh_allowed_workers", ""))
    denied_workers = split_worker_list(qt_get_text("rh_denied_workers", ""))
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
            "pool": qt_get_option("rh_pool", "Any"),
            "hardware_preset": qt_get_option(
                "rh_hardware_preset",
                "Any Compatible Worker",
            ),
            "allowed_workers": allowed_workers,
            "denied_workers": denied_workers,
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
        "pool": task.get("pool", "Any"),
        "machine_limit": task.get("machine_limit", 0),
        "concurrent_tasks": task.get("concurrent_tasks", 1),
        "allowed_workers": allowed_workers,
        "denied_workers": denied_workers,
        "hardware": {
            "preset": task.get("hardware_preset", "Any Compatible Worker"),
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


class TaskPreviewDialog(QtWidgets.QDialog):
    def __init__(self, api, task, errors=None, parent=None):
        super(TaskPreviewDialog, self).__init__(parent)
        self.api = api
        self.task = task
        self.errors = errors or []

        self.setWindowTitle("Review RenderHive Task")
        self.setObjectName("TaskPreviewDialog")
        self.resize(680, 620)
        self.setModal(True)

        self.build_ui()

    def build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QtWidgets.QLabel("Review Task")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Confirm the scheduling, worker targeting and output values before saving or submitting."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        frames = self.task.get("frames", {})
        farm = self.task.get("farm", {})
        validation = self.task.get("validation", {})

        summary = QtWidgets.QFrame()
        summary.setObjectName("Card")
        grid = QtWidgets.QGridLayout(summary)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        rows = [
            ("Job", self.task.get("job_name", "—")),
            ("Frames", "{}–{}  step {}".format(
                frames.get("start", "—"),
                frames.get("end", "—"),
                frames.get("step", 1),
            )),
            ("Tasks", "{} task(s), chunk {}".format(
                frames.get("task_count", 0),
                frames.get("chunk_size", 1),
            )),
            ("Pool", farm.get("pool", "Any")),
            ("Machine Limit", str(farm.get("machine_limit", 0) or "Unlimited")),
            ("Concurrent / Worker", str(farm.get("concurrent_tasks", 1))),
            ("Hardware", farm.get("hardware", {}).get("preset", "Any Compatible Worker")),
            ("Submission", self.task.get("submission", {}).get("mode", "Shared Storage")),
            ("Validation", "{} error(s), {} warning(s)".format(
                validation.get("errors", 0),
                validation.get("warnings", 0),
            )),
        ]

        for row, (label, value) in enumerate(rows):
            label_widget = QtWidgets.QLabel(label)
            label_widget.setObjectName("FieldLabel")
            value_widget = QtWidgets.QLabel(str(value))
            value_widget.setObjectName("SecondaryText")
            value_widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            grid.addWidget(label_widget, row, 0)
            grid.addWidget(value_widget, row, 1)

        grid.setColumnStretch(1, 1)
        root.addWidget(summary)

        if self.errors:
            error_box = QtWidgets.QLabel(
                "Task validation found:\n• " + "\n• ".join(self.errors)
            )
            error_box.setObjectName("PreviewError")
            error_box.setWordWrap(True)
            root.addWidget(error_box)

        tabs = QtWidgets.QTabWidget()

        json_view = QtWidgets.QPlainTextEdit()
        json_view.setObjectName("JsonPreview")
        json_view.setReadOnly(True)
        json_view.setPlainText(json.dumps(self.task, indent=4, sort_keys=False))
        tabs.addTab(json_view, "Task JSON")

        workers_view = QtWidgets.QPlainTextEdit()
        workers_view.setObjectName("JsonPreview")
        workers_view.setReadOnly(True)
        workers_view.setPlainText(
            "Allowed Workers\n{}\n\nDenied Workers\n{}\n\nJob Dependencies\n{}".format(
                ", ".join(self.task.get("allowed_workers", [])) or "Any compatible worker",
                ", ".join(self.task.get("denied_workers", [])) or "None",
                ", ".join(self.task.get("job_dependencies", [])) or "None",
            )
        )
        tabs.addTab(workers_view, "Targeting")
        root.addWidget(tabs, 1)

        buttons = QtWidgets.QHBoxLayout()

        copy_button = QtWidgets.QPushButton("Copy JSON")
        copy_button.clicked.connect(
            lambda: QtWidgets.QApplication.clipboard().setText(
                json.dumps(self.task, indent=4)
            )
        )

        save_button = QtWidgets.QPushButton("Save JSON As…")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.save_json)

        close_button = QtWidgets.QPushButton("Close")
        close_button.setObjectName("GhostButton")
        close_button.clicked.connect(self.accept)

        buttons.addWidget(copy_button)
        buttons.addWidget(save_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    def save_json(self):
        default_name = "{}_task.json".format(
            self.api.safe_name(self.task.get("job_name", "maya_job"))
        )

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save RenderHive Task",
            os.path.join(self.api.get_worker_tasks_dir(), default_name),
            "JSON Files (*.json)",
        )

        if not path:
            return

        self.api.write_task_json(path, self.task)
        qt_set_status("Task JSON saved: {}".format(path))


# -----------------------------------------------------------------------------
# Main window
# -----------------------------------------------------------------------------


class RenderHiveSubmitter(QtWidgets.QDialog):
    def __init__(self, api, parent=None):
        super(RenderHiveSubmitter, self).__init__(parent or maya_main_window())
        self.api = api
        self.settings = QtCore.QSettings("RenderHive", "MayaSubmitter")
        self.nav_buttons = []
        self.page_stack = None

        self.setObjectName("RenderHiveWindow")
        self.setWindowTitle("RenderHive")
        self.setMinimumSize(680, 600)
        self.resize(720, 690)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(build_stylesheet())

        self.build_ui()
        self.restore_ui_state()
        self.sync_from_scene()

    def closeEvent(self, event):
        global _WINDOW

        self.settings.setValue("geometry_v08", self.saveGeometry())
        if self.page_stack is not None:
            self.settings.setValue("page_v08", self.page_stack.currentIndex())

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
        priority.setRange(0, 100)
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
            "These values are stored now and will be enforced by the backend scheduler later.",
        )
        schedule_grid = QtWidgets.QGridLayout()
        schedule_grid.setHorizontalSpacing(10)
        schedule_grid.setVerticalSpacing(8)

        chunk_size = register("rh_chunk_size", QtWidgets.QSpinBox())
        chunk_size.setRange(1, 10000)
        chunk_size.setValue(10)
        chunk_size.setToolTip("Number of frames assigned to each farm task.")

        machine_limit = register("rh_machine_limit", QtWidgets.QSpinBox())
        machine_limit.setRange(0, 10000)
        machine_limit.setValue(0)
        machine_limit.setSpecialValueText("Unlimited")

        concurrent = register("rh_concurrent_tasks", QtWidgets.QSpinBox())
        concurrent.setRange(1, 64)
        concurrent.setValue(1)

        pool = register("rh_pool", QtWidgets.QComboBox())
        pool.setEditable(True)
        pool.addItems(["Any", "CPU", "GPU", "High Memory", "Preview"])

        start_suspended = register("rh_start_suspended", QtWidgets.QCheckBox("Start job suspended"))
        start_suspended.setToolTip("The backend can queue this job without starting it immediately.")

        schedule_grid.addWidget(LabeledField("Chunk Size", chunk_size), 0, 0)
        schedule_grid.addWidget(LabeledField("Machine Limit", machine_limit), 0, 1)
        schedule_grid.addWidget(LabeledField("Concurrent Tasks / Worker", concurrent), 1, 0)
        schedule_grid.addWidget(LabeledField("Pool / Queue", pool), 1, 1)
        schedule_grid.addWidget(start_suspended, 2, 0, 1, 2)
        schedule_grid.setColumnStretch(0, 1)
        schedule_grid.setColumnStretch(1, 1)
        scheduling.layout.addLayout(schedule_grid)
        body.addWidget(scheduling)

        targeting = Card(
            "Worker Targeting",
            "Limit the job to compatible hardware or named farm machines.",
        )
        target_grid = QtWidgets.QGridLayout()
        target_grid.setHorizontalSpacing(10)
        target_grid.setVerticalSpacing(8)

        hardware = register("rh_hardware_preset", QtWidgets.QComboBox())
        hardware.addItems([
            "Any Compatible Worker",
            "CPU Render",
            "GPU Render",
            "High Memory",
            "Fast Preview",
        ])
        hardware.currentTextChanged.connect(self.apply_hardware_preset)

        min_ram = register("rh_min_ram_gb", QtWidgets.QSpinBox())
        min_ram.setRange(0, 2048)
        min_ram.setSpecialValueText("Any")
        min_ram.setSuffix(" GB")

        min_vram = register("rh_min_vram_gb", QtWidgets.QSpinBox())
        min_vram.setRange(0, 256)
        min_vram.setSpecialValueText("Any")
        min_vram.setSuffix(" GB")

        allowed = register("rh_allowed_workers", QtWidgets.QLineEdit())
        allowed.setPlaceholderText("worker-01, worker-02 (blank = any)")
        denied = register("rh_denied_workers", QtWidgets.QLineEdit())
        denied.setPlaceholderText("worker-test, worker-offline")

        target_grid.addWidget(LabeledField("Hardware Preset", hardware), 0, 0, 1, 2)
        target_grid.addWidget(LabeledField("Minimum RAM", min_ram), 1, 0)
        target_grid.addWidget(LabeledField("Minimum VRAM", min_vram), 1, 1)
        target_grid.addWidget(LabeledField("Allowed Workers", allowed), 2, 0, 1, 2)
        target_grid.addWidget(LabeledField("Denied Workers", denied), 3, 0, 1, 2)
        target_grid.setColumnStretch(0, 1)
        target_grid.setColumnStretch(1, 1)
        targeting.layout.addLayout(target_grid)
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

        action_row = QtWidgets.QHBoxLayout()

        validate = QtWidgets.QPushButton("Validate Scene")
        validate.setObjectName("PrimaryButton")
        validate.clicked.connect(self.validate_scene)

        select_node = QtWidgets.QPushButton("Select Node")
        select_node.clicked.connect(self.api.select_validation_node)

        export = QtWidgets.QPushButton("Export Report")
        export.clicked.connect(self.api.export_validation_report)

        clear = QtWidgets.QPushButton("Clear")
        clear.setObjectName("GhostButton")
        clear.clicked.connect(clear_validation_results)

        action_row.addWidget(validate)
        action_row.addWidget(select_node)
        action_row.addWidget(export)
        action_row.addStretch()
        action_row.addWidget(clear)
        body.addLayout(action_row)

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

        details_card = _WIDGETS.get("validation_details_card")
        if isinstance(details_card, QtWidgets.QWidget):
            details_card.setVisible(True)

        severity = str(result.get("severity", "INFO")).upper()
        category = result.get("category", "General")
        node = result.get("node", "") or "None"
        fixable = "Yes" if result.get("fixable") else "No"
        message = result.get("message", "")

        if isinstance(badge, QtWidgets.QLabel):
            badge.setText(severity)
            badge.setStyleSheet(
                "QLabel { color:%s; border-color:%s; }"
                % (severity_color(severity), severity_color(severity))
            )

        if isinstance(message_label, QtWidgets.QLabel):
            message_label.setText(message)

        if isinstance(meta_label, QtWidgets.QLabel):
            meta_label.setText(
                "Category: {}    Node: {}    Auto-fixable: {}".format(
                    category,
                    node,
                    fixable,
                )
            )

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
            "Recent submission activity and maintenance options.",
        )

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
        activity_log.setMinimumHeight(280)
        activity.layout.addWidget(activity_log)
        body.addWidget(activity, 1)

        maintenance_row = QtWidgets.QHBoxLayout()
        maintenance_row.addStretch()

        menu_button = QtWidgets.QToolButton()
        menu_button.setObjectName("MaintenanceButton")
        menu_button.setText("•••")
        menu_button.setToolTip("Maintenance")
        menu_button.setPopupMode(
            QtWidgets.QToolButton.InstantPopup
        )

        menu = QtWidgets.QMenu(menu_button)

        uninstall_action = menu.addAction(
            "Uninstall RenderHive…"
        )
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

        submit = QtWidgets.QPushButton("Submit Job")
        submit.setObjectName("SubmitButton")
        submit.setMinimumWidth(340)
        submit.setMaximumWidth(420)
        submit.setMinimumHeight(38)
        submit.setToolTip(
            "Submit the current Maya job. "
            "This action will be connected to the backend API."
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

    def apply_hardware_preset(self, preset):
        values = {
            "Any Compatible Worker": (0, 0),
            "CPU Render": (16, 0),
            "GPU Render": (16, 8),
            "High Memory": (64, 0),
            "Fast Preview": (16, 4),
        }.get(str(preset), (0, 0))

        qt_set_int("rh_min_ram_gb", values[0])
        qt_set_int("rh_min_vram_gb", values[1])

        if preset == "Fast Preview":
            qt_set_int("rh_chunk_size", 5)
            qt_set_int("rh_concurrent_tasks", 2)

        self.set_status("Hardware preset updated: {}.".format(preset), level="info")

    def preview_task(self):
        try:
            task = self.api.build_task()
            errors = self.api.validate_task(task)
            dialog = TaskPreviewDialog(
                self.api,
                task,
                errors=errors,
                parent=self,
            )
            dialog.exec_()
        except Exception as error:
            self.set_status("Task review failed: {}".format(error), level="error")
            QtWidgets.QMessageBox.critical(
                self,
                "RenderHive",
                "Could not build the task preview:\n\n{}".format(error),
            )

    def validate_scene(self):
        return self.safe_action("Validating scene", self.api.validate_scene_from_ui)


    def submit_job(self):
        """
        Single submission entry point.

        It currently uses the existing local-worker flow. Replace the callback
        here with the backend API submission when the service is ready.
        """
        return self.safe_action(
            "Submitting job",
            self.api.run_local_worker,
        )

    def run_local_worker(self):
        return self.safe_action("Running local worker", self.api.run_local_worker)

    def sync_from_scene(self, *args):
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

        self.set_status("Synced from scene.", level="info")
        self.append_activity("Scene values synchronized.")

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
