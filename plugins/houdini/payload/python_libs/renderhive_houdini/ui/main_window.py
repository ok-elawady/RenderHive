"""Production RenderHive Houdini submitter."""

from __future__ import absolute_import

import datetime
import json
import os
from dataclasses import replace

from renderhive_houdini.api.client import RenderHiveApiClient
from renderhive_houdini.api.config import load_config
from renderhive_houdini.api.models import normalize_pool, normalize_worker
from renderhive_houdini.adapters.houdini_adapter import HoudiniAdapter
from renderhive_houdini.core.constants import WINDOW_OBJECT_NAME, WINDOW_TITLE
from renderhive_houdini.core.dependency_collector import collect_dependencies
from renderhive_houdini.core.logging_utils import get_logger, log_json
from renderhive_houdini.core.paths import reports_dir, runtime_logs_dir
from renderhive_houdini.core.production_check import run_check
from renderhive_houdini.core.state_store import StateStore
from renderhive_houdini.core.support import create_support_bundle
from renderhive_houdini.core.task_builder import build_api_request, build_task
from renderhive_houdini.integration.maintenance import uninstall_current_profile
from renderhive_houdini.ui.qt_compat import (
    QtCore,
    QtGui,
    QtWidgets,
    Signal,
    WINDOW,
    set_window_flag,
    ALIGN_CENTER,
    ALIGN_RIGHT,
    ALIGN_VCENTER,
    ALIGN_HCENTER,
    MESSAGE_YES,
    dialog_exec,
)
from renderhive_houdini.ui.pages.job_page import JobPage
from renderhive_houdini.ui.pages.render_page import RenderPage
from renderhive_houdini.ui.pages.validation_page import ValidationPage
from renderhive_houdini.ui.pages.tools_page import ToolsPage
from renderhive_houdini.ui.theme import stylesheet
from renderhive_houdini.ui.widgets import apply_status_appearance, StatusChip
from renderhive_houdini.ui.icons import icon_path
from renderhive_houdini.ui.job_dependency_widgets import JobDependencyDialog
from renderhive_houdini.validation.auto_fix import apply_fix, apply_many, requires_confirmation, fix_label
from renderhive_houdini.validation.validator import summary
from renderhive_houdini.version import __version__


class ApiTaskThread(QtCore.QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self._operation = operation

    def run(self):
        try:
            self.succeeded.emit(self._operation())
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QtWidgets.QWidget):
    def __init__(self, parent=None, embedded=False):
        super().__init__(parent)
        self._embedded = bool(embedded)
        self._closing = False
        self._context = None
        self._api_thread = None
        self._api_operation = ""
        self._farm_ready = False
        self._workers = []
        self._pools = []
        self._file_dependencies = []
        self._restoring_state = False
        self._last_validation = []
        self._pending_render_state = None
        self.adapter = HoudiniAdapter()
        self.logger = get_logger("ui")
        self.state_store = StateStore()
        self.window_settings = QtCore.QSettings("RenderHive", "HoudiniSubmitter")

        try:
            self.api_config = load_config()
            self.api_client = RenderHiveApiClient(self.api_config)
            self.api_config_error = ""
        except Exception as error:
            self.api_config = {}
            self.api_client = None
            self.api_config_error = str(error)

        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("{} v{}".format(WINDOW_TITLE, __version__))
        self.setMinimumSize(720, 620)
        self.resize(820, 780)
        self.setStyleSheet(stylesheet())
        if not self._embedded:
            set_window_flag(self, WINDOW, True)

        self._build_ui()
        self._restore_window_state()
        self.refresh_context(scan_nodes=False)
        self._initialize_api_status()

        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setInterval(4000)
        self._autosave_timer.timeout.connect(self.save_scene_state)
        self._autosave_timer.start()
        QtCore.QTimer.singleShot(350, self.sync_backend)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        root.addWidget(self._build_header())

        center = QtWidgets.QHBoxLayout()
        center.setSpacing(8)
        center.addWidget(self._build_sidebar())
        self.page_stack = QtWidgets.QStackedWidget()
        self.job_page = JobPage()
        self.render_page = RenderPage()
        self.validation_page = ValidationPage()
        self.tools_page = ToolsPage()
        for page in (self.job_page, self.render_page, self.validation_page, self.tools_page):
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            scroll.setWidget(page)
            self.page_stack.addWidget(scroll)
        center.addWidget(self.page_stack, 1)
        root.addLayout(center, 1)
        root.addWidget(self._build_footer())

        self.render_page.refreshRequested.connect(self.refresh_render_nodes)
        self.render_page.useSelectedRequested.connect(self.use_selected_render_node)
        self.render_page.renderNodeChanged.connect(self.on_render_node_changed)
        self.render_page.renderSelectionChanged.connect(self.on_render_selection_changed)
        self.job_page.refreshFarmRequested.connect(self.sync_backend)
        self.job_page.browseDependenciesRequested.connect(self.open_job_dependency_browser)
        self.tools_page.retryConnectionRequested.connect(self.sync_backend)
        self.tools_page.openRuntimeLogsRequested.connect(lambda: self._open_folder(runtime_logs_dir()))
        self.tools_page.createSupportBundleRequested.connect(self.create_support_bundle)
        self.tools_page.runProductionCheckRequested.connect(self.run_production_check)
        self.tools_page.resetSceneStateRequested.connect(self.reset_scene_state)
        self.tools_page.uninstallRequested.connect(self.uninstall_plugin)
        self.validation_page.autoFixRequested.connect(self.apply_selected_fix)
        self.validation_page.autoFixAllRequested.connect(self.apply_safe_fixes)
        self.validation_page.selectNodeRequested.connect(self.select_houdini_node)
        self.validation_page.exportRequested.connect(self.export_validation_report)
        self.validation_page.validationCompleted.connect(self._on_validation_completed)
        self.submit_button.clicked.connect(self.submit_job)

    def _build_header(self):
        card = QtWidgets.QFrame(); card.setObjectName("HeaderCard")
        layout = QtWidgets.QHBoxLayout(card); layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(10)
        logo = QtWidgets.QLabel("⬢"); logo.setObjectName("HeaderLogo"); logo.setFixedSize(48, 48); logo.setAlignment(ALIGN_CENTER)
        logo_file = icon_path("renderhive_header_logo.png") or icon_path()
        if logo_file:
            pixmap = QtGui.QPixmap(logo_file)
            if not pixmap.isNull():
                logo.setText(""); logo.setPixmap(pixmap.scaled(44, 44))
        brand = QtWidgets.QVBoxLayout(); brand.setSpacing(0)
        title_row = QtWidgets.QHBoxLayout(); title_row.setSpacing(0)
        main = QtWidgets.QLabel("RENDER"); main.setObjectName("BrandMain")
        accent = QtWidgets.QLabel("HIVE"); accent.setObjectName("BrandAccent")
        title_row.addWidget(main); title_row.addWidget(accent); title_row.addStretch()
        subtitle = QtWidgets.QLabel("HOUDINI RENDER SUBMISSION"); subtitle.setObjectName("BrandSubtitle")
        self.scene_label = QtWidgets.QLabel("Scene: loading…"); self.scene_label.setObjectName("SceneMeta")
        brand.addLayout(title_row); brand.addWidget(subtitle); brand.addWidget(self.scene_label)
        meta = QtWidgets.QVBoxLayout(); meta.setSpacing(5); meta.setAlignment(ALIGN_RIGHT | ALIGN_VCENTER)
        self.version_chip = StatusChip("UI v{}".format(__version__))
        self.renderer_chip = StatusChip("Renderer: Not Set")
        meta.addWidget(self.version_chip); meta.addWidget(self.renderer_chip)
        layout.addWidget(logo); layout.addLayout(brand, 1); layout.addLayout(meta)
        return card

    def _build_sidebar(self):
        frame = QtWidgets.QFrame(); frame.setObjectName("Sidebar"); frame.setFixedWidth(104)
        layout = QtWidgets.QVBoxLayout(frame); layout.setContentsMargins(0, 8, 0, 8); layout.setSpacing(0)
        self.nav_buttons = []
        group = QtWidgets.QButtonGroup(self); group.setExclusive(True)
        for index, label in enumerate(("Job", "Render", "Validation", "Tools")):
            button = QtWidgets.QPushButton(label); button.setObjectName("NavButton"); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=index: self.select_page(page))
            group.addButton(button, index); layout.addWidget(button); self.nav_buttons.append(button)
        layout.addStretch()
        self.houdini_chip = StatusChip("Houdini")
        layout.addWidget(self.houdini_chip, 0, ALIGN_HCENTER)
        self.nav_buttons[0].setChecked(True)
        return frame

    def _build_footer(self):
        card = QtWidgets.QFrame(); card.setObjectName("FooterCard")
        root = QtWidgets.QVBoxLayout(card); root.setContentsMargins(10, 8, 10, 8); root.setSpacing(6)
        self.submit_button = QtWidgets.QPushButton("Submit Job"); self.submit_button.setObjectName("SubmitButton"); self.submit_button.setEnabled(False)
        self.submit_button.setMinimumWidth(340); self.submit_button.setMaximumWidth(440); self.submit_button.setMinimumHeight(38)
        row = QtWidgets.QHBoxLayout(); row.addStretch(); row.addWidget(self.submit_button); row.addStretch(); root.addLayout(row)
        status_row = QtWidgets.QHBoxLayout()
        self.status_dot = QtWidgets.QLabel("●"); self.status_text = QtWidgets.QLabel("Ready")
        status_row.addWidget(self.status_dot); status_row.addWidget(self.status_text); status_row.addStretch(); status_row.addWidget(QtWidgets.QLabel("RenderHive"))
        root.addLayout(status_row)
        return card

    def _restore_window_state(self):
        geometry = self.window_settings.value("geometry")
        if geometry:
            try: self.restoreGeometry(geometry)
            except Exception: pass
        try: page = int(self.window_settings.value("page", 0))
        except Exception: page = 0
        self.select_page(max(0, min(page, self.page_stack.count() - 1)))

    def _save_window_state(self):
        try:
            self.window_settings.setValue("geometry", self.saveGeometry())
            self.window_settings.setValue("page", self.page_stack.currentIndex())
        except Exception:
            pass

    def select_page(self, index):
        self.page_stack.setCurrentIndex(index)
        if 0 <= index < len(self.nav_buttons): self.nav_buttons[index].setChecked(True)

    def _set_busy(self, busy):
        # Connection/submission state is communicated by the footer status text
        # and Submit button label.  Keep the footer clean instead of showing an
        # indeterminate progress strip that does not represent real progress.
        self._busy = bool(busy)

    def _set_status(self, text, level="good"):
        self.status_text.setText(str(text)); apply_status_appearance(self.status_text, level); apply_status_appearance(self.status_dot, level)
        if hasattr(self, "tools_page"): self.tools_page.append_activity(text)
        log_json(self.logger, "info", "ui_status", {"message": text, "level": level})

    def _initialize_api_status(self):
        source = self.api_config.get("_config_source", "Unavailable") if self.api_config else "Unavailable"
        token = str((self.api_config.get("auth") or {}).get("token") or "") if self.api_config else ""
        self.tools_page.set_connection_config(source, bool(token))
        if self.api_config_error:
            self.tools_page.set_connection_error(self.api_config_error, "Now"); self.job_page.set_backend_error(self.api_config_error)

    def _scene_state_payload(self):
        return {"schema_version": 3, "job": self.job_page.state_values(), "render": self.render_page.state_values()}

    def save_scene_state(self):
        if self._restoring_state or self._context is None:
            return
        try:
            self.state_store.save(self._context.hip_path, self._scene_state_payload(), self._context.hip_name)
        except Exception as error:
            self.logger.warning("Could not save scene state: %s", error)

    def _restore_scene_state(self):
        if self._context is None:
            return
        data = self.state_store.load(self._context.hip_path, self._context.hip_name)
        if not data:
            return
        self._restoring_state = True
        try:
            self.job_page.apply_state(data.get("job") or {})
            render_state = data.get("render") or {}
            self._pending_render_state = render_state
            node_path = str(render_state.get("render_node_path") or "")
            selected_paths = [str(value or "").strip() for value in render_state.get("selected_render_node_paths") or [] if str(value or "").strip()]
            if node_path and node_path not in selected_paths:
                selected_paths.insert(0, node_path)
            if selected_paths:
                QtCore.QTimer.singleShot(120, lambda: self._restore_render_nodes(selected_paths, node_path, render_state))
            else:
                self.render_page.apply_state(render_state)
        finally:
            self._restoring_state = False

    def _restore_render_nodes(self, node_paths, primary_path, render_state):
        if self._closing or self._context is None:
            return
        nodes = []
        seen = set()
        for path in node_paths or []:
            clean = str(path or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            try:
                node = self.adapter.render_node(clean)
            except Exception:
                node = None
            if node is not None:
                nodes.append(node)
        if nodes:
            preferred = primary_path if any(node.path == primary_path for node in nodes) else nodes[0].path
            self.render_page.set_nodes(nodes, preferred_path=preferred)
        self.render_page.apply_state(render_state)
        self.on_render_selection_changed()

    def _restore_render_node(self, node_path, render_state):
        # Compatibility helper for older callback paths.
        self._restore_render_nodes([node_path], node_path, render_state)

    def refresh_context(self, scan_nodes=False):
        if self._closing: return
        try: context = self.adapter.scene_context()
        except Exception as error:
            self.scene_label.setText("Scene: unavailable"); self._set_status("Scene context failed: {}".format(error), "error"); return
        first_context = self._context is None
        previous_key = str(self._context.hip_path or "").strip().lower() if self._context else ""
        current_key = str(context.hip_path or "").strip().lower()
        scene_changed = bool(first_context or current_key != previous_key)
        if self._context is not None and scene_changed:
            self.save_scene_state()
        self._context = context
        self.job_page.set_context(context, force_identity=scene_changed)
        self.render_page.set_context(context, reset_scene=scene_changed)
        self.validation_page.set_context(context)
        if scene_changed:
            self._file_dependencies = []
            self.job_page.clear_job_dependencies()
            self.validation_page.set_dependencies([])
            self.validation_page.set_render_nodes([])
            self.validation_page.clear_results()
            self.renderer_chip.setText("Renderer: Not Set")
            self._restore_scene_state()
        self.scene_label.setText("Scene: {}{}".format(context.scene_name or "Untitled", " *" if context.has_unsaved_changes else ""))
        self.houdini_chip.setText("Houdini {}".format(".".join(context.houdini_version.split(".")[:2])))
        if scan_nodes: self.refresh_render_nodes()
        elif not self.render_page.has_nodes():
            self.render_page.show_scan_prompt(); self._set_status("Scene information loaded automatically.", "good")
        self._update_submit_enabled()

    def refresh_render_nodes(self):
        preferred = self.render_page.current_node_path(); self._set_status("Scanning render nodes…", "info")
        try: QtWidgets.QApplication.processEvents()
        except Exception: pass
        try: nodes = self.adapter.render_nodes()
        except Exception as error:
            self.render_page.set_nodes([], preferred_path=""); self._set_status("Render-node discovery failed: {}".format(error), "error"); return
        self.render_page.set_nodes(nodes, preferred_path=preferred)
        self._set_status("{} render node(s) detected.".format(len(nodes)), "good" if nodes else "warning")

    def use_selected_render_node(self):
        try:
            node_info = self.adapter.selected_render_node()
        except Exception as error:
            self._set_status("Could not read selected node: {}".format(error), "error")
            return
        if node_info is None:
            self._set_status("Select an executable ROP or Solaris render node.", "warning")
            return
        nodes = self.render_page.available_node_infos()
        mapping = {str(node.path): node for node in nodes}
        mapping[str(node_info.path)] = node_info
        merged = list(mapping.values())
        checked = self.render_page.selected_node_paths()
        if node_info.path not in checked:
            checked.append(node_info.path)
        self.render_page.set_nodes(merged, preferred_path=node_info.path)
        self.render_page.set_selected_node_paths(checked)
        self._set_status("Render source added: {}.".format(node_info.path), "good")

    def on_render_node_changed(self, node_info):
        if node_info is not None and not getattr(node_info, "details_loaded", True):
            try:
                detailed = self.adapter.render_node(node_info.path)
            except Exception as error:
                self._set_status("Could not inspect {}: {}".format(node_info.path, error), "warning")
                detailed = None
            if detailed is not None:
                self.render_page.replace_current_node(detailed)
                return
        self.renderer_chip.setText("Renderer: {}".format(node_info.renderer if node_info is not None else "Not Set"))
        self.on_render_selection_changed()

    def on_render_selection_changed(self):
        nodes = self.render_page.selected_node_infos()
        self.validation_page.set_render_nodes(nodes)
        self.job_page.set_render_requirements(
            getattr(self._context, "houdini_version", "") if self._context else "",
            nodes,
        )
        self._update_submit_enabled()

    def _update_submit_enabled(self):
        enabled = bool(
            self.api_client is not None
            and self.api_config.get("enabled", True)
            and self.render_page.selected_node_infos()
            and self._api_operation != "submit"
        )
        self.submit_button.setEnabled(enabled)

    def _start_api_operation(self, name, operation, success_callback):
        if self._api_thread is not None and self._api_thread.isRunning():
            self._set_status("Another backend operation is already running.", "warning"); return False
        self._api_operation = str(name); self._api_thread = ApiTaskThread(operation)
        self._api_thread.succeeded.connect(success_callback); self._api_thread.failed.connect(self._on_api_failed); self._api_thread.finished.connect(self._on_api_finished)
        self._api_thread.start(); self._set_busy(True); self._update_submit_enabled(); return True

    def sync_backend(self):
        if self.api_client is None:
            message = self.api_config_error or "Backend configuration is unavailable."
            self.job_page.set_backend_error(message); self.tools_page.set_connection_error(message, datetime.datetime.now().strftime("%H:%M")); self._set_status(message, "error"); return
        if not self.api_config.get("enabled", True):
            message = "RenderHive API is disabled by managed configuration."
            self.job_page.set_backend_error(message); self.tools_page.set_connection_error(message, datetime.datetime.now().strftime("%H:%M")); self._set_status(message, "warning"); return
        self.job_page.set_syncing(True); self.tools_page.set_connecting(); self._set_status("Connecting to RenderHive…", "info")
        def operation():
            self.api_client.test_connection()
            return {"workers": [normalize_worker(item) for item in self.api_client.list_workers()], "pools": [normalize_pool(item) for item in self.api_client.list_pools()]}
        self._start_api_operation("sync", operation, self._on_farm_synced)

    def _on_farm_synced(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        checked_at = datetime.datetime.now().strftime("%H:%M")
        self._workers = payload.get("workers") or []
        self._pools = payload.get("pools") or []
        self._farm_ready = True
        self.job_page.set_farm_data(self._workers, self._pools, checked_at)
        self.job_page.set_render_requirements(
            getattr(self._context, "houdini_version", "") if self._context else "",
            self.render_page.selected_node_infos(),
        )
        self.tools_page.set_connected(checked_at)
        self._set_status("Backend connected: {} worker(s), {} pool(s).".format(len(self._workers), len(self._pools)), "good")

    def open_job_dependency_browser(self):
        if self.api_client is None or not self.api_config.get("enabled", True):
            self._set_status("RenderHive backend is unavailable.", "warning")
            return
        self.job_page.browse_dependencies.setEnabled(False)
        self._set_status("Loading RenderHive jobs…", "info")
        self._start_api_operation("dependencies", self.api_client.list_all_jobs, self._on_dependency_jobs_loaded)

    def _on_dependency_jobs_loaded(self, jobs):
        jobs = [dict(item) for item in (jobs or []) if isinstance(item, dict)]
        dialog = JobDependencyDialog(jobs, self.job_page.selected_job_dependency_ids(), parent=self)
        if dialog_exec(dialog):
            self.job_page.set_job_dependencies(dialog.selected_ids(), dialog.selected_records())
            self.save_scene_state()
            self._set_status("{} job dependency/dependencies selected.".format(len(dialog.selected_ids())), "good")
        else:
            self._set_status("Job dependency selection unchanged.", "neutral")

    def _apply_focused_overrides(self, node):
        if node is None:
            return None
        values = self.render_page.submission_values()
        output_path = values.get("output_path")
        if output_path in ("Not Set", "—"):
            output_path = ""
        return replace(
            node,
            renderer=values.get("renderer") or node.renderer,
            camera=values.get("camera") or node.camera,
            output_path=output_path or node.output_path,
            frame_start=float(values.get("frame_start")),
            frame_end=float(values.get("frame_end")),
            frame_step=float(values.get("frame_step")),
            resolution_width=int(values.get("width") or node.resolution_width or 0),
            resolution_height=int(values.get("height") or node.resolution_height or 0),
            camera_override=bool(values.get("camera_override")),
            renderer_override=bool(values.get("renderer_override")),
            output_override=bool(values.get("output_override")),
            resolution_override=bool(values.get("resolution_override")),
        )

    def _node_for_submission(self):
        return self._apply_focused_overrides(self.render_page.current_node_info())

    def _selected_submission_nodes(self):
        selected_paths = self.render_page.selected_node_paths()
        current_path = self.render_page.current_node_path()
        nodes = []
        seen = set()
        for path in selected_paths:
            clean = str(path or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            node = next((item for item in self.render_page.available_node_infos() if str(item.path) == clean), None)
            if node is None or not getattr(node, "details_loaded", True):
                try:
                    detailed = self.adapter.render_node(clean)
                except Exception:
                    detailed = None
                if detailed is not None:
                    node = detailed
            if node is None:
                continue
            if clean == current_path:
                node = self._apply_focused_overrides(node)
            nodes.append(node)
        return nodes

    def _farm_validation_context(self, render_nodes=None):
        targeting = self.job_page.pool_targeting()
        settings = self.job_page.job_settings()
        return {
            "backend_online": self._farm_ready,
            "workers": self._workers,
            "pools": self._pools,
            "pool_strategy": targeting.get("strategy") or "all",
            "selected_pool_ids": targeting.get("selected_pool_ids") or [],
            "effective_pool_ids": targeting.get("effective_pool_ids") or [],
            "min_cores": settings.get("min_cores") or 0,
            "min_memory_mb": settings.get("min_memory_mb") or 0,
            "min_gpus": settings.get("min_gpus") or 0,
            "job_dependencies": settings.get("job_dependencies") or [],
            "render_nodes": list(render_nodes or []),
        }

    def run_full_validation(self):
        self.refresh_context(scan_nodes=False)
        nodes = self._selected_submission_nodes()
        try:
            self._file_dependencies = collect_dependencies()
        except Exception as error:
            self._file_dependencies = []
            self._set_status("File dependency collection warning: {}".format(error), "warning")
        self.validation_page.set_context(self._context)
        self.validation_page.set_render_nodes(nodes)
        self.validation_page.set_dependencies(self._file_dependencies)
        self.validation_page.set_farm_context(self._farm_validation_context(nodes))
        return self.validation_page.run_validation()

    def submit_job(self):
        results = self.run_full_validation()
        errors = [item for item in results if item.blocks_submission]
        if errors:
            self.select_page(2)
            self._set_status("Submission blocked by {} validation error(s).".format(len(errors)), "error")
            QtWidgets.QMessageBox.warning(self, "RenderHive Validation", "Fix the validation errors before submitting the job.")
            return
        settings = self.job_page.job_settings()
        targeting = self.job_page.pool_targeting()
        if targeting.get("strategy") == "selected_only" and not targeting.get("selected_pool_ids"):
            self._set_status("Select at least one worker pool.", "warning")
            return
        nodes = self._selected_submission_nodes()
        if not nodes:
            self._set_status("Select at least one Houdini render source.", "warning")
            return
        try:
            task = build_task(
                self._context,
                nodes[0],
                job_name=settings.get("job_name"),
                project_name=settings.get("project_name"),
                priority=settings.get("priority"),
                department=settings.get("department"),
                comment=settings.get("comment"),
                chunk_size=settings.get("chunk_size"),
                concurrent_tasks=settings.get("concurrent_tasks"),
                pool_targeting=targeting,
                retry_count=settings.get("retry_count"),
                timeout_seconds=settings.get("timeout_seconds"),
                min_cores=settings.get("min_cores"),
                min_memory_mb=settings.get("min_memory_mb"),
                min_gpus=settings.get("min_gpus"),
                dependencies=settings.get("job_dependencies") or [],
                render_nodes=nodes,
            )
            request_payload = build_api_request(task, self.api_config)
        except Exception as error:
            self._set_status("Could not prepare the job: {}".format(error), "error")
            QtWidgets.QMessageBox.critical(self, "RenderHive", str(error))
            return
        self.save_scene_state()
        self.submit_button.setText("Submitting…")
        self._set_status("Submitting {} Houdini render source(s) to RenderHive…".format(len(nodes)), "info")
        log_json(get_logger("submission"), "info", "submit_request", request_payload)
        self._start_api_operation("submit", lambda: self.api_client.submit_job(request_payload), self._on_job_submitted)

    def _on_job_submitted(self, response):
        response = response if isinstance(response, dict) else {}
        job_id = response.get("id") or response.get("job_id") or response.get("uid") or "Not returned"
        state = response.get("state") or response.get("status") or "PENDING"
        visible_name = response.get("visible_name") or self.job_page.job_name.text().strip()
        log_json(get_logger("submission"), "info", "submit_response", response)
        self._set_status("Job submitted: {} ({})".format(visible_name, state), "good")
        QtWidgets.QMessageBox.information(self, "RenderHive Job Submitted", "Job: {}\nStatus: {}\nReference: {}".format(visible_name, state, job_id))

    def _on_api_failed(self, message):
        checked_at = datetime.datetime.now().strftime("%H:%M")
        if self._api_operation == "sync":
            self._farm_ready = False
            self.job_page.set_backend_error(message)
            self.tools_page.set_connection_error(message, checked_at)
        self._set_status("Backend operation failed: {}".format(message), "error")
        if self._api_operation == "submit":
            QtWidgets.QMessageBox.critical(self, "RenderHive Submission Failed", str(message))

    def _on_api_finished(self):
        self.job_page.set_syncing(False)
        self.job_page.browse_dependencies.setEnabled(True)
        self.submit_button.setText("Submit Job")
        self._set_busy(False)
        if self._api_thread is not None:
            self._api_thread.deleteLater(); self._api_thread = None
        self._api_operation = ""; self._update_submit_enabled()

    def _on_validation_completed(self, results):
        self._last_validation = list(results or [])
        counts = summary(self._last_validation)
        if counts.get("ERROR"): self._set_status("Validation found {} error(s).".format(counts["ERROR"]), "error")
        elif counts.get("WARNING"): self._set_status("Validation passed with {} warning(s).".format(counts["WARNING"]), "warning")
        else: self._set_status("Validation passed.", "good")

    def apply_selected_fix(self, result):
        if requires_confirmation(result):
            answer = QtWidgets.QMessageBox.question(self, "RenderHive Auto Fix", "Apply '{}'?".format(fix_label(result)))
            if answer != MESSAGE_YES: return
        success, message = apply_fix(result)
        self._set_status(message, "good" if success else "error")
        if success:
            render_state = self.render_page.state_values()
            selected_paths = list(render_state.get("selected_render_node_paths") or [])
            primary_path = self.render_page.current_node_path()
            if primary_path and primary_path not in selected_paths:
                selected_paths.insert(0, primary_path)
            self.refresh_context(scan_nodes=False)
            if selected_paths:
                self._restore_render_nodes(selected_paths, primary_path, render_state)
            self.run_full_validation()

    def apply_safe_fixes(self, results):
        values = list(results or [])
        if not values: return
        answer = QtWidgets.QMessageBox.question(self, "RenderHive Auto Fix", "Apply {} safe fix(es)?".format(len(values)))
        if answer != MESSAGE_YES: return
        report = apply_many(values)
        self._set_status("Applied {} fix(es); {} failed.".format(report["success_count"], report["failure_count"]), "good" if not report["failure_count"] else "warning")
        self.refresh_context(scan_nodes=False); self.run_full_validation()

    def select_houdini_node(self, path):
        try:
            import hou
            node = hou.node(str(path or ""))
            if node is None: raise RuntimeError("Node no longer exists.")
            node.setSelected(True, clear_all_selected=True)
            pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
            if pane is not None: pane.setCurrentNode(node)
            self._set_status("Selected node: {}".format(path), "good")
        except Exception as error:
            self._set_status("Could not select node: {}".format(error), "error")

    def export_validation_report(self, results):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(reports_dir(), "houdini_validation_{}.json".format(stamp))
        payload = {
            "plugin_version": __version__,
            "scene": getattr(self._context, "__dict__", {}) if self._context else {},
            "summary": summary(results),
            "results": [item.as_dict() for item in results or []],
        }
        with open(path, "w", encoding="utf-8") as handle: json.dump(payload, handle, indent=2, default=str)
        self._set_status("Validation report exported: {}".format(path), "good")
        self._open_folder(os.path.dirname(path))

    def _open_folder(self, path):
        try:
            if not os.path.isdir(path): os.makedirs(path)
            if hasattr(os, "startfile"): os.startfile(path)
            else:
                import subprocess, sys
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
        except Exception as error:
            self._set_status("Could not open folder: {}".format(error), "error")

    def create_support_bundle(self):
        try:
            check = run_check(self._context, self.api_config, self.state_store)
            path = create_support_bundle(self.api_config, self._context, self._last_validation, check, {"workers": len(self._workers), "pools": len(self._pools)})
            self._set_status("Support bundle created: {}".format(path), "good")
            self._open_folder(os.path.dirname(path))
        except Exception as error:
            self._set_status("Support bundle failed: {}".format(error), "error")

    def run_production_check(self):
        report = run_check(self._context, self.api_config, self.state_store)
        lines = ["{} {} — {}".format("✓" if item["passed"] else "✗", item["name"], item["details"]) for item in report["checks"]]
        QtWidgets.QMessageBox.information(self, "RenderHive Production Check", "Passed: {}\nFailed: {}\n\n{}".format(report["passed_count"], report["failed_count"], "\n".join(lines)))
        self._set_status("Production check: {} passed, {} failed.".format(report["passed_count"], report["failed_count"]), "good" if report["passed"] else "warning")

    def reset_scene_state(self):
        if self._context is None: return
        answer = QtWidgets.QMessageBox.question(self, "Reset Scene Settings", "Reset saved RenderHive settings for the current HIP file?")
        if answer != MESSAGE_YES: return
        self.state_store.delete(self._context.hip_path, self._context.hip_name)
        self.job_page.clear_job_dependencies()
        self.job_page.set_context(self._context, force_identity=True)
        self.render_page.set_context(self._context, reset_scene=True)
        self.validation_page.set_render_nodes([])
        self.validation_page.set_dependencies([])
        self.validation_page.clear_results()
        self._set_status("Current scene settings were reset.", "good")

    def uninstall_plugin(self):
        answer = QtWidgets.QMessageBox.question(self, "Uninstall RenderHive", "Disable RenderHive for this Houdini profile? Houdini must be restarted.")
        if answer != MESSAGE_YES: return
        success, message = uninstall_current_profile()
        QtWidgets.QMessageBox.information(self, "RenderHive", message) if success else QtWidgets.QMessageBox.critical(self, "RenderHive", message)

    def closeEvent(self, event):
        self.save_scene_state(); self._save_window_state()
        if self._embedded:
            event.accept(); return
        self.hide(); event.ignore()

    def shutdown(self):
        self._closing = True
        self.save_scene_state(); self._save_window_state()
        if hasattr(self, "_autosave_timer"): self._autosave_timer.stop()
