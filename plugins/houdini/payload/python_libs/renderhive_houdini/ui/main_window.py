"""RenderHive Houdini submitter with managed backend integration."""

from __future__ import absolute_import

import datetime
from dataclasses import replace

from renderhive_houdini.api.client import RenderHiveApiClient
from renderhive_houdini.api.config import load_config
from renderhive_houdini.api.models import normalize_pool, normalize_worker
from renderhive_houdini.adapters.houdini_adapter import HoudiniAdapter
from renderhive_houdini.core.constants import WINDOW_OBJECT_NAME, WINDOW_TITLE
from renderhive_houdini.core.task_builder import build_api_request, build_task
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
)
from renderhive_houdini.ui.pages.job_page import JobPage
from renderhive_houdini.ui.pages.render_page import RenderPage
from renderhive_houdini.ui.pages.validation_page import ValidationPage
from renderhive_houdini.ui.pages.tools_page import ToolsPage
from renderhive_houdini.ui.theme import stylesheet
from renderhive_houdini.ui.widgets import apply_status_appearance, StatusChip
from renderhive_houdini.ui.icons import icon_path
from renderhive_houdini.validation.validator import validate
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
        self.adapter = HoudiniAdapter()

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
        self.setMinimumSize(760, 680)
        self.resize(900, 860)
        self.setStyleSheet(stylesheet())
        if not self._embedded:
            set_window_flag(self, WINDOW, True)

        self._build_ui()
        self.refresh_context(scan_nodes=False)
        self._initialize_api_status()
        QtCore.QTimer.singleShot(350, self.sync_backend)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
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

        for page in (
            self.job_page,
            self.render_page,
            self.validation_page,
            self.tools_page,
        ):
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
        self.job_page.refreshFarmRequested.connect(self.sync_backend)
        self.tools_page.retryConnectionRequested.connect(self.sync_backend)
        self.submit_button.clicked.connect(self.submit_job)

    def _build_header(self):
        card = QtWidgets.QFrame()
        card.setObjectName("HeaderCard")
        layout = QtWidgets.QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        logo = QtWidgets.QLabel("⬢")
        logo.setObjectName("BrandAccent")
        logo.setFixedSize(42, 42)
        logo.setAlignment(ALIGN_CENTER)
        logo_file = icon_path()
        if logo_file:
            pixmap = QtGui.QPixmap(logo_file)
            if not pixmap.isNull():
                logo.setText("")
                logo.setPixmap(pixmap.scaled(38, 38))

        brand = QtWidgets.QVBoxLayout()
        brand.setSpacing(0)
        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(0)
        main = QtWidgets.QLabel("RENDER")
        main.setObjectName("BrandMain")
        accent = QtWidgets.QLabel("HIVE")
        accent.setObjectName("BrandAccent")
        title_row.addWidget(main)
        title_row.addWidget(accent)
        title_row.addStretch()
        subtitle = QtWidgets.QLabel("HOUDINI RENDER SUBMISSION")
        subtitle.setObjectName("BrandSubtitle")
        self.scene_label = QtWidgets.QLabel("Scene: loading…")
        self.scene_label.setObjectName("SceneMeta")
        brand.addLayout(title_row)
        brand.addWidget(subtitle)
        brand.addWidget(self.scene_label)

        meta = QtWidgets.QVBoxLayout()
        meta.setSpacing(5)
        meta.setAlignment(ALIGN_RIGHT | ALIGN_VCENTER)
        self.version_chip = StatusChip("UI v{}".format(__version__))
        self.renderer_chip = StatusChip("Renderer: Not Set")
        meta.addWidget(self.version_chip)
        meta.addWidget(self.renderer_chip)

        layout.addWidget(logo)
        layout.addLayout(brand, 1)
        layout.addLayout(meta)
        return card

    def _build_sidebar(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("Sidebar")
        frame.setFixedWidth(104)
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)
        self.nav_buttons = []
        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        for index, label in enumerate(("Job", "Render", "Validation", "Tools")):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page=index: self.select_page(page)
            )
            group.addButton(button, index)
            layout.addWidget(button)
            self.nav_buttons.append(button)
        layout.addStretch()
        self.houdini_chip = StatusChip("Houdini")
        layout.addWidget(self.houdini_chip, 0, ALIGN_HCENTER)
        self.nav_buttons[0].setChecked(True)
        return frame

    def _build_footer(self):
        card = QtWidgets.QFrame()
        card.setObjectName("FooterCard")
        root = QtWidgets.QVBoxLayout(card)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        self.submit_button = QtWidgets.QPushButton("Submit Job")
        self.submit_button.setObjectName("SubmitButton")
        self.submit_button.setEnabled(False)
        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.submit_button, 1)
        button_row.addStretch()
        root.addLayout(button_row)

        status_row = QtWidgets.QHBoxLayout()
        self.status_dot = QtWidgets.QLabel("●")
        self.status_text = QtWidgets.QLabel("Ready")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        status_row.addWidget(QtWidgets.QLabel("RenderHive"))
        root.addLayout(status_row)
        return card

    def select_page(self, index):
        self.page_stack.setCurrentIndex(index)
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

    def _set_status(self, text, level="good"):
        self.status_text.setText(str(text))
        apply_status_appearance(self.status_text, level)
        apply_status_appearance(self.status_dot, level)
        if hasattr(self, "tools_page"):
            self.tools_page.append_activity(text)

    def _initialize_api_status(self):
        source = self.api_config.get("_config_source", "Unavailable") if self.api_config else "Unavailable"
        token = str((self.api_config.get("auth") or {}).get("token") or "") if self.api_config else ""
        self.tools_page.set_connection_config(source, bool(token))
        if self.api_config_error:
            self.tools_page.set_connection_error(self.api_config_error, "Now")
            self.job_page.set_backend_error(self.api_config_error)

    def refresh_context(self, scan_nodes=False):
        if self._closing:
            return
        try:
            context = self.adapter.scene_context()
        except Exception as error:
            self.scene_label.setText("Scene: unavailable")
            self._set_status("Scene context failed: {}".format(error), "error")
            return

        previous_key = ""
        if self._context is not None:
            previous_key = str(self._context.hip_path or "").strip().lower()
        current_key = str(context.hip_path or "").strip().lower()
        scene_changed = bool(self._context is not None and current_key != previous_key)

        self._context = context
        self.job_page.set_context(context, force_identity=scene_changed)
        self.render_page.set_context(context, reset_scene=scene_changed)
        self.validation_page.set_context(context)
        if scene_changed:
            self.validation_page.set_render_node(None)
            self.renderer_chip.setText("Renderer: Not Set")
        self.scene_label.setText(
            "Scene: {}{}".format(
                context.scene_name or "Untitled",
                " *" if context.has_unsaved_changes else "",
            )
        )
        self.houdini_chip.setText(
            "Houdini {}".format(".".join(context.houdini_version.split(".")[:2]))
        )
        if scan_nodes:
            self.refresh_render_nodes()
        elif not self.render_page.has_nodes():
            self.render_page.show_scan_prompt()
            self._set_status("Scene information loaded automatically.", "good")
        self._update_submit_enabled()

    def refresh_render_nodes(self):
        preferred = self.render_page.current_node_path()
        self._set_status("Scanning render nodes…", "info")
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass
        try:
            nodes = self.adapter.render_nodes()
        except Exception as error:
            self.render_page.set_nodes([], preferred_path="")
            self._set_status("Render-node discovery failed: {}".format(error), "error")
            return
        self.render_page.set_nodes(nodes, preferred_path=preferred)
        self._set_status(
            "{} render node(s) detected.".format(len(nodes)),
            "good" if nodes else "warning",
        )

    def use_selected_render_node(self):
        try:
            node_info = self.adapter.selected_render_node()
        except Exception as error:
            self._set_status("Could not read selected node: {}".format(error), "error")
            return
        if node_info is None:
            self._set_status("Select an executable ROP or Solaris render node.", "warning")
            return
        if not self.render_page.select_node_path(node_info.path):
            self.render_page._nodes = [node_info]
            self.render_page.set_nodes([node_info], preferred_path=node_info.path)
        else:
            self.render_page.replace_current_node(node_info)
        self._set_status("Render settings loaded from {}.".format(node_info.path), "good")

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
        self.validation_page.set_render_node(node_info)
        self.renderer_chip.setText(
            "Renderer: {}".format(node_info.renderer if node_info is not None else "Not Set")
        )
        self._update_submit_enabled()

    def _update_submit_enabled(self):
        enabled = bool(
            self.api_client is not None
            and self.api_config.get("enabled", True)
            and self.render_page.current_node_info() is not None
            and self._api_operation != "submit"
        )
        self.submit_button.setEnabled(enabled)

    def _start_api_operation(self, name, operation, success_callback):
        if self._api_thread is not None and self._api_thread.isRunning():
            self._set_status("Another backend operation is already running.", "warning")
            return False
        self._api_operation = str(name)
        self._api_thread = ApiTaskThread(operation, parent=self)
        self._api_thread.succeeded.connect(success_callback)
        self._api_thread.failed.connect(self._on_api_failed)
        self._api_thread.finished.connect(self._on_api_finished)
        self._api_thread.start()
        self._update_submit_enabled()
        return True

    def sync_backend(self):
        if self.api_client is None:
            message = self.api_config_error or "Backend configuration is unavailable."
            self.job_page.set_backend_error(message)
            self.tools_page.set_connection_error(message, datetime.datetime.now().strftime("%H:%M"))
            self._set_status(message, "error")
            return
        if not self.api_config.get("enabled", True):
            message = "RenderHive API is disabled by managed configuration."
            self.job_page.set_backend_error(message)
            self.tools_page.set_connection_error(message, datetime.datetime.now().strftime("%H:%M"))
            self._set_status(message, "warning")
            return

        self.job_page.set_syncing(True)
        self.tools_page.set_connecting()
        self._set_status("Connecting to RenderHive…", "info")

        def operation():
            self.api_client.test_connection()
            return {
                "workers": [normalize_worker(item) for item in self.api_client.list_workers()],
                "pools": [normalize_pool(item) for item in self.api_client.list_pools()],
            }

        self._start_api_operation("sync", operation, self._on_farm_synced)

    def _on_farm_synced(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        checked_at = datetime.datetime.now().strftime("%H:%M")
        workers = payload.get("workers") or []
        pools = payload.get("pools") or []
        self._farm_ready = True
        self.job_page.set_farm_data(workers, pools, checked_at)
        self.tools_page.set_connected(checked_at)
        self._set_status(
            "Backend connected: {} worker(s), {} pool(s).".format(len(workers), len(pools)),
            "good",
        )

    def _node_for_submission(self):
        node = self.render_page.current_node_info()
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

    def submit_job(self):
        self.refresh_context(scan_nodes=False)
        context = self._context
        node = self._node_for_submission()
        results = validate(context, node)
        errors = [item for item in results if item.blocks_submission]
        if errors:
            self.validation_page.set_context(context)
            self.validation_page.set_render_node(node)
            self.validation_page.run_validation()
            self.select_page(2)
            self._set_status("Submission blocked by {} validation error(s).".format(len(errors)), "error")
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive Validation",
                "Fix the validation errors before submitting the job.",
            )
            return

        settings = self.job_page.job_settings()
        targeting = self.job_page.pool_targeting()
        if targeting.get("strategy") == "selected_only" and not targeting.get("selected_pool_ids"):
            self._set_status("Select at least one worker pool.", "warning")
            return

        try:
            task = build_task(
                context,
                node,
                job_name=settings.get("job_name"),
                project_name=settings.get("project_name"),
                priority=settings.get("priority"),
                department=settings.get("department"),
                comment=settings.get("comment"),
                chunk_size=settings.get("chunk_size"),
                machine_limit=settings.get("machine_limit"),
                concurrent_tasks=settings.get("concurrent_tasks"),
                start_suspended=settings.get("start_suspended"),
                pool_targeting=targeting,
            )
            request_payload = build_api_request(task, self.api_config)
        except Exception as error:
            self._set_status("Could not prepare the job: {}".format(error), "error")
            QtWidgets.QMessageBox.critical(self, "RenderHive", str(error))
            return

        self.submit_button.setText("Submitting…")
        self._set_status("Submitting Houdini job to RenderHive…", "info")
        self._start_api_operation(
            "submit",
            lambda: self.api_client.submit_job(request_payload),
            self._on_job_submitted,
        )

    def _on_job_submitted(self, response):
        response = response if isinstance(response, dict) else {}
        job_id = response.get("id") or response.get("job_id") or response.get("uid") or "Not returned"
        state = response.get("state") or response.get("status") or "PENDING"
        visible_name = response.get("visible_name") or self.job_page.job_name.text().strip()
        self._set_status("Job submitted: {} ({})".format(visible_name, state), "good")
        QtWidgets.QMessageBox.information(
            self,
            "RenderHive Job Submitted",
            "Job: {}\nStatus: {}\nReference: {}".format(visible_name, state, job_id),
        )

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
        self.submit_button.setText("Submit Job")
        if self._api_thread is not None:
            self._api_thread.deleteLater()
            self._api_thread = None
        self._api_operation = ""
        self._update_submit_enabled()

    def closeEvent(self, event):
        if self._embedded:
            event.accept()
            return
        self.hide()
        event.ignore()
