from __future__ import absolute_import, print_function

import os

from ..qt_compat import QtCore, QtGui, QtWidgets
from ..qt_theme import COLORS
from ..targeting_widgets import WorkerSyncThread
from ..runtime_registry import WIDGETS as _WIDGETS


class ApiControllerMixin(object):
    """Backend connection and submission lifecycle for the Maya window."""
    def api_enabled(self):
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
                    "Configuration unavailable",
                    level="error",
                )
                self.append_activity(
                    "Could not load managed API configuration: {}".format(error)
                )
                return
    
            source_widget = _WIDGETS.get("api_config_source")
            if isinstance(source_widget, QtWidgets.QLabel):
                source = str(
                    config.get("_config_source")
                    or self.api.get_api_config_source()
                    or "Managed"
                )
                source_widget.setText(
                    "Configuration: {}".format(source)
                )
    
            has_token = bool(config.get("auth", {}).get("token"))
            if config.get("enabled", False) and has_token:
                self.set_api_status(
                    "Ready to connect",
                    level="info",
                )
            elif config.get("enabled", False):
                self.set_api_status(
                    "Credentials not configured",
                    level="warning",
                )
            else:
                self.set_api_status(
                    "Backend disabled by configuration",
                    level="warning",
                )


    def api_settings_payload(self):
            return self.api.get_api_config()


    def save_api_settings(self):
            # Artist mode is read-only. Connection settings are managed outside
            # Maya and are reloaded automatically for every API operation.
            try:
                return self.api.get_api_config()
            except Exception as error:
                self.set_api_status(
                    "Configuration unavailable",
                    level="error",
                )
                self.append_activity(
                    "Could not load managed API configuration: {}".format(error)
                )
                return None


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
                    "QLabel#ConnectionState {"
                    "background-color:%s;"
                    "border:1px solid %s;"
                    "border-radius:7px;"
                    "color:%s;"
                    "padding:8px 10px;"
                    "font-weight:600;"
                    "}" % (COLORS["surface2"], color, color)
                )


    def open_api_config(self):
            if not bool(getattr(self.api, "api_admin_mode_enabled", lambda: False)()):
                return
    
            try:
                path = self.api.get_api_config_path()
                if not path:
                    raise RuntimeError(
                        "No managed API configuration file is available."
                    )
    
                if hasattr(os, "startfile"):
                    os.startfile(path)
                else:
                    QtGui.QDesktopServices.openUrl(
                        QtCore.QUrl.fromLocalFile(path)
                    )
    
                self.append_activity(
                    "Opened managed API config: {}".format(path)
                )
            except Exception as error:
                QtWidgets.QMessageBox.warning(
                    self,
                    "RenderHive API",
                    "Could not open managed configuration:\n\n{}".format(error),
                )


    def test_api_connection(self, *args):
            if self._is_closing:
                return
    
            if (
                self.api_test_thread is not None
                and self.api_test_thread.isRunning()
            ):
                return
    
            if not self.api_enabled():
                self.set_api_status(
                    "Backend disabled by configuration",
                    level="warning",
                )
                self.set_status(
                    "Backend submission is disabled.",
                    level="warning",
                )
                return
    
            button = _WIDGETS.get("test_api_button")
            if isinstance(button, QtWidgets.QPushButton):
                button.setEnabled(False)
                button.setText("Connecting…")
    
            self.set_api_status(
                "Connecting…",
                level="info",
            )
            self.set_status(
                "Connecting to RenderHive…",
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
                "Connected",
                level="success",
            )
            self.set_status(
                "RenderHive connected.",
                level="success",
            )
            self.append_activity(
                "Backend connection succeeded (HTTP {}).".format(status_code)
            )
    
            if not self._is_closing:
                self.sync_available_workers()


    def on_api_test_failed(self, error):
            self.set_api_status(
                "Connection unavailable",
                level="error",
            )
            self.set_status(
                "RenderHive connection failed.",
                level="error",
            )
            self.append_activity(
                "Backend connection failed: {}".format(error)
            )


    def on_api_test_finished(self):
            if self._is_closing:
                return
    
            button = _WIDGETS.get("test_api_button")
            if isinstance(button, QtWidgets.QPushButton):
                button.setEnabled(True)
                button.setText("Retry Connection")
    
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
                        "No online workers are available in the targeted pools.\n\n"
                        "The Job can still be submitted, but it may remain PENDING "
                        "until a Worker in one of those pools becomes available.\n\n"
                        "Submit it anyway?"
                    ),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
    
                if answer != QtWidgets.QMessageBox.Yes:
                    self.set_status(
                        "Submission cancelled: no workers in the targeted pools.",
                        level="warning",
                    )
                    return None
    
            # Reconcile the selector with Maya immediately before submission.
            # set_layers() preserves only still-available checked names and never
            # injects defaultRenderLayer into an existing user selection.
            self.refresh_render_layers(record_activity=False)
    
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
            if self._is_closing:
                return None
    
            if not self.api_enabled():
                self.set_status(
                    "RenderHive API is disabled.",
                    level="warning",
                )
                QtWidgets.QMessageBox.warning(
                    self,
                    "RenderHive API",
                    (
                        "Backend submission is disabled in the managed "
                        "RenderHive configuration. Contact the pipeline "
                        "administrator."
                    ),
                )
                return None
    
            if (
                self.api_submit_thread is not None
                and self.api_submit_thread.isRunning()
            ):
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
            if self._is_closing:
                return
    
            button = _WIDGETS.get("submit_job_button")
            if isinstance(button, QtWidgets.QPushButton):
                button.setEnabled(True)
                button.setText("Submit Job")
    
            self.set_busy(False)
    
            if self.api_submit_thread is not None:
                self.api_submit_thread.deleteLater()
                self.api_submit_thread = None
