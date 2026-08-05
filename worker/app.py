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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from adapters import AdapterFactory
from adapters.base import AdapterError
from core.dcc_discovery import (
    DCCInstallation,
    build_capabilities,
    build_capability_tags,
    discover_all,
)
from core.process_runner import run_process
from core.runtime_paths import writable_log_root
from core.task_normalizer import normalize_task
from core.ui_helpers import (
    build_task_ui_payload,
    extract_progress_frame,
    format_bytes,
    format_duration,
    format_timestamp,
    frame_progress_percent,
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
        self.started_monotonic = time.monotonic()
        self.last_worker_profile_fetch = 0.0
        self.poll_interval = max(2, min(30, int(self.profile.get("poll_interval", 5) or 5)))
        self._last_progress_frame = None

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

        gpu_models: List[str] = []
        try:
            nvidia_smi = shutil.which("nvidia-smi")
            if nvidia_smi:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                output = subprocess.check_output(
                    [
                        nvidia_smi,
                        "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    creationflags=creationflags,
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                rows = []
                for line in output.strip().splitlines():
                    parts = [part.strip() for part in line.split(",")]
                    if len(parts) < 4:
                        continue
                    gpu_models.append(parts[0])
                    rows.append(
                        {
                            "name": parts[0],
                            "vram_mb": int(float(parts[1])),
                            "vram_used_mb": int(float(parts[2])),
                            "utilization_percent": float(parts[3]),
                        }
                    )
                if rows:
                    info["gpus"] = rows
                    info["gpu_name"] = rows[0]["name"]
                    info["gpu_vram_mb"] = rows[0]["vram_mb"]
                    info["gpu_vram_used_mb"] = rows[0]["vram_used_mb"]
                    info["gpu_percent"] = rows[0]["utilization_percent"]
        except Exception:
            pass

        info["gpu_models"] = gpu_models
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

    def _process_output_line(self, task, line: str) -> None:
        frame = extract_progress_frame(line, task.frame_start, task.frame_end)
        if frame is None or frame == self._last_progress_frame:
            return
        self._last_progress_frame = frame
        percent = frame_progress_percent(frame, task.frame_start, task.frame_end, task.frame_step)
        if self.current_task_ui:
            self.current_task_ui["progress"] = percent
            self.current_task_ui["current_frame"] = frame
        self.task_progress_signal.emit(
            {
                "task_id": task.task_id,
                "frame": frame,
                "percent": percent,
                "status": "RENDERING",
            }
        )

    def run_task(self, raw_task: Dict[str, object]) -> int:
        try:
            task = normalize_task(raw_task)
            adapter = self.adapter_factory.for_task(task)
            plan = adapter.build_plan(task)
        except (AdapterError, ValueError) as error:
            self.log_signal.emit("Task preparation failed: {}".format(error))
            return -2
        except Exception as error:
            self.log_signal.emit("Unexpected task preparation error: {}".format(error))
            return -3

        task_ui = build_task_ui_payload(raw_task, task)
        detail = self.fetch_job_detail(safe_text(task_ui.get("job_id")))
        if detail:
            task_ui = merge_job_detail(task_ui, detail)

        self.current_task_id = task.task_id
        self.current_task_ui = task_ui
        self.cancel_current_requested = False
        self._last_progress_frame = None
        started = time.monotonic()
        task_ui["status"] = "RENDERING"
        task_ui["started_at_monotonic"] = started
        self.task_started_signal.emit(dict(task_ui))

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
        )

        arnold_gpu_failed = False
        scene_info = task.raw.get("scene_info") or task.raw.get("layer", {}).get("scene_info") or {}
        is_arnold = task.renderer.lower() == "arnold" if task.renderer else (scene_info.get("renderer", "").lower() == "arnold")
        
        if result.exit_code == 0 and is_arnold:
            try:
                with open(result.log_path, "r") as log_r:
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
                )
            except Exception as error:
                self.log_signal.emit(f"Task retry preparation failed: {error}")

        duration = max(0.0, time.monotonic() - started)
        cancelled = self.cancel_current_requested
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
                "progress": 100 if result.exit_code == 0 else task_ui.get("progress", 0),
            }
        )
        self.task_finished_signal.emit(finished_payload)
        self.current_task_ui = {}

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
        return result.exit_code

    def report_status(self, task_id: str, exit_status: int) -> None:
        try:
            endpoint = "succeed" if exit_status == 0 else "fail"
            payload: Dict[str, Any] = {"exit_status": int(exit_status)}
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
                    exit_status = self.run_task(task)
                    self.report_status(str(task_id), exit_status)
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
        self.setMinimumSize(720, 690)
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
        self.resize(1120, 760)
        self.setMinimumSize(960, 650)
        self.is_quitting = False
        self.worker_status = "OFFLINE"
        self.scheduler_status = "STOPPED"
        self.backend_connected = False
        self.worker_started_monotonic = 0.0
        self.current_task: Dict[str, Any] = {}
        self.current_task_started = 0.0
        self.last_system_info: Dict[str, Any] = {}
        self.server_worker: Dict[str, Any] = {}
        self.current_log_path = ""

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.settings = QSettings("RenderHive", "WorkerDaemon")
        self.worker_thread: WorkerThread | None = None
        self.discovered = discover_all()

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

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(1000)
        self.ui_timer.timeout.connect(self.update_live_ui)
        self.ui_timer.start()

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
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("HeaderCard")
        header.setStyleSheet("QFrame#HeaderCard { border-radius: 0; border-left: 0; border-right: 0; border-top: 0; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(12)

        if icon_path and os.path.exists(icon_path):
            logo = QLabel()
            logo.setPixmap(QIcon(icon_path).pixmap(34, 34))
            header_layout.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("RENDERHIVE WORKER")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("{}  •  Multi-DCC Render Node".format(HOSTNAME))
        subtitle.setObjectName("MutedLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addSpacing(12)

        self.header_status_chip = StatusChip("OFFLINE")
        self.header_connection_chip = StatusChip("DISCONNECTED")
        header_layout.addWidget(self.header_status_chip)
        header_layout.addWidget(self.header_connection_chip)
        header_layout.addStretch()

        version_label = QLabel("v{}".format(WORKER_VERSION))
        version_label.setObjectName("MutedLabel")
        header_layout.addWidget(version_label)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("SecondaryBtn")
        self.settings_btn.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_btn)
        self.start_btn = QPushButton("Start Worker")
        self.start_btn.clicked.connect(self.start_worker)
        header_layout.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop Worker")
        self.stop_btn.setObjectName("DestructiveBtn")
        self.stop_btn.clicked.connect(self.stop_worker)
        self.stop_btn.setEnabled(False)
        header_layout.addWidget(self.stop_btn)
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(188)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 18, 12, 14)
        side_layout.setSpacing(6)
        section_label = QLabel("WORKER CONSOLE")
        section_label.setObjectName("FieldLabel")
        side_layout.addWidget(section_label)
        side_layout.addSpacing(4)

        self.nav_buttons: List[NavButton] = []
        for index, caption in enumerate(("Overview", "Current Job", "Worker Info", "Logs")):
            button = NavButton(caption)
            button.clicked.connect(lambda checked=False, page=index: self.switch_page(page))
            self.nav_buttons.append(button)
            side_layout.addWidget(button)
        side_layout.addStretch()

        self.sidebar_worker_chip = StatusChip("OFFLINE")
        side_layout.addWidget(self.sidebar_worker_chip)
        self.sidebar_scheduler_label = QLabel("Scheduler: Stopped")
        self.sidebar_scheduler_label.setObjectName("MutedLabel")
        self.sidebar_scheduler_label.setWordWrap(True)
        side_layout.addWidget(self.sidebar_scheduler_label)
        self.sidebar_dcc_label = QLabel(self.short_dcc_summary())
        self.sidebar_dcc_label.setObjectName("MutedLabel")
        self.sidebar_dcc_label.setWordWrap(True)
        side_layout.addWidget(self.sidebar_dcc_label)
        body.addWidget(sidebar)

        self.page_stack = QStackedWidget()
        body.addWidget(self.page_stack, 1)
        self.page_stack.addWidget(self.build_overview_page())
        self.page_stack.addWidget(self.build_job_page())
        self.page_stack.addWidget(self.build_worker_page())
        self.page_stack.addWidget(self.build_logs_page())
        self.switch_page(0)

    def page_container(self, title: str, subtitle: str = ""):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("MutedLabel")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)
        return scroll, layout

    def build_overview_page(self) -> QWidget:
        page, layout = self.page_container(
            "Worker Overview",
            "Live status, active workload, machine utilization, and scheduling controls.",
        )

        cards = QGridLayout()
        cards.setSpacing(10)
        self.status_card = StatCard("Worker Status", "Offline", HOSTNAME)
        self.scheduler_card = StatCard("Scheduler", "Stopped", "Not accepting tasks")
        self.current_job_card = StatCard("Current Job", "Idle", "Waiting for a compatible task")
        completed = int(self.settings.value("completed_tasks", 0) or 0)
        failed = int(self.settings.value("failed_tasks", 0) or 0)
        self.history_card = StatCard("Task History", "{} complete".format(completed), "{} failed".format(failed))
        for index, card in enumerate((self.status_card, self.scheduler_card, self.current_job_card, self.history_card)):
            cards.addWidget(card, 0, index)
            cards.setColumnStretch(index, 1)
        layout.addLayout(cards)

        metrics_card = SectionCard("System Activity", "Live machine metrics are updated while the application is open.")
        metrics = QGridLayout()
        metrics.setSpacing(10)
        self.cpu_meter = ResourceMeter("CPU")
        self.memory_meter = ResourceMeter("Memory")
        self.disk_meter = ResourceMeter("System Disk")
        self.gpu_meter = ResourceMeter("GPU")
        metrics.addWidget(self.cpu_meter, 0, 0)
        metrics.addWidget(self.memory_meter, 0, 1)
        metrics.addWidget(self.disk_meter, 1, 0)
        metrics.addWidget(self.gpu_meter, 1, 1)
        metrics_card.add_layout(metrics)
        layout.addWidget(metrics_card)

        control_card = SectionCard("Scheduling Controls")
        control_row = QHBoxLayout()
        self.pause_dispatch_btn = QPushButton("Pause Dispatch")
        self.pause_dispatch_btn.setObjectName("SecondaryBtn")
        self.pause_dispatch_btn.clicked.connect(self.toggle_dispatch_pause)
        self.pause_dispatch_btn.setEnabled(False)
        self.after_task_btn = QPushButton("Pause After Current Task")
        self.after_task_btn.setObjectName("SecondaryBtn")
        self.after_task_btn.setCheckable(True)
        self.after_task_btn.clicked.connect(self.toggle_pause_after_task)
        self.after_task_btn.setEnabled(False)
        refresh_btn = QPushButton("Refresh Server Data")
        refresh_btn.setObjectName("SecondaryBtn")
        refresh_btn.clicked.connect(self.refresh_server_data)
        control_row.addWidget(self.pause_dispatch_btn)
        control_row.addWidget(self.after_task_btn)
        control_row.addWidget(refresh_btn)
        control_row.addStretch()
        control_card.add_layout(control_row)
        layout.addWidget(control_card)

        dcc_card = SectionCard("Detected DCC Applications")
        self.overview_dcc_table = self.create_dcc_table()
        self.overview_dcc_table.setMinimumHeight(160)
        dcc_card.add_widget(self.overview_dcc_table)
        layout.addWidget(dcc_card)
        layout.addStretch()
        return page

    def build_job_page(self) -> QWidget:
        page, layout = self.page_container(
            "Current Job",
            "Job, task, frame, renderer, and output information for the active or most recently completed task.",
        )
        self.job_state_stack = QStackedWidget()
        self.job_empty = EmptyState(
            "No task has been received",
            "Start the worker and submit a compatible Maya or Houdini job. The task details will appear here automatically.",
        )
        self.job_state_stack.addWidget(self.job_empty)

        active = QWidget()
        active_layout = QVBoxLayout(active)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.setSpacing(12)

        progress_card = SectionCard()
        progress_header = QHBoxLayout()
        self.job_title_label = QLabel("Job")
        self.job_title_label.setObjectName("TitleLabel")
        self.job_status_chip = StatusChip("OFFLINE")
        self.job_elapsed_label = QLabel("Elapsed: 00h 00m 00s")
        self.job_elapsed_label.setObjectName("MutedLabel")
        self.cancel_task_btn = QPushButton("Cancel Current Task")
        self.cancel_task_btn.setObjectName("DestructiveBtn")
        self.cancel_task_btn.clicked.connect(self.cancel_current_task)
        self.cancel_task_btn.setEnabled(False)
        progress_header.addWidget(self.job_title_label)
        progress_header.addWidget(self.job_status_chip)
        progress_header.addStretch()
        progress_header.addWidget(self.job_elapsed_label)
        progress_header.addWidget(self.cancel_task_btn)
        progress_card.add_layout(progress_header)
        self.job_progress = QProgressBar()
        self.job_progress.setRange(0, 100)
        self.job_progress.setValue(0)
        progress_card.add_widget(self.job_progress)
        self.job_progress_detail = QLabel("Waiting")
        self.job_progress_detail.setObjectName("MutedLabel")
        progress_card.add_widget(self.job_progress_detail)
        active_layout.addWidget(progress_card)

        job_card = SectionCard("Job Information")
        self.job_info = InfoGrid(
            [
                ("job_name", "Name"),
                ("job_user", "User"),
                ("department", "Department"),
                ("project", "Project"),
                ("priority", "Priority"),
                ("submit_date", "Submit Date"),
                ("pool", "Pool Routing"),
                ("notes", "Notes"),
            ],
            columns=2,
        )
        job_card.add_widget(self.job_info)
        active_layout.addWidget(job_card)

        task_card = SectionCard("Task & Render Information")
        self.task_info = InfoGrid(
            [
                ("task_id", "Task ID"),
                ("task_name", "Task Name"),
                ("layer_name", "Layer"),
                ("frame_range", "Frames"),
                ("dcc", "DCC"),
                ("dcc_version", "DCC Version"),
                ("renderer", "Renderer"),
                ("execution_mode", "Execution Mode"),
                ("render_node", "Render Node"),
                ("camera", "Camera"),
                ("exit_code", "Exit Code"),
                ("output_image_path", "Last Output Image"),
            ],
            columns=2,
        )
        task_card.add_widget(self.task_info)
        active_layout.addWidget(task_card)

        path_card = SectionCard("Scene & Output Paths")
        self.path_info = InfoGrid(
            [
                ("scene_path", "Scene File"),
                ("project_path", "Project Path"),
                ("output_path", "Output Path"),
                ("log_path", "Task Log"),
            ],
            columns=1,
        )
        path_card.add_widget(self.path_info)
        active_layout.addWidget(path_card)
        active_layout.addStretch()

        self.job_state_stack.addWidget(active)
        layout.addWidget(self.job_state_stack)
        layout.addStretch()
        return page

    def build_worker_page(self) -> QWidget:
        page, layout = self.page_container(
            "Worker Information",
            "Scheduler state, server assignments, task statistics, machine specifications, and installed render software.",
        )

        schedule_card = SectionCard("Worker & Scheduler")
        self.worker_schedule_info = InfoGrid(
            [
                ("worker_status", "Worker Status"),
                ("scheduler_status", "Scheduler Status"),
                ("backend", "Connected to Backend"),
                ("running_time", "Running Time"),
                ("after_task", "After Current Task"),
                ("region", "Region"),
                ("description", "Description"),
                ("comment", "Comment"),
                ("pools", "Assigned Pools"),
                ("groups", "Groups / Worker Tags"),
                ("dequeue_mode", "Dequeuing Mode"),
                ("concurrent_limit", "Concurrent Task Limit"),
                ("completed", "Completed Tasks"),
                ("failed", "Failed Tasks"),
            ],
            columns=2,
        )
        schedule_card.add_widget(self.worker_schedule_info)
        layout.addWidget(schedule_card)

        specs_card = SectionCard("Worker Specifications")
        self.worker_specs_info = InfoGrid(
            [
                ("os", "Operating System"),
                ("user", "Machine User"),
                ("cpu", "CPU"),
                ("cores", "Logical / Physical Cores"),
                ("memory", "Memory Usage"),
                ("ip", "IP Address"),
                ("mac", "MAC Address"),
                ("disk", "Free Disk Space"),
                ("gpu", "Video Card"),
                ("gpu_usage", "GPU Usage"),
                ("worker_version", "Worker Version"),
                ("last_ping", "Last Server Ping"),
            ],
            columns=2,
        )
        specs_card.add_widget(self.worker_specs_info)
        layout.addWidget(specs_card)

        dcc_card = SectionCard("DCC Capabilities")
        self.worker_dcc_table = self.create_dcc_table()
        self.worker_dcc_table.setMinimumHeight(200)
        dcc_card.add_widget(self.worker_dcc_table)
        layout.addWidget(dcc_card)
        layout.addStretch()
        return page

    def build_logs_page(self) -> QWidget:
        page, layout = self.page_container(
            "Worker Logs",
            "Live worker events are shown here. Full DCC output is written to per-task log files.",
        )
        tools = QHBoxLayout()
        self.log_search_input = QLineEdit()
        self.log_search_input.setPlaceholderText("Find in log…")
        self.log_search_input.returnPressed.connect(self.find_in_log)
        clear_btn = QPushButton("Clear View")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.clicked.connect(self.clear_log_view)
        copy_btn = QPushButton("Copy Log")
        copy_btn.setObjectName("SecondaryBtn")
        copy_btn.clicked.connect(self.copy_log_view)
        open_btn = QPushButton("Open Log Folder")
        open_btn.setObjectName("SecondaryBtn")
        open_btn.clicked.connect(self.open_log_folder)
        tools.addWidget(self.log_search_input, 1)
        tools.addWidget(clear_btn)
        tools.addWidget(copy_btn)
        tools.addWidget(open_btn)
        layout.addLayout(tools)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(5000)
        self.log_console.setMinimumHeight(520)
        layout.addWidget(self.log_console, 1)
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
        rows = _installation_rows(self.discovered)
        for table in (self.overview_dcc_table, self.worker_dcc_table):
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    table.setItem(row_index, column_index, item)
        self.sidebar_dcc_label.setText(self.short_dcc_summary())

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
        self.page_stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

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

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.worker_status = str(status or "OFFLINE").upper()
        self.header_status_chip.set_status(self.worker_status)
        self.sidebar_worker_chip.set_status(self.worker_status)
        self.status_card.set_value(self.worker_status.title(), HOSTNAME)
        self.worker_schedule_info.set_value("worker_status", self.worker_status.title())
        if self.worker_status == "RENDERING":
            self.current_job_card.set_value(
                safe_text(self.current_task.get("job_name"), "Rendering"),
                safe_text(self.current_task.get("frame_range"), "Task in progress"),
            )
        elif self.worker_status in ("ONLINE", "PAUSED") and not self.current_task:
            self.current_job_card.set_value("Idle", "Waiting for a compatible task")

    @Slot(str)
    def update_scheduler(self, status: str) -> None:
        self.scheduler_status = str(status or "STOPPED").upper()
        self.sidebar_scheduler_label.setText("Scheduler: {}".format(self.scheduler_status.title()))
        detail = {
            "WAITING": "Accepting compatible tasks",
            "PAUSED": "Dispatch is paused",
            "RUNNING TASK": "Rendering the current task",
            "STOPPED": "Worker is not running",
        }.get(self.scheduler_status, "")
        self.scheduler_card.set_value(self.scheduler_status.title(), detail)
        self.worker_schedule_info.set_value("scheduler_status", self.scheduler_status.title())
        self.pause_dispatch_btn.setText("Resume Dispatch" if self.scheduler_status == "PAUSED" else "Pause Dispatch")

    @Slot(bool)
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
        self.job_state_stack.setCurrentIndex(1)
        self.job_title_label.setText(safe_text(self.current_task.get("job_name"), "Current Job"))
        self.job_status_chip.set_status("RENDERING")
        self.job_progress.setRange(0, 0)
        self.job_progress_detail.setText(
            "Frames {}  •  {} {}  •  {}".format(
                safe_text(self.current_task.get("frame_range"), "—"),
                safe_text(self.current_task.get("dcc"), "DCC"),
                safe_text(self.current_task.get("dcc_version")),
                safe_text(self.current_task.get("renderer"), "Renderer not specified"),
            )
        )
        self.cancel_task_btn.setEnabled(True)
        self.job_info.set_values(self.current_task)
        self.task_info.set_values(self.current_task)
        self.path_info.set_values(self.current_task)
        self.current_job_card.set_value(
            safe_text(self.current_task.get("job_name"), "Rendering"),
            safe_text(self.current_task.get("frame_range"), "Task in progress"),
        )

    @Slot(object)
    def on_task_progress(self, payload: object) -> None:
        data = safe_dict(payload)
        percent = max(0, min(100, int(data.get("percent") or 0)))
        self.job_progress.setRange(0, 100)
        self.job_progress.setValue(percent)
        frame = data.get("frame")
        self.job_progress_detail.setText("Rendering frame {}  •  {}%".format(frame, percent))

    @Slot(object)
    def on_task_finished(self, payload: object) -> None:
        data = safe_dict(payload)
        self.current_task = data
        self.current_task_started = 0.0
        status = safe_text(data.get("status"), "FAILED").upper()
        self.job_status_chip.set_status("ONLINE" if status == "SUCCEEDED" else "ERROR")
        self.job_progress.setRange(0, 100)
        self.job_progress.setValue(100 if status == "SUCCEEDED" else self.job_progress.value())
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
        self.current_job_card.set_value(
            safe_text(data.get("job_name"), "Last Task"),
            "{} in {}".format(status.title(), format_duration(data.get("duration_seconds"))),
        )

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
            gpu_detail = "{}  •  {} / {} VRAM".format(
                gpu_name,
                format_bytes(int(info.get("gpu_vram_used_mb") or 0) * 1024 * 1024),
                format_bytes(int(info.get("gpu_vram_mb") or 0) * 1024 * 1024),
            )
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
                "gpu_usage": "{}%".format(int(round(gpu_percent))) if info.get("gpu_name") else "—",
                "worker_version": safe_text(info.get("worker_version"), WORKER_VERSION),
            }
        )

    def refresh_local_snapshot(self) -> None:
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(_disk_root())
            snapshot = dict(self.last_system_info)
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
        self.worker_thread.capabilities_signal.connect(lambda text: self.sidebar_dcc_label.setToolTip(text))
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
