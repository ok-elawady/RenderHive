from __future__ import print_function

import datetime
import hashlib
import importlib
import json
import os
import sys

from .qt_compat import QtCore, QtGui, QtWidgets, wrapInstance, isValid

import maya.OpenMayaUI as omui
import maya.cmds as cmds

from .qt_theme import COLORS, build_stylesheet
from .runtime_registry import WIDGETS
from .controllers.api_controller import ApiControllerMixin
from .controllers.targeting_controller import TargetingControllerMixin
from .controllers.dependency_controller import DependencyControllerMixin
from .common_widgets import (
    PageHeader,
)
from .targeting_widgets import RenderLayerSelector
from .pages.job_page import build_job_page as build_job_page_view
from .pages.render_page import build_render_page as build_render_page_view
from .pages.validation_page import build_checks_page as build_checks_page_view
from .pages.tools_page import build_more_page as build_more_page_view
from core.state_store import StateStore
from api.version import PLUGIN_VERSION


WINDOW_OBJECT_NAME = "RenderHiveQtSubmitter"
UI_VERSION = PLUGIN_VERSION
_WINDOW = None
_API = None
_WIDGETS = WIDGETS
_BACKGROUND_THREADS = set()


def _release_background_thread(thread):
    """Release a detached worker only after Qt reports it has finished."""
    try:
        _BACKGROUND_THREADS.discard(thread)
        thread.deleteLater()
    except Exception:
        pass



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





def install_api_bridge(api):
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
    api.refresh_validation_filters = refresh_validation_filters
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

    task_builder = importlib.import_module("submission.task_builder")
    importlib.reload(task_builder)
    task_validation = importlib.import_module("submission.task_validation")
    importlib.reload(task_validation)

    api.build_task = lambda: task_builder.build_task(
        api,
        window=_WINDOW,
        widgets=_WIDGETS,
        validation_report=getattr(api, "VALIDATION_REPORT", {}) or {},
    )
    api.validate_task = task_validation.validate_task


# -----------------------------------------------------------------------------
# Reusable widgets
# -----------------------------------------------------------------------------





















































# -----------------------------------------------------------------------------
# Task review dialog
# -----------------------------------------------------------------------------




# -----------------------------------------------------------------------------
# Main window
# -----------------------------------------------------------------------------


class RenderHiveSubmitter(
    QtWidgets.QDialog,
    ApiControllerMixin,
    TargetingControllerMixin,
    DependencyControllerMixin,
):
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
        self.job_dependency_thread = None
        self.job_dependency_jobs = []
        self.job_dependency_records = {}
        self.worker_target_last_sync = None
        self.worker_target_has_sync = False
        self.worker_target_sync_error = ""
        self.api_test_thread = None
        self.api_submit_thread = None
        self._is_closing = False
        self.worker_pools = self.load_worker_pools()
        self.api_pools = []

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

        self.startup_timer = QtCore.QTimer(self)
        self.startup_timer.setSingleShot(True)
        self.startup_timer.timeout.connect(
            self.test_api_connection
        )

        self.setObjectName("RenderHiveWindow")
        self.setWindowTitle("RenderHive")
        self.setMinimumSize(720, 620)
        self.resize(760, 720)
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
        self.startup_timer.start(0)

    def _detach_running_thread(self, attribute_name):
        thread = getattr(self, attribute_name, None)
        if thread is None:
            return

        try:
            if thread.isRunning():
                thread.requestInterruption()

                for signal_name in ("succeeded", "failed", "finished"):
                    signal = getattr(thread, signal_name, None)
                    if signal is not None:
                        try:
                            signal.disconnect()
                        except Exception:
                            pass

                thread.setParent(None)
                _BACKGROUND_THREADS.add(thread)
                thread.finished.connect(
                    lambda current=thread: _release_background_thread(current)
                )
            else:
                thread.deleteLater()
        except Exception:
            pass

        setattr(self, attribute_name, None)

    def closeEvent(self, event):
        global _WINDOW, _WIDGETS

        if self._is_closing:
            event.accept()
            return

        self._is_closing = True

        for timer in (
            self.startup_timer,
            self.scene_state_timer,
            self.scene_state_save_timer,
            self.worker_stale_timer,
        ):
            try:
                timer.stop()
            except Exception:
                pass

        for attribute_name in (
            "worker_sync_thread",
            "job_dependency_thread",
            "api_test_thread",
            "api_submit_thread",
        ):
            self._detach_running_thread(attribute_name)

        try:
            self.settings.setValue("geometry_v08", self.saveGeometry())
            if self.page_stack is not None:
                self.settings.setValue(
                    "page_v08",
                    self.page_stack.currentIndex(),
                )
            self.save_scene_state(force=True)
            self.save_worker_pools()
        except Exception:
            pass

        _WIDGETS.clear()
        _WINDOW = None
        event.accept()
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
                "rh_concurrent_tasks",
                "rh_minimum_cores",
                "rh_minimum_ram_gb",
                "rh_minimum_gpus",
                "rh_retry_count",
                "rh_timeout_minutes",
                "rh_frame_start",
                "rh_frame_end",
                "rh_frame_step",
                "rh_frame_padding",
                "rh_width",
                "rh_height",
            ),
            "boolean": (),
            "option": (
                "rh_pool_strategy",
                "rh_renderer",
                "rh_camera",
                "rh_image_format",
                "render_preset",
            ),
            "list": (
                "rh_selected_pools",
                "rh_excluded_pools",
                "rh_render_layers",
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
            for name,value in (state.get("text") or {}).items():
                widget=_WIDGETS.get(name)
                if isinstance(widget,QtWidgets.QLineEdit): widget.setText(str(value or ""))
            for name,value in (state.get("integer") or {}).items():
                widget=_WIDGETS.get(name)
                if isinstance(widget,QtWidgets.QSpinBox):
                    try: widget.setValue(int(value))
                    except Exception: pass
            for name,value in (state.get("boolean") or {}).items():
                widget=_WIDGETS.get(name)
                if isinstance(widget,QtWidgets.QCheckBox): widget.setChecked(bool(value))

            options=state.get("option") or {}
            lists=state.get("list") or {}
            for name,value in options.items():
                if name in ("rh_pool","rh_worker_assignment_mode"): continue
                widget=_WIDGETS.get(name); value=str(value or "")
                if isinstance(widget,QtWidgets.QComboBox):
                    index=widget.findText(value)
                    if index>=0: widget.setCurrentIndex(index)
                    elif widget.isEditable() and value: widget.setEditText(value)
                elif hasattr(widget,"setCurrentText"):
                    try: widget.setCurrentText(value)
                    except Exception: pass

            if "rh_render_layers" in lists:
                qt_set_list(
                    "rh_render_layers",
                    lists.get("rh_render_layers") or [],
                )

            strategy=str(options.get("rh_pool_strategy") or "")
            selected=list(lists.get("rh_selected_pools") or [])
            excluded=list(lists.get("rh_excluded_pools") or [])
            if not strategy:
                old_pool=str(options.get("rh_pool") or "All Workers")
                if old_pool and old_pool not in ("All","All Workers"):
                    strategy="Selected Pools Only"
                    if not selected: selected=[old_pool]
                else:
                    strategy="All Pools"
            widget=_WIDGETS.get("rh_pool_strategy")
            if hasattr(widget,"setCurrentText"): widget.setCurrentText(strategy)
            self._pending_worker_scene_state={
                "rh_selected_pools":selected,
                "rh_excluded_pools":excluded,
            }
            self.apply_pending_pool_scene_state()
            self.on_pool_strategy_changed(self.pool_assignment_strategy())
            return True
        finally:
            self._scene_state_restoring=False

    def apply_pending_pool_scene_state(self):
        if not self._pending_worker_scene_state:
            return
        for name in ("rh_selected_pools","rh_excluded_pools"):
            if name in self._pending_worker_scene_state:
                qt_set_list(name,self._pending_worker_scene_state.get(name) or [])

        self._pending_worker_scene_state = {}

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

    def open_runtime_logs_folder(self):
        provider = getattr(self.api, "get_runtime_log_folder", None)
        if not callable(provider):
            return
        folder = provider()
        try:
            if hasattr(os, "startfile"):
                os.startfile(folder)
            else:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
            self.append_activity("Opened runtime logs: {}".format(folder))
        except Exception as error:
            QtWidgets.QMessageBox.warning(self, "RenderHive", "Could not open runtime logs:\n\n{}".format(error))

    def create_support_bundle(self):
        provider = getattr(self.api, "create_diagnostics_bundle", None)
        if not callable(provider):
            return
        try:
            path = provider()
            self.append_activity("Created support bundle: {}".format(path))
            QtWidgets.QMessageBox.information(
                self,
                "RenderHive Support Bundle",
                "Support bundle created successfully:\n\n{}".format(path),
            )
        except Exception as error:
            QtWidgets.QMessageBox.warning(self, "RenderHive", "Could not create support bundle:\n\n{}".format(error))

    def run_production_check(self):
        provider = getattr(self.api, "get_production_health_report", None)
        if not callable(provider):
            return
        try:
            report = provider()
            failed = [item for item in report.get("checks", []) if not item.get("ok")]
            lines = [
                "Plugin: v{}".format(report.get("plugin_version", "—")),
                "Overall: {}".format("PASS" if report.get("ok") else "ATTENTION REQUIRED"),
                "",
            ]
            for item in report.get("checks", []):
                lines.append("{}  {}".format("PASS" if item.get("ok") else "FAIL", item.get("name", "check")))
            self.append_activity("Production check completed: {}".format("PASS" if not failed else "{} issue(s)".format(len(failed))))
            QtWidgets.QMessageBox.information(self, "RenderHive Production Check", "\n".join(lines))
        except Exception as error:
            QtWidgets.QMessageBox.warning(self, "RenderHive", "Production check failed:\n\n{}".format(error))

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

        subtitle = QtWidgets.QLabel("MAYA RENDER SUBMISSION")
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
        frame.setFixedWidth(104)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        button_group = QtWidgets.QButtonGroup(self)
        button_group.setExclusive(True)

        pages = [
            "Job",
            "Render",
            "Validation",
            "Tools",
        ]

        for index, title in enumerate(pages):
            button = QtWidgets.QPushButton(title)
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
        return build_job_page_view(self, register)

    # ------------------------------------------------------------------
    # Render page
    # ------------------------------------------------------------------

    def build_render_page(self):
        return build_render_page_view(self, register)

    # ------------------------------------------------------------------
    # Validation page
    # ------------------------------------------------------------------

    def build_checks_page(self):
        return build_checks_page_view(self, register)

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
        return build_more_page_view(self, register)

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

    def validate_scene(self):
        return self.safe_action("Validating scene", self.api.validate_scene_from_ui)



    def refresh_render_layers(self, *args, **kwargs):
        record_activity = bool(kwargs.get("record_activity", True))
        selector = _WIDGETS.get("rh_render_layers")
        if not isinstance(selector, RenderLayerSelector):
            return []

        try:
            records = self.api.get_render_layers() or []
        except Exception as error:
            records = []
            if record_activity:
                self.set_status(
                    "Could not read Maya render layers.",
                    level="warning",
                )
                self.append_activity(
                    "Render layer refresh failed: {}".format(error)
                )

        selector.set_layers(records)

        if record_activity and records:
            self.set_status(
                "Render layers refreshed: {} selected.".format(
                    len(selector.selected_values())
                ),
                level="info",
            )
            self.append_activity(
                "Detected {} Maya render layer{}.".format(
                    len(records),
                    "" if len(records) == 1 else "s",
                )
            )

        if self._active_scene_state_key and not self._scene_state_restoring:
            self.save_scene_state()
        return records

    def on_render_layer_selection_changed(self):
        selector = _WIDGETS.get("rh_render_layers")
        if not isinstance(selector, RenderLayerSelector):
            return

        count = len(selector.selected_values())
        if count:
            self.set_status(
                "{} render layer{} selected.".format(
                    count,
                    "" if count == 1 else "s",
                ),
                level="info",
            )
        else:
            self.set_status(
                "Select at least one render layer.",
                level="warning",
            )

        if self._active_scene_state_key and not self._scene_state_restoring:
            self.save_scene_state()

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

        scene_renderer = self.api.get_current_renderer()
        renderer_combo = _WIDGETS.get("rh_renderer")
        if isinstance(renderer_combo, QtWidgets.QComboBox):
            index = renderer_combo.findText("arnold")
            if index >= 0:
                renderer_combo.setCurrentIndex(index)

        qt_rebuild_camera_menu()
        self.refresh_render_layers(record_activity=False)

        header_scene = _WIDGETS.get("header_scene")
        if isinstance(header_scene, QtWidgets.QLabel):
            header_scene.setText(
                "Scene: {}".format(self.api.get_scene_name() or "Untitled")
            )

        header_renderer = _WIDGETS.get("header_renderer")
        if isinstance(header_renderer, QtWidgets.QLabel):
            header_renderer.setText(
                "Renderer: Arnold"
                if str(scene_renderer or "").lower() == "arnold"
                else "Renderer: Arnold required"
            )

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
    install_api_bridge(api)

    if _WINDOW is not None:
        try:
            if isValid(_WINDOW) and not _WINDOW._is_closing:
                if _WINDOW.isMinimized():
                    _WINDOW.showNormal()
                else:
                    _WINDOW.show()
                _WINDOW.raise_()
                _WINDOW.activateWindow()
                return _WINDOW
        except Exception:
            _WINDOW = None

    _WIDGETS.clear()
    _WINDOW = RenderHiveSubmitter(api)
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW
