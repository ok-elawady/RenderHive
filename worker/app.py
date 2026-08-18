"""RenderHive multi-DCC worker application with production dashboard UI.

The worker keeps the existing Maya/Houdini adapter architecture while exposing
Deadline-class operational information through a RenderHive-specific interface.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Sequence

import psutil
import requests
from PySide6.QtCore import QSettings, QSharedMemory, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from adapters import AdapterFactory
from adapters.base import AdapterError
from core.gpu_info import GPUDetector
from core.dcc_discovery import (
    DCCInstallation,
    build_capabilities,
    build_capability_tags,
    discover_all,
)
from core.process_runner import run_process
from core.progress import TaskProgressTracker
from core.smooth_progress import SmoothProgressValue
from core.runtime_paths import writable_log_root
from core.task_normalizer import normalize_task
from core.ui_helpers import (
    build_task_ui_payload,
    format_bytes,
    format_duration,
    format_timestamp,
    local_ip_address,
    mac_address,
    machine_user,
    merge_job_detail,
    pool_names_from_worker,
    safe_dict,
    safe_text,
    select_worker_record,
    split_csv,
)
from ui.theme import APP_STYLESHEET
from ui.widgets import EmptyState, InfoGrid, NavButton, ResourceMeter, SectionCard, StatCard, StatusChip
from version import WORKER_VERSION


HOSTNAME = socket.gethostname()


def _format_installations(discovered: Dict[str, Sequence[DCCInstallation]]) -> str:
    lines: List[str] = []
    maya_items = list(discovered.get("maya") or [])
    houdini_items = list(discovered.get("houdini") or [])

    if maya_items:
        lines.append("Maya")
        for item in maya_items:
            render_path = item.executables.get("render") or "Render.exe missing"
            lines.append("  {}  |  {}".format(item.version, render_path))
    else:
        lines.append("Maya: Not detected")

    lines.append("")
    if houdini_items:
        lines.append("Houdini")
        for item in houdini_items:
            modes = []
            if item.executables.get("hython"):
                modes.append("hython")
            if item.executables.get("husk"):
                modes.append("husk")
            lines.append(
                "  {}  |  {}  |  {}".format(
                    item.version,
                    ", ".join(modes) or "No render executable",
                    item.root,
                )
            )
    else:
        lines.append("Houdini: Not detected")
    return "\n".join(lines)


def _installation_rows(discovered: Dict[str, Sequence[DCCInstallation]]) -> List[List[str]]:
    rows: List[List[str]] = []
    for dcc in ("maya", "houdini"):
        for item in discovered.get(dcc) or []:
            if dcc == "maya":
                tools = [name for name in ("render", "mayapy", "maya") if item.executables.get(name)]
            else:
                tools = [name for name in ("hython", "husk", "houdini") if item.executables.get(name)]
            rows.append([dcc.title(), item.version, ", ".join(tools) or "Unavailable", item.root])
    return rows


def _disk_root() -> str:
    if os.name == "nt":
        return (os.environ.get("SystemDrive") or "C:") + "\\"
    return "/"


class WorkerThread(QThread):
    log_signal = Signal(str)
    status_signal = Signal(str)
    scheduler_signal = Signal(str)
    capabilities_signal = Signal(str)
    connection_signal = Signal(bool)
    system_info_signal = Signal(object)
    server_worker_signal = Signal(object)
    task_started_signal = Signal(object)
    task_progress_signal = Signal(object)
    task_finished_signal = Signal(object)

    def __init__(
        self,
        api_url: str,
        api_token: str,
        discovered: Dict[str, Sequence[DCCInstallation]],
        profile: Dict[str, Any] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.discovered = discovered
        self.profile = dict(profile or {})
        self.adapter_factory = AdapterFactory(discovered)
        self.is_running = True
        self.dispatch_paused = bool(self.profile.get("start_paused", False))
        self.pause_after_current = str(self.profile.get("after_task", "continue")).lower() == "pause"
        self.cancel_current_requested = False
        self.force_profile_refresh = False
        self.current_task_id = ""
        self.current_task_ui: Dict[str, Any] = {}
        self.session = requests.Session()
        self._last_system_info: Dict[str, Any] = {}
        self.started_monotonic = time.monotonic()
        self.last_worker_profile_fetch = 0.0
        self.poll_interval = max(2, min(30, int(self.profile.get("poll_interval", 5) or 5)))
        self._last_progress_frame = None
        self._progress_tracker: TaskProgressTracker | None = None
        self._last_progress_signature = None
        self._last_progress_emit = 0.0
        self.gpu_detector = GPUDetector()

    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": "Token {}".format(self.api_token),
            "Content-Type": "application/json",
            "User-Agent": "RenderHive-Worker/{}".format(WORKER_VERSION),
        }

    def collect_system_info(self) -> Dict[str, object]:
        virtual_memory = psutil.virtual_memory()
        disk = psutil.disk_usage(_disk_root())
        info: Dict[str, object] = {
            "worker_version": WORKER_VERSION,
            "platform": platform.platform(),
            "operating_system": "{} {}".format(platform.system(), platform.release()).strip(),
            "python_version": platform.python_version(),
            "machine_user": machine_user(),
            "hostname": HOSTNAME,
            "ip_address": local_ip_address(),
            "mac_address": mac_address(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": virtual_memory.percent,
            "memory_used_mb": (virtual_memory.total - virtual_memory.available) // (1024 * 1024),
            "cpu_count": psutil.cpu_count(logical=True),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "total_memory_mb": virtual_memory.total // (1024 * 1024),
            "disk_total_bytes": disk.total,
            "disk_used_bytes": disk.used,
            "disk_free_bytes": disk.free,
            "disk_percent": disk.percent,
            "worker_uptime_seconds": int(time.monotonic() - self.started_monotonic),
            "scheduler_status": "PAUSED" if self.dispatch_paused else "WAITING",
            "after_task": "PAUSE" if self.pause_after_current else "CONTINUE",
            "capabilities": build_capabilities(self.discovered),
            "worker_profile": {
                "description": safe_text(self.profile.get("description")),
                "comment": safe_text(self.profile.get("comment")),
                "region": safe_text(self.profile.get("region"), "Default"),
                "custom_tags": split_csv(self.profile.get("custom_tags")),
            },
        }

        try:
            if os.name == "nt":
                import winreg  # type: ignore

                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                )
                info["cpu_name"] = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
                winreg.CloseKey(key)
            else:
                info["cpu_name"] = platform.processor()
        except Exception:
            info["cpu_name"] = platform.processor()

        if self.current_task_ui:
            info["current_task"] = {
                "task_id": safe_text(self.current_task_ui.get("task_id")),
                "job_name": safe_text(self.current_task_ui.get("job_name")),
                "phase": safe_text(self.current_task_ui.get("phase")),
                "progress_percent": int(self.current_task_ui.get("progress") or 0),
                "current_frame": self.current_task_ui.get("current_frame"),
                "total_frames": int(self.current_task_ui.get("total_frames") or 1),
                "elapsed_seconds": float(self.current_task_ui.get("elapsed_seconds") or 0.0),
                "eta_seconds": self.current_task_ui.get("eta_seconds"),
            }

        info.update(self.gpu_detector.query())
        return info

    def heartbeat_payload(self) -> Dict[str, object]:
        system_info = self.collect_system_info()
        tags = build_capability_tags(self.discovered)
        tags.extend(split_csv(self.profile.get("custom_tags")))
        tags = list(dict.fromkeys(tags))
        return {
            "hostname": HOSTNAME,
            "ip_address": system_info.get("ip_address") or None,
            "status": "RENDERING" if self.current_task_id else "ONLINE",
            "tags": tags,
            "cores": max(1, int(system_info.get("cpu_count") or 1)),
            "memory_mb": max(1, int(system_info.get("total_memory_mb") or 1)),
            "gpu_models": list(system_info.get("gpu_models") or []),
            "system_info": system_info,
            "capabilities": build_capabilities(self.discovered),
        }

    def send_heartbeat(self) -> bool:
        payload = self.heartbeat_payload()
        self.system_info_signal.emit(payload.get("system_info") or {})
        try:
            response = self.session.post(
                "{}/workers/ping/".format(self.api_url),
                json=payload,
                headers=self.get_headers(),
                timeout=8,
            )
            if not (200 <= response.status_code < 300):
                self.log_signal.emit("Heartbeat failed: HTTP {}".format(response.status_code))
                self.connection_signal.emit(False)
                return False
            self.connection_signal.emit(True)
            now = time.monotonic()
            if self.force_profile_refresh or now - self.last_worker_profile_fetch >= 30.0:
                self.force_profile_refresh = False
                self.last_worker_profile_fetch = now
                self.fetch_server_worker()
            return True
        except requests.exceptions.RequestException as error:
            self.log_signal.emit("Heartbeat connection error: {}".format(error))
            self.connection_signal.emit(False)
            return False
        except Exception as error:
            self.log_signal.emit("Heartbeat unexpected error: {}".format(error))
            self.connection_signal.emit(False)
            return False

    def fetch_server_worker(self) -> None:
        try:
            response = self.session.get(
                "{}/workers/".format(self.api_url),
                params={"search": HOSTNAME},
                headers=self.get_headers(),
                timeout=8,
            )
            if not (200 <= response.status_code < 300):
                return
            record = select_worker_record(response.json(), HOSTNAME)
            if record:
                self.server_worker_signal.emit(record)
        except Exception:
            return

    def fetch_job_detail(self, job_id: str) -> Dict[str, Any]:
        if not job_id:
            return {}
        try:
            response = self.session.get(
                "{}/jobs/{}/".format(self.api_url, job_id),
                headers=self.get_headers(),
                timeout=8,
            )
            if 200 <= response.status_code < 300:
                data = response.json()
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def set_dispatch_paused(self, paused: bool) -> None:
        self.dispatch_paused = bool(paused)
        state = "PAUSED" if self.dispatch_paused else "WAITING"
        self.scheduler_signal.emit(state)
        if not self.current_task_id:
            self.status_signal.emit("PAUSED" if self.dispatch_paused else "ONLINE")
        self.log_signal.emit("Scheduler {}.".format("paused" if paused else "resumed"))

    def set_pause_after_current(self, enabled: bool) -> None:
        self.pause_after_current = bool(enabled)
        self.log_signal.emit(
            "After current task: {}.".format("pause dispatch" if enabled else "continue")
        )

    def cancel_current_task(self) -> None:
        if self.current_task_id:
            self.cancel_current_requested = True
            self.log_signal.emit("Cancellation requested for task {}.".format(self.current_task_id))

    def request_profile_refresh(self) -> None:
        self.force_profile_refresh = True

    def _emit_progress_snapshot(self, task_id: str, status: str = "RENDERING", force: bool = False) -> None:
        tracker = self._progress_tracker
        if tracker is None:
            return
        data = tracker.snapshot().to_dict()
        data.update({"task_id": task_id, "status": status})
        signature = (
            data.get("phase"),
            data.get("percent"),
            data.get("current_frame"),
            data.get("completed_frames"),
            round(float(data.get("renderer_percent") or 0.0), 1),
            data.get("detail"),
        )
        now = time.monotonic()
        if not force and signature == self._last_progress_signature and now - self._last_progress_emit < 1.0:
            return
        self._last_progress_signature = signature
        self._last_progress_emit = now
        if self.current_task_ui:
            self.current_task_ui.update(
                {
                    "progress": data.get("percent", 0),
                    "phase": data.get("phase", "Rendering"),
                    "current_frame": data.get("current_frame"),
                    "completed_frames": data.get("completed_frames", 0),
                    "total_frames": data.get("total_frames", 1),
                    "elapsed_seconds": data.get("elapsed_seconds", 0.0),
                    "eta_seconds": data.get("eta_seconds"),
                    "progress_detail": data.get("detail", ""),
                    "renderer_percent": data.get("renderer_percent"),
                }
            )
        self.task_progress_signal.emit(data)

    def _process_event(self, task, event: str) -> None:
        if self._progress_tracker is None:
            return
        self._progress_tracker.on_process_event(event)
        self._emit_progress_snapshot(task.task_id)

    def _process_output_line(self, task, line: str) -> None:
        if self._progress_tracker is None:
            return
        self._progress_tracker.on_line(line)
        self._emit_progress_snapshot(task.task_id)

    def run_task(self, raw_task: Dict[str, object]) -> Tuple[int, str, str, float, str]:
        task = None
        try:
            task = normalize_task(raw_task)
            adapter = self.adapter_factory.for_task(task)
            plan = adapter.build_plan(task)
        except (AdapterError, ValueError) as error:
            self.log_signal.emit("Task preparation failed: {}".format(error))
            fallback_ui = build_task_ui_payload(raw_task, task)
            fallback_ui.update(
                {
                    "status": "FAILED",
                    "exit_code": -2,
                    "duration_seconds": 0.0,
                    "error_tail": str(error),
                    "progress": 0,
                    "phase": "Failed",
                    "progress_detail": "Preparation failed: {}".format(error),
                }
            )
            self.task_finished_signal.emit(fallback_ui)
            return -2, "", str(error), 0.0, ""
        except Exception as error:
            self.log_signal.emit("Unexpected task preparation error: {}".format(error))
            fallback_ui = build_task_ui_payload(raw_task, task)
            fallback_ui.update(
                {
                    "status": "FAILED",
                    "exit_code": -3,
                    "duration_seconds": 0.0,
                    "error_tail": str(error),
                    "progress": 0,
                    "phase": "Failed",
                    "progress_detail": "Preparation error: {}".format(error),
                }
            )
            self.task_finished_signal.emit(fallback_ui)
            return -3, "", str(error), 0.0, ""

        task_ui = build_task_ui_payload(raw_task, task)
        detail = self.fetch_job_detail(safe_text(task_ui.get("job_id")))
        if detail:
            task_ui = merge_job_detail(task_ui, detail)

        self.current_task_id = task.task_id
        self.current_task_ui = task_ui
        self.cancel_current_requested = False
        self._last_progress_frame = None
        started = time.monotonic()
        self._progress_tracker = TaskProgressTracker(
            task.frame_start, task.frame_end, task.frame_step, started_at=started
        )
        self._last_progress_signature = None
        self._last_progress_emit = 0.0
        initial_progress = self._progress_tracker.snapshot().to_dict()
        task_ui.update(
            {
                "status": "RENDERING",
                "started_at_monotonic": started,
                "progress": initial_progress.get("percent", 1),
                "phase": initial_progress.get("phase", "Preparing Task"),
                "current_frame": initial_progress.get("current_frame"),
                "completed_frames": initial_progress.get("completed_frames", 0),
                "elapsed_seconds": initial_progress.get("elapsed_seconds", 0.0),
                "eta_seconds": initial_progress.get("eta_seconds"),
                "progress_detail": initial_progress.get("detail", "Preparing Task"),
            }
        )
        self.task_started_signal.emit(dict(task_ui))
        self._emit_progress_snapshot(task.task_id, force=True)

        self.log_signal.emit(
            "Executing task {} | {} | Frames {}-{} step {}".format(
                task.task_id,
                plan.description,
                task.frame_start,
                task.frame_end,
                task.frame_step,
            )
        )
        self.log_signal.emit("Executable: {}".format(plan.executable))
        self.log_signal.emit("Command: {}".format(subprocess.list2cmdline(plan.command)))
        self.log_signal.emit("Working Directory: {}".format(plan.cwd or "<default>"))

        result = run_process(
            command=plan.command,
            task_id=task.task_id,
            env=plan.env,
            cwd=plan.cwd,
            is_cancelled=lambda: (not self.is_running) or self.cancel_current_requested,
            heartbeat=self.send_heartbeat,
            log=self.log_signal.emit,
            line_callback=lambda line: self._process_output_line(task, line),
            event_callback=lambda event: self._process_event(task, event),
        )

        arnold_gpu_failed = False
        scene_info = task.raw.get("scene_info") or task.raw.get("layer", {}).get("scene_info") or {}
        is_arnold = task.renderer.lower() == "arnold" if task.renderer else (scene_info.get("renderer", "").lower() == "arnold")
        
        if result.exit_code == 0 and is_arnold:
            try:
                with open(result.log_path, "r", encoding="utf-8", errors="replace") as log_r:
                    log_contents = log_r.read()
                gpu_failure_patterns = [
                    "Unable to load Optix library",
                    "GPU rendering is not available",
                    "Failed to initialize GPU",
                ]
                if any(p in log_contents for p in gpu_failure_patterns) and not result.output_image_path:
                    arnold_gpu_failed = True
            except Exception:
                pass

        if arnold_gpu_failed:
            self.log_signal.emit(f"Task {task.task_id}: Arnold GPU/OptiX failed. Auto-retrying with CPU rendering...")
            task.raw["force_cpu"] = True
            try:
                plan = adapter.build_plan(task)
                result = run_process(
                    command=plan.command,
                    task_id=task.task_id + "_cpu_retry",
                    env=plan.env,
                    cwd=plan.cwd,
                    is_cancelled=lambda: (not self.is_running) or self.cancel_current_requested,
                    heartbeat=self.send_heartbeat,
                    log=self.log_signal.emit,
                    line_callback=lambda line: self._process_output_line(task, line),
                    event_callback=lambda event: self._process_event(task, event),
                )
            except Exception as error:
                self.log_signal.emit(f"Task retry preparation failed: {error}")
        duration = max(0.0, time.monotonic() - started)
        cancelled = self.cancel_current_requested
        final_progress = (
            self._progress_tracker.finish(result.exit_code == 0, cancelled=cancelled).to_dict()
            if self._progress_tracker is not None
            else {}
        )
        self.current_task_id = ""
        self.cancel_current_requested = False

        display_log = result.log_path.replace("\\", "/")
        final_status = "CANCELLED" if cancelled else ("SUCCEEDED" if result.exit_code == 0 else "FAILED")
        finished_payload = dict(task_ui)
        finished_payload.update(
            {
                "status": final_status,
                "exit_code": result.exit_code,
                "duration_seconds": duration,
                "log_path": display_log,
                "output_image_path": result.output_image_path,
                "error_tail": result.error_tail,
                "progress": int(final_progress.get("percent", 100 if result.exit_code == 0 else task_ui.get("progress", 0))),
                "phase": final_progress.get("phase", final_status.title()),
                "current_frame": final_progress.get("current_frame"),
                "completed_frames": final_progress.get("completed_frames", 0),
                "total_frames": final_progress.get("total_frames", task_ui.get("total_frames", 1)),
                "elapsed_seconds": duration,
                "eta_seconds": final_progress.get("eta_seconds"),
                "progress_detail": final_progress.get("detail", final_status.title()),
            }
        )
        self.task_finished_signal.emit(finished_payload)
        self.current_task_ui = {}
        self._progress_tracker = None

        if result.exit_code == 0:
            message = "Task {} completed successfully.".format(task.task_id)
            if result.output_image_path:
                message += "\n  Output Image: {}".format(result.output_image_path)
            message += "\n  Log: {}".format(display_log)
            self.log_signal.emit(message)
        else:
            message = "Task {} {} with exit code {}.".format(
                task.task_id,
                "was cancelled" if cancelled else "failed",
                result.exit_code,
            )
            if result.error_tail:
                message += "\n  Output: {}".format(result.error_tail)
            message += "\n  Log: {}".format(display_log)
            self.log_signal.emit(message)
        return result.exit_code, display_log, result.error_tail, duration, result.output_image_path

    def report_status(
        self,
        task_id: str,
        exit_status: int,
        log_path: str = "",
        error_tail: str = "",
        duration_seconds: float = 0.0,
        output_image_path: str = "",
    ) -> None:
        try:
            endpoint = "succeed" if exit_status == 0 else "fail"
            log_text = ""
            if log_path and os.path.isfile(log_path):
                try:
                    file_size = os.path.getsize(log_path)
                    max_read_bytes = 2 * 1024 * 1024  # 2 MB ceiling
                    with open(log_path, "rb") as handle:
                        if file_size > max_read_bytes:
                            handle.seek(file_size - max_read_bytes)
                        log_bytes = handle.read()
                    log_text = log_bytes.decode("utf-8", errors="replace")
                except Exception:
                    pass

            payload: Dict[str, Any] = {
                "exit_status": int(exit_status),
                "worker_hostname": HOSTNAME,
                "log_output": log_text,
                "error_tail": error_tail or "",
                "duration_seconds": duration_seconds,
                "output_image_path": output_image_path or "",
            }
            if endpoint == "succeed":
                payload.update({"max_memory_used_mb": 0})
            response = self.session.post(
                "{}/tasks/{}/{}/".format(self.api_url, task_id, endpoint),
                json=payload,
                headers=self.get_headers(),
                timeout=15,
            )
            if not (200 <= response.status_code < 300):
                self.log_signal.emit("Failed to report task status: HTTP {}".format(response.status_code))
        except Exception as error:
            self.log_signal.emit("Error reporting task status: {}".format(error))

    def run(self) -> None:
        self.log_signal.emit("Starting RenderHive Worker {} on {}...".format(WORKER_VERSION, HOSTNAME))
        summary = _format_installations(self.discovered)
        self.capabilities_signal.emit(summary)
        self.log_signal.emit("Detected DCC applications:\n{}".format(summary))

        if not any(self.discovered.values()):
            self.log_signal.emit(
                "Warning: No Maya or Houdini installation was detected. "
                "The worker will stay online but cannot execute DCC tasks."
            )

        if not self.send_heartbeat():
            self.log_signal.emit("FATAL: Cannot connect to the server or authentication failed.")
            self.status_signal.emit("ERROR")
            self.is_running = False
            return

        self.log_signal.emit("Worker started successfully.")
        self.scheduler_signal.emit("PAUSED" if self.dispatch_paused else "WAITING")
        self.status_signal.emit("PAUSED" if self.dispatch_paused else "ONLINE")
        psutil.cpu_percent(interval=1)
        last_heartbeat = time.monotonic()

        while self.is_running:
            now = time.monotonic()
            if now - last_heartbeat >= float(self.poll_interval):
                self.send_heartbeat()
                last_heartbeat = now

            if self.dispatch_paused:
                time.sleep(0.25)
                continue

            try:
                response = self.session.post(
                    "{}/tasks/dispatch/".format(self.api_url),
                    json={
                        "worker_name": HOSTNAME,
                        "tags": build_capability_tags(self.discovered),
                        "capabilities": build_capabilities(self.discovered),
                        "capabilities_snapshot": self._last_system_info,
                    },
                    headers=self.get_headers(),
                    timeout=15,
                )
                self.connection_signal.emit(True)
                if response.status_code == 200:
                    task = response.json()
                    task_id = task.get("id", task.get("task_id", "unknown")) if isinstance(task, dict) else "unknown"
                    self.status_signal.emit("RENDERING")
                    self.scheduler_signal.emit("RUNNING TASK")
                    self.log_signal.emit("Received task {}.".format(task_id))
                    exit_status, log_path, error_tail, duration, out_img = self.run_task(task)
                    self.report_status(
                        str(task_id),
                        exit_status,
                        log_path=log_path,
                        error_tail=error_tail,
                        duration_seconds=duration,
                        output_image_path=out_img,
                    )
                    if self.pause_after_current:
                        self.dispatch_paused = True
                        self.scheduler_signal.emit("PAUSED")
                        self.log_signal.emit("Dispatch paused after the completed task.")
                    else:
                        self.scheduler_signal.emit("WAITING")
                    if self.is_running:
                        self.status_signal.emit("PAUSED" if self.dispatch_paused else "ONLINE")
                elif response.status_code in (204, 404):
                    time.sleep(float(self.poll_interval))
                else:
                    self.log_signal.emit("Dispatch error: HTTP {}".format(response.status_code))
                    time.sleep(float(self.poll_interval))
            except requests.exceptions.RequestException as error:
                self.connection_signal.emit(False)
                self.log_signal.emit("Dispatch connection error: {}".format(error))
                time.sleep(float(self.poll_interval))
            except Exception as error:
                self.log_signal.emit("Worker loop error: {}".format(error))
                time.sleep(float(self.poll_interval))

        self.current_task_id = ""
        self.scheduler_signal.emit("STOPPED")
        self.status_signal.emit("OFFLINE")

    def stop(self) -> None:
        self.is_running = False
        self.cancel_current_requested = True
        self.log_signal.emit("Worker stopping...")
        self.status_signal.emit("OFFLINE")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RenderHive Worker Settings")
        self.setMinimumSize(660, 600)
        self.settings = QSettings("RenderHive", "WorkerDaemon")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Worker Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 4, 0)
        body_layout.setSpacing(12)
        root.addWidget(scroll, 1)

        connection_card = SectionCard(
            "Backend Connection",
            "Connection changes take effect the next time the worker starts.",
        )
        connection_form = QFormLayout()
        connection_form.setHorizontalSpacing(18)
        connection_form.setVerticalSpacing(10)
        self.api_url_input = QLineEdit()
        self.api_url_input.setText(self.settings.value("api_url", "http://server.renderhive.local/api"))
        connection_form.addRow("API URL", self.api_url_input)
        self.api_token_input = QLineEdit()
        self.api_token_input.setText(self.settings.value("api_token", ""))
        self.api_token_input.setEchoMode(QLineEdit.Password)
        connection_form.addRow("API Token", self.api_token_input)
        connection_card.add_layout(connection_form)
        body_layout.addWidget(connection_card)

        profile_card = SectionCard(
            "Worker Identity",
            "These fields are published as worker metadata and help administrators identify the machine.",
        )
        profile_form = QFormLayout()
        profile_form.setHorizontalSpacing(18)
        profile_form.setVerticalSpacing(10)
        self.description_input = QLineEdit()
        self.description_input.setText(self.settings.value("description", ""))
        profile_form.addRow("Description", self.description_input)
        self.comment_input = QLineEdit()
        self.comment_input.setText(self.settings.value("comment", ""))
        profile_form.addRow("Comment", self.comment_input)
        self.region_input = QLineEdit()
        self.region_input.setText(self.settings.value("region", "Default"))
        profile_form.addRow("Region", self.region_input)
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Example: gpu, studio-a, overnight")
        self.tags_input.setText(self.settings.value("custom_tags", ""))
        profile_form.addRow("Custom Tags", self.tags_input)
        profile_card.add_layout(profile_form)
        body_layout.addWidget(profile_card)

        behavior_card = SectionCard("Scheduling & Startup")
        behavior_form = QFormLayout()
        behavior_form.setHorizontalSpacing(18)
        behavior_form.setVerticalSpacing(10)
        self.poll_interval_input = QSpinBox()
        self.poll_interval_input.setRange(2, 30)
        self.poll_interval_input.setSuffix(" seconds")
        self.poll_interval_input.setValue(int(self.settings.value("poll_interval", 5) or 5))
        behavior_form.addRow("Dispatch Interval", self.poll_interval_input)
        self.after_task_combo = QComboBox()
        self.after_task_combo.addItem("Continue to the next task", "continue")
        self.after_task_combo.addItem("Pause dispatch after the current task", "pause")
        saved_after = str(self.settings.value("after_task", "continue") or "continue")
        self.after_task_combo.setCurrentIndex(1 if saved_after == "pause" else 0)
        behavior_form.addRow("After Task", self.after_task_combo)
        self.auto_start_check = QCheckBox("Start the worker automatically when the application opens")
        self.auto_start_check.setChecked(str(self.settings.value("auto_start", "false")).lower() == "true")
        behavior_form.addRow("", self.auto_start_check)
        self.start_minimized_check = QCheckBox("Open minimized to the system tray")
        self.start_minimized_check.setChecked(str(self.settings.value("start_minimized", "false")).lower() == "true")
        behavior_form.addRow("", self.start_minimized_check)
        behavior_card.add_layout(behavior_form)
        body_layout.addWidget(behavior_card)

        detected_card = SectionCard("Detected Applications")
        self.detected_apps = QPlainTextEdit()
        self.detected_apps.setReadOnly(True)
        self.detected_apps.setMinimumHeight(190)
        detected_card.add_widget(self.detected_apps)
        refresh_btn = QPushButton("Refresh Detection")
        refresh_btn.setObjectName("SecondaryBtn")
        refresh_btn.clicked.connect(self.refresh_detection)
        detected_card.add_widget(refresh_btn)
        body_layout.addWidget(detected_card)
        body_layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        root.addLayout(buttons)

        self.refresh_detection()

    def refresh_detection(self) -> None:
        self.detected_apps.setPlainText(_format_installations(discover_all()))

    def save_settings(self) -> None:
        self.settings.setValue("api_url", self.api_url_input.text().strip())
        self.settings.setValue("api_token", self.api_token_input.text().strip())
        self.settings.setValue("description", self.description_input.text().strip())
        self.settings.setValue("comment", self.comment_input.text().strip())
        self.settings.setValue("region", self.region_input.text().strip() or "Default")
        self.settings.setValue("custom_tags", self.tags_input.text().strip())
        self.settings.setValue("poll_interval", self.poll_interval_input.value())
        self.settings.setValue("after_task", self.after_task_combo.currentData())
        self.settings.setValue("auto_start", self.auto_start_check.isChecked())
        self.settings.setValue("start_minimized", self.start_minimized_check.isChecked())
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RenderHive Worker {}".format(WORKER_VERSION))
        self.resize(800, 520)
        self.setMinimumSize(720, 470)
        self.is_quitting = False
        self.worker_status = "OFFLINE"
        self.scheduler_status = "STOPPED"
        self.backend_connected = False
        self.worker_started_monotonic = 0.0
        self.current_task: Dict[str, Any] = {}
        self.current_task_started = 0.0
        self.current_progress_percent = 0
        self.current_progress_target = 0
        self.progress_animator = SmoothProgressValue(0.0, 0.0)
        self.current_progress_phase = "Idle"
        self.current_progress_frame = None
        self.current_progress_total_frames = 1
        self.current_progress_eta_seconds = None
        self.last_system_info: Dict[str, Any] = {}
        self.server_worker: Dict[str, Any] = {}
        self.current_log_path = ""

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.settings = QSettings("RenderHive", "WorkerDaemon")
        self.worker_thread: WorkerThread | None = None
        self.discovered = discover_all()
        self.local_gpu_detector = GPUDetector()
        self._last_local_gpu_query = 0.0

        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        show_action = QAction("Show RenderHive Worker", self)
        show_action.triggered.connect(self.show_from_tray)
        pause_action = QAction("Pause / Resume Dispatch", self)
        pause_action.triggered.connect(self.toggle_dispatch_pause)
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(pause_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        QApplication.instance().aboutToQuit.connect(self.stop_worker)
        self._build_ui(icon_path)

        geometry = self.settings.value("compact_geometry_v131")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        try:
            self.main_tabs.setCurrentIndex(
                max(0, min(1, int(self.settings.value("compact_tab_v131", 0) or 0)))
            )
        except Exception:
            pass

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(1000)
        self.ui_timer.timeout.connect(self.update_live_ui)
        self.ui_timer.start()

        # Renderer output is often sparse (for example 1%, 25%, 75%, 100%).
        # Keep a separate high-frequency visual timer so the percentage label
        # counts through every integer and the bar moves continuously toward
        # the latest real renderer target without fabricating extra progress.
        self.progress_animation_timer = QTimer(self)
        self.progress_animation_timer.setInterval(25)
        self.progress_animation_timer.timeout.connect(self._animate_progress_tick)
        self.progress_animation_timer.start()

        self.refresh_dcc_tables()
        self.refresh_local_snapshot()
        self.log("Worker UI loaded. Detected: {}".format(self.short_dcc_summary()))

        auto_start = str(self.settings.value("auto_start", "false")).lower() == "true"
        start_minimized = str(self.settings.value("start_minimized", "false")).lower() == "true"
        if start_minimized:
            QTimer.singleShot(0, self.hide)
        if auto_start:
            QTimer.singleShot(250, self.start_worker)

    def _build_ui(self, icon_path: str) -> None:
        central = QWidget()
        central.setObjectName("RootWidget")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        header = QFrame()
        header.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 7, 10, 7)
        header_layout.setSpacing(8)

        if icon_path and os.path.exists(icon_path):
            logo = QLabel()
            logo.setObjectName("BrandLogo")
            logo.setFixedSize(32, 32)
            logo.setAlignment(Qt.AlignCenter)
            logo.setPixmap(QIcon(icon_path).pixmap(28, 28))
            header_layout.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 6, 0)
        title_box.setSpacing(1)
        title = QLabel("RENDERHIVE WORKER")
        title.setObjectName("TitleLabel")
        subtitle = QLabel(HOSTNAME)
        subtitle.setObjectName("MutedLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.setStretchFactor(title_box, 0)

        self.header_status_chip = StatusChip("OFFLINE")
        self.header_connection_chip = StatusChip("DISCONNECTED")
        header_layout.addWidget(self.header_status_chip)
        header_layout.addWidget(self.header_connection_chip)

        self.header_dcc_label = QLabel(self.short_dcc_summary().replace("\n", "  |  "))
        self.header_dcc_label.setObjectName("CompactBadge")
        self.header_dcc_label.setMinimumWidth(150)
        self.header_dcc_label.setAlignment(Qt.AlignCenter)
        self.header_dcc_label.setToolTip(_format_installations(self.discovered))
        header_layout.addWidget(self.header_dcc_label, 1)

        version_label = QLabel("v{}".format(WORKER_VERSION))
        version_label.setObjectName("VersionLabel")
        header_layout.addWidget(version_label)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("SecondaryBtn")
        self.settings_btn.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_btn)

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_worker)
        header_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("DestructiveBtn")
        self.stop_btn.clicked.connect(self.stop_worker)
        self.stop_btn.setEnabled(False)
        header_layout.addWidget(self.stop_btn)
        outer.addWidget(header)

        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("MainTabs")
        self.page_stack = self.main_tabs
        self.nav_buttons = []
        self.main_tabs.addTab(self.build_job_page(), "Job Information")
        self.main_tabs.addTab(self.build_worker_page(), "Worker Information")
        outer.addWidget(self.main_tabs, 1)

        command_bar = QFrame()
        command_bar.setObjectName("CommandBar")
        command_layout = QHBoxLayout(command_bar)
        command_layout.setContentsMargins(9, 6, 9, 6)
        command_layout.setSpacing(6)

        self.pause_dispatch_btn = QPushButton("Pause Dispatch")
        self.pause_dispatch_btn.setObjectName("SecondaryBtn")
        self.pause_dispatch_btn.clicked.connect(self.toggle_dispatch_pause)
        self.pause_dispatch_btn.setEnabled(False)
        command_layout.addWidget(self.pause_dispatch_btn)

        self.after_task_btn = QPushButton("Pause After Task")
        self.after_task_btn.setObjectName("SecondaryBtn")
        self.after_task_btn.setCheckable(True)
        self.after_task_btn.clicked.connect(self.toggle_pause_after_task)
        self.after_task_btn.setEnabled(False)
        command_layout.addWidget(self.after_task_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("SecondaryBtn")
        refresh_btn.clicked.connect(self.refresh_server_data)
        command_layout.addWidget(refresh_btn)

        self.footer_scheduler_label = QLabel("Scheduler: Stopped")
        self.footer_scheduler_label.setObjectName("SchedulerHint")
        command_layout.addWidget(self.footer_scheduler_label)
        command_layout.addStretch()

        self.log_preview_label = QLabel("Ready")
        self.log_preview_label.setObjectName("LogPreview")
        self.log_preview_label.setMinimumWidth(180)
        self.log_preview_label.setToolTip("Latest worker event")
        command_layout.addWidget(self.log_preview_label, 1)

        self.log_toggle_btn = QPushButton("Show Log")
        self.log_toggle_btn.setObjectName("GhostBtn")
        self.log_toggle_btn.clicked.connect(self.toggle_log_drawer)
        command_layout.addWidget(self.log_toggle_btn)
        outer.addWidget(command_bar)

        self.log_drawer = QFrame()
        self.log_drawer.setObjectName("LogDrawer")
        log_layout = QVBoxLayout(self.log_drawer)
        log_layout.setContentsMargins(10, 8, 10, 10)
        log_layout.setSpacing(6)

        log_tools = QHBoxLayout()
        self.log_search_input = QLineEdit()
        self.log_search_input.setPlaceholderText("Find in log")
        self.log_search_input.returnPressed.connect(self.find_in_log)
        log_tools.addWidget(self.log_search_input, 1)

        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("SecondaryBtn")
        copy_btn.clicked.connect(self.copy_log_view)
        log_tools.addWidget(copy_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.clicked.connect(self.clear_log_view)
        log_tools.addWidget(clear_btn)

        open_btn = QPushButton("Open Folder")
        open_btn.setObjectName("SecondaryBtn")
        open_btn.clicked.connect(self.open_log_folder)
        log_tools.addWidget(open_btn)
        log_layout.addLayout(log_tools)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(5000)
        self.log_console.setMinimumHeight(118)
        self.log_console.setMaximumHeight(170)
        log_layout.addWidget(self.log_console)

        expanded = str(self.settings.value("compact_log_expanded_v131", "false")).lower() == "true"
        self.log_drawer.setVisible(expanded)
        self.log_toggle_btn.setText("Hide Log" if expanded else "Show Log")
        outer.addWidget(self.log_drawer)

    def page_container(self, title: str = "", subtitle: str = ""):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        page.setObjectName("PageRoot")
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(8)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("SectionTitle")
            if subtitle:
                title_label.setToolTip(subtitle)
            layout.addWidget(title_label)
        return scroll, layout

    def build_overview_page(self) -> QWidget:
        return self.build_worker_page()

    def build_job_page(self) -> QWidget:
        page, layout = self.page_container()
        self.job_state_stack = QStackedWidget()
        self.job_state_stack.setObjectName("JobStateStack")

        empty_page = QWidget()
        empty_page.setObjectName("EmptyStatePage")
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.addStretch(1)
        self.job_empty = EmptyState(
            "No active task",
            "Start the worker, then submit a compatible Maya or Houdini job.",
        )
        self.job_empty.setMaximumWidth(390)
        self.job_empty.setMinimumWidth(320)
        empty_row = QHBoxLayout()
        empty_row.addStretch(1)
        empty_row.addWidget(self.job_empty)
        empty_row.addStretch(1)
        empty_layout.addLayout(empty_row)
        empty_layout.addStretch(1)
        self.job_state_stack.addWidget(empty_page)

        active = QWidget()
        active_layout = QVBoxLayout(active)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(8)

        progress_card = SectionCard()
        progress_header = QHBoxLayout()
        self.job_title_label = QLabel("Current Job")
        self.job_title_label.setObjectName("TitleLabel")
        self.job_status_chip = StatusChip("OFFLINE")
        self.job_elapsed_label = QLabel("Elapsed: 00h 00m 00s")
        self.job_elapsed_label.setObjectName("MutedLabel")
        self.cancel_task_btn = QPushButton("Cancel Task")
        self.cancel_task_btn.setObjectName("DestructiveBtn")
        self.cancel_task_btn.clicked.connect(self.cancel_current_task)
        self.cancel_task_btn.setEnabled(False)
        progress_header.addWidget(self.job_title_label)
        progress_header.addWidget(self.job_status_chip)
        progress_header.addStretch()
        progress_header.addWidget(self.job_elapsed_label)
        progress_header.addWidget(self.cancel_task_btn)
        progress_card.add_layout(progress_header)

        progress_meta = QHBoxLayout()
        progress_meta.setSpacing(8)
        self.job_phase_label = QLabel("Preparing Task")
        self.job_phase_label.setObjectName("AccentLabel")
        self.job_frame_label = QLabel("Frame — / —")
        self.job_frame_label.setObjectName("MutedLabel")
        self.job_eta_label = QLabel("Remaining: Estimating…")
        self.job_eta_label.setObjectName("MutedLabel")
        self.job_percent_label = QLabel("0%")
        self.job_percent_label.setObjectName("ProgressPercent")
        progress_meta.addWidget(self.job_phase_label)
        progress_meta.addWidget(self.job_frame_label)
        progress_meta.addStretch()
        progress_meta.addWidget(self.job_eta_label)
        progress_meta.addWidget(self.job_percent_label)
        progress_card.add_layout(progress_meta)

        self.job_progress = QProgressBar()
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(0)
        self.job_progress.setTextVisible(False)
        progress_card.add_widget(self.job_progress)
        self.job_progress_detail = QLabel("Waiting for a task")
        self.job_progress_detail.setObjectName("MutedLabel")
        progress_card.add_widget(self.job_progress_detail)
        active_layout.addWidget(progress_card)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)

        job_card = SectionCard("Job")
        self.job_info = InfoGrid(
            [
                ("job_name", "Name"),
                ("job_user", "User"),
                ("department", "Department"),
                ("pool", "Pool"),
                ("priority", "Priority"),
                ("submit_date", "Submitted"),
            ],
            columns=2,
        )
        job_card.add_widget(self.job_info)
        summary_row.addWidget(job_card, 1)

        task_card = SectionCard("Task")
        self.task_info = InfoGrid(
            [
                ("task_id", "Task ID"),
                ("frame_range", "Frames"),
                ("dcc", "Application"),
                ("dcc_version", "Version"),
                ("renderer", "Renderer"),
                ("execution_mode", "Mode"),
                ("phase", "Phase"),
                ("progress_display", "Progress"),
                ("render_node", "Render Node"),
                ("exit_code", "Exit Code"),
            ],
            columns=2,
        )
        task_card.add_widget(self.task_info)
        summary_row.addWidget(task_card, 1)
        active_layout.addLayout(summary_row)

        path_card = SectionCard("Scene & Output")
        self.path_info = InfoGrid(
            [
                ("scene_path", "Scene"),
                ("output_path", "Output"),
            ],
            columns=1,
        )
        path_card.add_widget(self.path_info)
        active_layout.addWidget(path_card)
        active_layout.addStretch()

        self.job_state_stack.addWidget(active)
        layout.addWidget(self.job_state_stack)
        return page

    def build_worker_page(self) -> QWidget:
        page, layout = self.page_container()

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.status_card = StatCard("Worker", "Offline", HOSTNAME)
        self.scheduler_card = StatCard("Scheduler", "Stopped", "Not accepting tasks")
        completed = int(self.settings.value("completed_tasks", 0) or 0)
        failed = int(self.settings.value("failed_tasks", 0) or 0)
        self.history_card = StatCard("Task History", "{} complete".format(completed), "{} failed".format(failed))
        top_row.addWidget(self.status_card, 1)
        top_row.addWidget(self.scheduler_card, 1)
        top_row.addWidget(self.history_card, 1)
        layout.addLayout(top_row)

        details_row = QHBoxLayout()
        details_row.setSpacing(8)

        schedule_card = SectionCard("Worker & Scheduler")
        self.worker_schedule_info = InfoGrid(
            [
                ("worker_status", "Worker Status"),
                ("scheduler_status", "Scheduler"),
                ("backend", "Backend"),
                ("running_time", "Running Time"),
                ("after_task", "After Task"),
                ("pools", "Assigned Pools"),
                ("completed", "Completed"),
                ("failed", "Failed"),
            ],
            columns=2,
        )
        schedule_card.add_widget(self.worker_schedule_info)
        details_row.addWidget(schedule_card, 1)

        specs_card = SectionCard("Machine")
        self.worker_specs_info = InfoGrid(
            [
                ("os", "Operating System"),
                ("user", "User"),
                ("cpu", "CPU"),
                ("memory", "Memory"),
                ("gpu", "GPU"),
                ("ip", "IP Address"),
                ("disk", "Free Disk"),
                ("last_ping", "Last Ping"),
            ],
            columns=2,
        )
        specs_card.add_widget(self.worker_specs_info)
        details_row.addWidget(specs_card, 1)
        layout.addLayout(details_row)

        metrics_card = SectionCard("Live Utilization")
        metrics = QGridLayout()
        metrics.setSpacing(8)
        self.cpu_meter = ResourceMeter("CPU")
        self.memory_meter = ResourceMeter("Memory")
        self.disk_meter = ResourceMeter("Disk")
        self.gpu_meter = ResourceMeter("GPU")
        metrics.addWidget(self.cpu_meter, 0, 0)
        metrics.addWidget(self.memory_meter, 0, 1)
        metrics.addWidget(self.disk_meter, 1, 0)
        metrics.addWidget(self.gpu_meter, 1, 1)
        metrics_card.add_layout(metrics)
        layout.addWidget(metrics_card)

        dcc_card = SectionCard("Render Applications")
        dcc_row = QHBoxLayout()
        self.dcc_summary_label = QLabel(self.short_dcc_summary().replace("\n", "  |  "))
        self.dcc_summary_label.setObjectName("FieldValue")
        self.dcc_summary_label.setToolTip(_format_installations(self.discovered))
        dcc_row.addWidget(self.dcc_summary_label, 1)
        details_btn = QPushButton("View Details")
        details_btn.setObjectName("SecondaryBtn")
        details_btn.clicked.connect(self.show_dcc_details)
        dcc_row.addWidget(details_btn)
        dcc_card.add_layout(dcc_row)
        layout.addWidget(dcc_card)
        layout.addStretch()

        self.current_job_card = None
        self.overview_dcc_table = None
        self.worker_dcc_table = None
        return page

    def build_logs_page(self) -> QWidget:
        page, layout = self.page_container()
        message = EmptyState("Logs moved", "Use the Show Log button at the bottom of the window.")
        layout.addWidget(message)
        return page

    def create_dcc_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Application", "Version", "Executables", "Install Root"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        return table

    def refresh_dcc_tables(self) -> None:
        summary = self.short_dcc_summary().replace("\n", "  |  ")
        detail = _format_installations(self.discovered)
        if hasattr(self, "header_dcc_label"):
            self.header_dcc_label.setText(summary)
            self.header_dcc_label.setToolTip(detail)
        if hasattr(self, "dcc_summary_label"):
            self.dcc_summary_label.setText(summary)
            self.dcc_summary_label.setToolTip(detail)

    def short_dcc_summary(self) -> str:
        maya_versions = [item.version for item in self.discovered.get("maya") or []]
        houdini_versions = [item.version for item in self.discovered.get("houdini") or []]
        lines = []
        lines.append("Maya {}".format(", ".join(maya_versions)) if maya_versions else "Maya unavailable")
        lines.append("Houdini {}".format(", ".join(houdini_versions)) if houdini_versions else "Houdini unavailable")
        return "\n".join(lines)

    def worker_profile(self) -> Dict[str, Any]:
        return {
            "description": self.settings.value("description", ""),
            "comment": self.settings.value("comment", ""),
            "region": self.settings.value("region", "Default"),
            "custom_tags": self.settings.value("custom_tags", ""),
            "poll_interval": int(self.settings.value("poll_interval", 5) or 5),
            "after_task": self.settings.value("after_task", "continue"),
            "start_paused": False,
        }

    def switch_page(self, index: int) -> None:
        if hasattr(self, "main_tabs"):
            self.main_tabs.setCurrentIndex(max(0, min(index, self.main_tabs.count() - 1)))

    @Slot(str)
    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        text = str(message or "")
        lines = text.splitlines() or [""]
        for line in lines:
            self.log_console.appendPlainText("[{}] {}".format(timestamp, line))
        cursor = self.log_console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_console.setTextCursor(cursor)
        latest = lines[-1].strip() or "Ready"
        self.log_preview_label.setText(latest)
        self.log_preview_label.setToolTip(text)

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.worker_status = str(status or "OFFLINE").upper()
        self.header_status_chip.set_status(self.worker_status)
        self.status_card.set_value(self.worker_status.title(), HOSTNAME)
        self.worker_schedule_info.set_value("worker_status", self.worker_status.title())

    @Slot(str)
    def update_scheduler(self, status: str) -> None:
        self.scheduler_status = str(status or "STOPPED").upper()
        detail = {
            "WAITING": "Accepting compatible tasks",
            "PAUSED": "Dispatch is paused",
            "RUNNING TASK": "Rendering the current task",
            "STOPPED": "Worker is not running",
        }.get(self.scheduler_status, "")
        self.scheduler_card.set_value(self.scheduler_status.title(), detail)
        self.worker_schedule_info.set_value("scheduler_status", self.scheduler_status.title())
        self.footer_scheduler_label.setText("Scheduler: {}".format(self.scheduler_status.title()))
        self.pause_dispatch_btn.setText("Resume Dispatch" if self.scheduler_status == "PAUSED" else "Pause Dispatch")

    def update_connection(self, connected: bool) -> None:
        self.backend_connected = bool(connected)
        self.header_connection_chip.set_status("CONNECTED" if connected else "DISCONNECTED")
        self.worker_schedule_info.set_value("backend", "Yes" if connected else "No")

    @Slot(object)
    def update_system_info(self, info: object) -> None:
        self.last_system_info = safe_dict(info)
        self.apply_system_info(self.last_system_info)

    @Slot(object)
    def update_server_worker(self, worker: object) -> None:
        self.server_worker = safe_dict(worker)
        pools = pool_names_from_worker(self.server_worker)
        self.worker_schedule_info.set_value("pools", ", ".join(pools) if pools else "Unassigned")
        self.worker_specs_info.set_value("last_ping", format_timestamp(self.server_worker.get("last_ping")))
        tags = self.server_worker.get("tags")
        self.worker_schedule_info.set_value("groups", ", ".join(tags or []) if tags else "—")

    @Slot(object)
    def on_task_started(self, payload: object) -> None:
        self.current_task = safe_dict(payload)
        self.current_task_started = time.monotonic()
        initial_target = max(1, min(100, int(self.current_task.get("progress") or 1)))
        self.current_progress_percent = 1
        self.current_progress_target = initial_target
        self.progress_animator.reset(1.0)
        self.progress_animator.set_target(initial_target)
        self.current_progress_phase = safe_text(self.current_task.get("phase"), "Preparing Task")
        self.current_progress_frame = self.current_task.get("current_frame")
        self.current_progress_total_frames = max(1, int(self.current_task.get("total_frames") or 1))
        self.current_progress_eta_seconds = None
        self.job_state_stack.setCurrentIndex(1)
        self.job_title_label.setText(safe_text(self.current_task.get("job_name"), "Current Job"))
        self.job_status_chip.set_status("RENDERING")
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(self.progress_animator.bar_value)
        self.job_percent_label.setText("{}%".format(self.current_progress_percent))
        self.job_phase_label.setText(self.current_progress_phase)
        self.job_frame_label.setText(self._progress_frame_text())
        self.job_eta_label.setText("Remaining: Estimating…")
        self.job_progress_detail.setText(
            "Frames {}  •  {} {}  •  {}".format(
                safe_text(self.current_task.get("frame_range"), "—"),
                safe_text(self.current_task.get("dcc"), "DCC"),
                safe_text(self.current_task.get("dcc_version")),
                safe_text(self.current_task.get("renderer"), "Renderer not specified"),
            )
        )
        self.current_task["progress_display"] = "{}%".format(self.current_progress_percent)
        self.cancel_task_btn.setEnabled(True)
        self.job_info.set_values(self.current_task)
        self.task_info.set_values(self.current_task)
        self.path_info.set_values(self.current_task)

    @Slot(object)
    def on_task_progress(self, payload: object) -> None:
        data = safe_dict(payload)
        percent = max(0, min(100, int(data.get("percent") or 0)))
        phase = safe_text(data.get("phase"), self.current_progress_phase, "Rendering")
        self.current_progress_target = max(self.current_progress_target, percent)
        self.progress_animator.set_target(self.current_progress_target)
        self.current_progress_phase = phase
        self.current_progress_frame = data.get("current_frame")
        self.current_progress_total_frames = max(1, int(data.get("total_frames") or self.current_progress_total_frames or 1))
        eta = data.get("eta_seconds")
        try:
            self.current_progress_eta_seconds = max(0.0, float(eta)) if eta is not None else None
        except Exception:
            self.current_progress_eta_seconds = None

        self.current_task.update(data)
        self.current_task["progress_target"] = percent
        self.current_task["progress"] = self.current_progress_percent
        self.current_task["progress_display"] = "{}%".format(self.current_progress_percent)
        self.current_task["phase"] = phase

        self.job_phase_label.setText(phase)
        self.job_frame_label.setText(self._progress_frame_text())
        self.job_eta_label.setText(self._progress_eta_text())
        detail = safe_text(data.get("detail"))
        renderer_percent = data.get("renderer_percent")
        if renderer_percent is not None:
            try:
                renderer_text = "Renderer {:.0f}%".format(float(renderer_percent))
                detail = "{}  •  {}".format(detail, renderer_text) if detail else renderer_text
            except Exception:
                pass
        self.job_progress_detail.setText(detail or phase)
        self.task_info.set_value("phase", phase)
        self.task_info.set_value("progress_display", "{}%".format(self.current_progress_percent))

    @Slot(object)
    def on_task_finished(self, payload: object) -> None:
        data = safe_dict(payload)
        self.current_task = data
        self.current_task_started = 0.0
        final_target = max(0, min(100, int(data.get("progress") or 0)))
        self.current_progress_target = 100 if safe_text(data.get("status"), "FAILED").upper() == "SUCCEEDED" else max(self.current_progress_target, final_target)
        self.progress_animator.set_target(self.current_progress_target)
        self.current_progress_phase = safe_text(data.get("phase"), data.get("status"), "Finished")
        self.current_progress_frame = data.get("current_frame")
        self.current_progress_total_frames = max(1, int(data.get("total_frames") or 1))
        self.current_progress_eta_seconds = None
        status = safe_text(data.get("status"), "FAILED").upper()
        self.job_status_chip.set_status("ONLINE" if status == "SUCCEEDED" else "ERROR")
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(self.progress_animator.bar_value)
        self.job_percent_label.setText("{}%".format(self.current_progress_percent))
        self.job_phase_label.setText("Complete" if status == "SUCCEEDED" else self.current_progress_phase)
        self.job_frame_label.setText(self._progress_frame_text())
        self.job_eta_label.setText("Remaining: 00h 00m 00s" if status == "SUCCEEDED" else "Remaining: —")
        data["progress_target"] = self.current_progress_target
        data["progress"] = self.current_progress_percent
        data["progress_display"] = "{}%".format(self.current_progress_percent)
        self.job_progress_detail.setText(
            "{}  •  {}  •  Exit code {}".format(
                status.title(),
                format_duration(data.get("duration_seconds")),
                data.get("exit_code", "—"),
            )
        )
        self.cancel_task_btn.setEnabled(False)
        self.job_info.set_values(data)
        self.task_info.set_values(data)
        self.path_info.set_values(data)
        self.current_log_path = safe_text(data.get("log_path"))

        completed = int(self.settings.value("completed_tasks", 0) or 0)
        failed = int(self.settings.value("failed_tasks", 0) or 0)
        if status == "SUCCEEDED":
            completed += 1
        else:
            failed += 1
        self.settings.setValue("completed_tasks", completed)
        self.settings.setValue("failed_tasks", failed)
        self.history_card.set_value("{} complete".format(completed), "{} failed".format(failed))
        self.worker_schedule_info.set_value("completed", completed)
        self.worker_schedule_info.set_value("failed", failed)

    def apply_system_info(self, info: Dict[str, Any]) -> None:
        if not info:
            return
        cpu_percent = float(info.get("cpu_percent") or 0)
        memory_percent = float(info.get("memory_percent") or 0)
        disk_percent = float(info.get("disk_percent") or 0)
        gpu_percent = float(info.get("gpu_percent") or 0)
        total_memory = int(info.get("total_memory_mb") or 0) * 1024 * 1024
        used_memory = int(info.get("memory_used_mb") or 0) * 1024 * 1024
        self.cpu_meter.set_metric(
            cpu_percent,
            "{} logical cores".format(info.get("cpu_count") or "—"),
        )
        self.memory_meter.set_metric(
            memory_percent,
            "{} / {}".format(format_bytes(used_memory), format_bytes(total_memory)),
        )
        self.disk_meter.set_metric(
            disk_percent,
            "{} free".format(format_bytes(info.get("disk_free_bytes"))),
        )
        gpu_name = safe_text(info.get("gpu_name"), "Not detected")
        gpu_detail = gpu_name
        if info.get("gpu_vram_mb"):
            if info.get("gpu_telemetry_available"):
                gpu_detail = "{}  •  {} / {} VRAM".format(
                    gpu_name,
                    format_bytes(int(info.get("gpu_vram_used_mb") or 0) * 1024 * 1024),
                    format_bytes(int(info.get("gpu_vram_mb") or 0) * 1024 * 1024),
                )
            else:
                gpu_detail = "{}  •  {} VRAM".format(
                    gpu_name,
                    format_bytes(int(info.get("gpu_vram_mb") or 0) * 1024 * 1024),
                )
        if info.get("gpu_name") and not info.get("gpu_telemetry_available"):
            self.gpu_meter.set_unavailable(gpu_detail + "  •  Usage unavailable")
        else:
            self.gpu_meter.set_metric(gpu_percent, gpu_detail)

        self.worker_specs_info.set_values(
            {
                "os": safe_text(info.get("operating_system"), info.get("platform")),
                "user": safe_text(info.get("machine_user")),
                "cpu": safe_text(info.get("cpu_name"), platform.processor()),
                "cores": "{} / {}".format(
                    info.get("cpu_count") or "—",
                    info.get("physical_cpu_count") or "—",
                ),
                "memory": "{} / {} ({}%)".format(
                    format_bytes(used_memory),
                    format_bytes(total_memory),
                    int(round(memory_percent)),
                ),
                "ip": safe_text(info.get("ip_address")),
                "mac": safe_text(info.get("mac_address")),
                "disk": "{} of {}".format(
                    format_bytes(info.get("disk_free_bytes")),
                    format_bytes(info.get("disk_total_bytes")),
                ),
                "gpu": gpu_name,
                "gpu_usage": (
                    "{}%".format(int(round(gpu_percent)))
                    if info.get("gpu_name") and info.get("gpu_telemetry_available")
                    else ("N/A" if info.get("gpu_name") else "—")
                ),
                "worker_version": safe_text(info.get("worker_version"), WORKER_VERSION),
            }
        )

    def refresh_local_snapshot(self) -> None:
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(_disk_root())
            snapshot = dict(self.last_system_info)
            now = time.monotonic()
            if now - self._last_local_gpu_query >= 5.0:
                snapshot.update(self.local_gpu_detector.query())
                self._last_local_gpu_query = now
            snapshot.update(
                {
                    "operating_system": "{} {}".format(platform.system(), platform.release()).strip(),
                    "machine_user": machine_user(),
                    "cpu_name": snapshot.get("cpu_name") or platform.processor(),
                    "cpu_count": psutil.cpu_count(logical=True),
                    "physical_cpu_count": psutil.cpu_count(logical=False),
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "memory_percent": memory.percent,
                    "memory_used_mb": (memory.total - memory.available) // (1024 * 1024),
                    "total_memory_mb": memory.total // (1024 * 1024),
                    "disk_total_bytes": disk.total,
                    "disk_free_bytes": disk.free,
                    "disk_percent": disk.percent,
                    "ip_address": local_ip_address(),
                    "mac_address": mac_address(),
                    "worker_version": WORKER_VERSION,
                }
            )
            self.apply_system_info(snapshot)
        except Exception:
            pass

    def _apply_progress_visual(self) -> None:
        """Keep the percentage label and bar locked to the same visual value."""
        self.current_progress_percent = self.progress_animator.display_percent
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(self.progress_animator.bar_value)
        self.job_percent_label.setText("{}%".format(self.current_progress_percent))
        if self.current_task:
            self.current_task["progress"] = self.current_progress_percent
            self.current_task["progress_display"] = "{}%".format(self.current_progress_percent)
            self.current_task["progress_target"] = self.current_progress_target
            self.task_info.set_value("progress_display", "{}%".format(self.current_progress_percent))

    def _animate_progress_tick(self) -> None:
        """Animate through every percentage toward the latest real target.

        A sub-one-percent step guarantees that the visible counter cannot skip
        an integer.  Completion is slightly faster so a finished task reaches
        100% promptly while still showing 91, 92, ... 100 in sequence.
        """
        if not self.current_task:
            return
        self.progress_animator.set_target(self.current_progress_target)
        step = 0.80 if self.current_progress_target >= 100 else 0.50
        previous = self.progress_animator.current
        current = self.progress_animator.tick(step=step)
        if current != previous or self.current_progress_percent != self.progress_animator.display_percent:
            self._apply_progress_visual()

    def _progress_frame_text(self) -> str:
        total = max(1, int(self.current_progress_total_frames or 1))
        frame = self.current_progress_frame
        if frame is None:
            completed = int(self.current_task.get("completed_frames") or 0) if self.current_task else 0
            if completed > 0:
                return "Frames {} / {}".format(min(completed, total), total)
            return "Frame — / {}".format(total)

        try:
            start = int(self.current_task.get("frame_start") or frame)
            step = max(1, int(self.current_task.get("frame_step") or 1))
            index = ((int(frame) - start) // step) + 1
            index = max(1, min(total, index))
        except Exception:
            index = max(1, int(self.current_task.get("completed_frames") or 0) + 1)
        return "Frame {} / {}".format(index, total)

    def _progress_eta_text(self) -> str:
        eta_percent = max(self.current_progress_percent, self.current_progress_target)
        if eta_percent >= 100:
            return "Remaining: 00h 00m 00s"
        if not self.current_task_started or eta_percent < 5:
            return "Remaining: Estimating…"

        elapsed = max(0.0, time.monotonic() - self.current_task_started)
        completed = int(self.current_task.get("completed_frames") or 0) if self.current_task else 0
        total = max(1, int(self.current_progress_total_frames or 1))
        if total > 1 and completed > 0:
            remaining = (elapsed / float(completed)) * max(0, total - completed)
        else:
            remaining = elapsed * (
                (100.0 - float(eta_percent))
                / max(1.0, float(eta_percent))
            )
        remaining = max(0.0, min(remaining, 7.0 * 24.0 * 60.0 * 60.0))
        return "Remaining: ~{}".format(format_duration(remaining))

    def update_live_ui(self) -> None:
        self.refresh_local_snapshot()
        if self.worker_started_monotonic:
            runtime = time.monotonic() - self.worker_started_monotonic
        else:
            runtime = 0
        self.worker_schedule_info.set_value("running_time", format_duration(runtime))
        self.worker_schedule_info.set_value(
            "after_task",
            "Pause" if self.after_task_btn.isChecked() else "Continue",
        )
        if self.current_task_started:
            self.job_elapsed_label.setText(
                "Elapsed: {}".format(format_duration(time.monotonic() - self.current_task_started))
            )
            self.job_eta_label.setText(self._progress_eta_text())
            self._apply_progress_visual()
            self.job_phase_label.setText(self.current_progress_phase)
            self.job_frame_label.setText(self._progress_frame_text())
        elif self.current_task:
            self.job_elapsed_label.setText(
                "Duration: {}".format(format_duration(self.current_task.get("duration_seconds")))
            )
        profile = self.worker_profile()
        self.worker_schedule_info.set_values(
            {
                "region": safe_text(profile.get("region"), "Default"),
                "description": safe_text(profile.get("description"), "—"),
                "comment": safe_text(profile.get("comment"), "—"),
                "dequeue_mode": "Compatible Jobs",
                "concurrent_limit": "1 (single DCC process)",
                "completed": int(self.settings.value("completed_tasks", 0) or 0),
                "failed": int(self.settings.value("failed_tasks", 0) or 0),
            }
        )

    def toggle_log_drawer(self) -> None:
        visible = not self.log_drawer.isVisible()
        self.log_drawer.setVisible(visible)
        self.log_toggle_btn.setText("Hide Log" if visible else "Show Log")
        self.settings.setValue("compact_log_expanded_v131", visible)
        if visible:
            self.log_console.setFocus()

    def show_dcc_details(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Detected Render Applications")
        dialog.resize(720, 360)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        table = self.create_dcc_table()
        rows = _installation_rows(self.discovered)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                table.setItem(row_index, column_index, item)
        root.addWidget(table, 1)
        buttons = QHBoxLayout()
        buttons.addStretch()
        refresh = QPushButton("Refresh Detection")
        refresh.setObjectName("SecondaryBtn")
        refresh.clicked.connect(lambda: self._refresh_dcc_dialog(table))
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(refresh)
        buttons.addWidget(close)
        root.addLayout(buttons)
        dialog.exec()

    def _refresh_dcc_dialog(self, table: QTableWidget) -> None:
        self.discovered = discover_all()
        self.refresh_dcc_tables()
        rows = _installation_rows(self.discovered)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                table.setItem(row_index, column_index, item)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.discovered = discover_all()
            self.refresh_dcc_tables()
            self.log("Settings saved. Connection and scheduling defaults apply on the next worker start.")

    def start_worker(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            return
        api_url = str(self.settings.value("api_url", "") or "").strip()
        api_token = str(self.settings.value("api_token", "") or "").strip()
        if not api_url or not api_token:
            QMessageBox.warning(
                self,
                "Missing Configuration",
                "Open Settings and provide the Backend API URL and Token.",
            )
            return

        self.discovered = discover_all()
        self.refresh_dcc_tables()
        profile = self.worker_profile()
        self.worker_thread = WorkerThread(api_url, api_token, self.discovered, profile)
        self.worker_thread.log_signal.connect(self.log)
        self.worker_thread.status_signal.connect(self.update_status)
        self.worker_thread.scheduler_signal.connect(self.update_scheduler)
        self.worker_thread.connection_signal.connect(self.update_connection)
        self.worker_thread.system_info_signal.connect(self.update_system_info)
        self.worker_thread.server_worker_signal.connect(self.update_server_worker)
        self.worker_thread.task_started_signal.connect(self.on_task_started)
        self.worker_thread.task_progress_signal.connect(self.on_task_progress)
        self.worker_thread.task_finished_signal.connect(self.on_task_finished)
        self.worker_thread.capabilities_signal.connect(lambda text: self.dcc_summary_label.setToolTip(text))
        self.worker_thread.finished.connect(self.on_worker_finished)
        self.worker_thread.start()

        self.worker_started_monotonic = time.monotonic()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_dispatch_btn.setEnabled(True)
        self.after_task_btn.setEnabled(True)
        self.after_task_btn.setChecked(str(profile.get("after_task")) == "pause")

    def stop_worker(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()

    def on_worker_finished(self) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_dispatch_btn.setEnabled(False)
        self.after_task_btn.setEnabled(False)
        self.worker_started_monotonic = 0.0
        self.update_status("OFFLINE")
        self.update_scheduler("STOPPED")
        self.update_connection(False)
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    def toggle_dispatch_pause(self) -> None:
        if not self.worker_thread or not self.worker_thread.isRunning():
            return
        should_pause = self.scheduler_status != "PAUSED"
        self.worker_thread.set_dispatch_paused(should_pause)

    def toggle_pause_after_task(self, checked: bool) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.set_pause_after_current(bool(checked))
        self.settings.setValue("after_task", "pause" if checked else "continue")

    def cancel_current_task(self) -> None:
        if not self.worker_thread or not self.current_task_started:
            return
        answer = QMessageBox.question(
            self,
            "Cancel Current Task",
            "Stop the running DCC process and report this task as failed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.worker_thread.cancel_current_task()

    def refresh_server_data(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.request_profile_refresh()
            self.log("Server data refresh requested.")
        else:
            self.log("Start the worker before refreshing server assignments.")

    def open_log_folder(self) -> None:
        path = writable_log_root()
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def clear_log_view(self) -> None:
        self.log_console.clear()

    def copy_log_view(self) -> None:
        QApplication.clipboard().setText(self.log_console.toPlainText())

    def find_in_log(self) -> None:
        text = self.log_search_input.text().strip()
        if not text:
            return
        if not self.log_console.find(text):
            cursor = self.log_console.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_console.setTextCursor(cursor)
            self.log_console.find(text)

    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.show_from_tray()

    def quit_app(self) -> None:
        self.is_quitting = True
        self.stop_worker()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.wait(5000)
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        self.settings.setValue("compact_geometry_v131", self.saveGeometry())
        self.settings.setValue("compact_tab_v131", self.main_tabs.currentIndex())
        if self.is_quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "RenderHive Worker",
            "Worker continues in the system tray.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )


def main() -> int:
    app = QApplication(sys.argv)
    shared_memory = QSharedMemory("RenderHiveWorkerSingleton")
    if not shared_memory.create(1):
        QMessageBox.warning(None, "Already Running", "RenderHive Worker is already running.")
        return 0

    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "renderhive.worker.multidcc.{}".format(WORKER_VERSION)
        )

    app.setStyleSheet(APP_STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
