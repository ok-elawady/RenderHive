from __future__ import absolute_import

import uuid

from ..qt_compat import QtWidgets
from ..runtime_registry import WIDGETS as _WIDGETS
from ..targeting_widgets import WorkerSyncThread
from ..job_dependency_widgets import JobDependencyDialog, job_display_name, job_identifier


def _split_ids(value):
    result = []
    for item in str(value or "").replace(";", ",").split(","):
        clean = item.strip()
        if not clean:
            continue
        try:
            clean = str(uuid.UUID(clean))
        except Exception:
            pass
        if clean not in result:
            result.append(clean)
    return result


class DependencyControllerMixin(object):
    """Backend Job browser and persisted dependency selection."""

    @staticmethod
    def normalize_dependency_jobs(payload):
        if isinstance(payload, dict):
            for key in ("results", "jobs", "items", "data"):
                candidate = payload.get(key)
                if isinstance(candidate, (list, tuple)):
                    payload = candidate
                    break
            else:
                payload = []
        if not isinstance(payload, (list, tuple)):
            return []

        jobs = []
        seen = set()
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            job_id = job_identifier(entry)
            if not job_id or job_id in seen:
                continue
            try:
                job_id = str(uuid.UUID(job_id))
            except Exception:
                # The API contract defines Job ids as UUIDs. Invalid records are
                # not safe to use as dependency references.
                continue
            seen.add(job_id)
            record = dict(entry)
            record["id"] = job_id
            jobs.append(record)

        jobs.sort(
            key=lambda item: (
                str(item.get("created_at") or ""),
                job_display_name(item).lower(),
            ),
            reverse=True,
        )
        return jobs

    def selected_job_dependency_ids(self):
        widget = _WIDGETS.get("rh_job_dependencies")
        if isinstance(widget, QtWidgets.QLineEdit):
            return _split_ids(widget.text())
        return []

    def set_selected_job_dependency_ids(self, values, records=None):
        clean = []
        for value in values or []:
            text = str(value or "").strip()
            if not text:
                continue
            try:
                text = str(uuid.UUID(text))
            except Exception:
                continue
            if text not in clean:
                clean.append(text)

        if records is not None:
            for record in records or []:
                if not isinstance(record, dict):
                    continue
                job_id = job_identifier(record)
                if job_id:
                    self.job_dependency_records[job_id] = dict(record)

        widget = _WIDGETS.get("rh_job_dependencies")
        if isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(", ".join(clean))
        self.update_job_dependency_summary()

        if self._active_scene_state_key and not self._scene_state_restoring:
            self.save_scene_state()

    def update_job_dependency_summary(self, *args):
        ids = self.selected_job_dependency_ids()
        label = _WIDGETS.get("rh_job_dependencies_summary")
        clear_button = _WIDGETS.get("rh_job_dependencies_clear")

        if isinstance(clear_button, QtWidgets.QPushButton):
            clear_button.setEnabled(bool(ids))

        if not isinstance(label, QtWidgets.QLabel):
            return

        if not ids:
            label.setText("No dependencies selected")
            label.setToolTip("This job can start as soon as scheduler requirements are satisfied.")
            return

        names = []
        tooltip_lines = []
        for job_id in ids:
            record = self.job_dependency_records.get(job_id)
            name = job_display_name(record) if record else ""
            if name and name not in names:
                names.append(name)
            tooltip_lines.append("{} — {}".format(name or "Saved dependency", job_id))

        if len(ids) == 1:
            text = "1 job selected"
            if names:
                text += " · {}".format(names[0])
        elif names and len(ids) <= 3:
            text = "{} jobs · {}".format(len(ids), ", ".join(names[:3]))
        else:
            text = "{} jobs selected".format(len(ids))

        label.setText(text)
        label.setToolTip("\n".join(tooltip_lines))

    def clear_job_dependencies(self, *args):
        self.set_selected_job_dependency_ids([])

    def open_job_dependency_browser(self, *args):
        if self._is_closing:
            return

        if self.job_dependency_thread is not None and self.job_dependency_thread.isRunning():
            return

        try:
            config = self.api.get_api_config()
        except Exception as error:
            QtWidgets.QMessageBox.warning(
                self,
                "RenderHive Dependencies",
                "Could not read backend configuration:\n\n{}".format(error),
            )
            return

        if not bool(config.get("enabled", False)):
            QtWidgets.QMessageBox.information(
                self,
                "RenderHive Dependencies",
                "Backend access is disabled by the managed RenderHive configuration.",
            )
            return

        button = _WIDGETS.get("rh_job_dependencies_browse")
        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(False)
            button.setText("Loading…")

        self.set_status("Loading RenderHive jobs…", level="info")
        self.job_dependency_thread = WorkerSyncThread(
            self.api.get_api_jobs,
            parent=self,
        )
        self.job_dependency_thread.succeeded.connect(self.on_job_dependencies_loaded)
        self.job_dependency_thread.failed.connect(self.on_job_dependencies_failed)
        self.job_dependency_thread.finished.connect(self.on_job_dependencies_finished)
        self.job_dependency_thread.start()

    def on_job_dependencies_loaded(self, payload):
        jobs = self.normalize_dependency_jobs(payload)
        self.job_dependency_jobs = jobs
        self.job_dependency_records = {
            job_identifier(job): dict(job)
            for job in jobs
            if job_identifier(job)
        }
        self.update_job_dependency_summary()

        dialog = JobDependencyDialog(
            jobs,
            selected_ids=self.selected_job_dependency_ids(),
            parent=self,
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            self.set_status("Job dependency selection unchanged.", level="info")
            return

        selected_ids = dialog.selected_ids()
        self.set_selected_job_dependency_ids(selected_ids, dialog.selected_records())
        self.set_status(
            "{} job dependenc{} selected.".format(
                len(selected_ids),
                "y" if len(selected_ids) == 1 else "ies",
            ),
            level="success" if selected_ids else "info",
        )
        self.append_activity(
            "Job dependencies updated: {} selected.".format(len(selected_ids))
        )

    def on_job_dependencies_failed(self, error):
        self.set_status("Could not load RenderHive jobs.", level="warning")
        self.append_activity("Job dependency browser failed: {}".format(error))
        QtWidgets.QMessageBox.warning(
            self,
            "RenderHive Dependencies",
            "Could not load jobs from the RenderHive backend:\n\n{}".format(error),
        )

    def on_job_dependencies_finished(self):
        if self._is_closing:
            return

        button = _WIDGETS.get("rh_job_dependencies_browse")
        if isinstance(button, QtWidgets.QPushButton):
            button.setEnabled(True)
            button.setText("Browse Jobs…")

        if self.job_dependency_thread is not None:
            self.job_dependency_thread.deleteLater()
            self.job_dependency_thread = None
