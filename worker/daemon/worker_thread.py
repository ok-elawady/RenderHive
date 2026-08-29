"""RenderHive worker background thread scheduler and process controller."""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psutil
import requests
from PySide6.QtCore import QThread, Signal

from adapters import AdapterFactory
from adapters.base import AdapterError
from core.dcc_discovery import (
    DCCInstallation,
    build_capabilities,
    build_capability_tags,
)
from core.gpu_info import GPUDetector
from core.process_runner import run_process
from core.progress import TaskProgressTracker
from core.task_normalizer import normalize_task
from core.ui_helpers import (
    build_task_ui_payload,
    collect_disk_metrics,
    get_cpu_name,
    local_ip_address,
    mac_address,
    machine_user,
    merge_job_detail,
    safe_text,
    split_csv,
)
from daemon.api_client import RenderHiveApiClient
from version import WORKER_VERSION

HOSTNAME = socket.gethostname()


def _disk_root() -> str:
    if os.name == "nt":
        return (os.environ.get("SystemDrive") or "C:") + "\\"
    return "/"


def format_installations_summary(discovered: Dict[str, Sequence[DCCInstallation]]) -> str:
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
        profile: Optional[Dict[str, Any]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.discovered = discovered
        self.profile = dict(profile or {})
        self.client = RenderHiveApiClient(self.api_url, self.api_token)
        self.adapter_factory = AdapterFactory(discovered)
        self.is_running = True
        self.dispatch_paused = bool(self.profile.get("start_paused", False))
        self.pause_after_current = str(self.profile.get("after_task", "continue")).lower() == "pause"
        self.cancel_current_requested = False
        self.force_profile_refresh = False
        self.current_task_id = ""
        self.current_task_ui: Dict[str, Any] = {}
        self._last_system_info: Dict[str, Any] = {}
        self.started_monotonic = time.monotonic()
        self.last_worker_profile_fetch = 0.0
        self.poll_interval = max(2, min(30, int(self.profile.get("poll_interval", 5) or 5)))
        self._last_progress_frame = None
        self._progress_tracker: TaskProgressTracker | None = None
        self._last_progress_signature = None
        self._last_progress_emit = 0.0
        self.gpu_detector = GPUDetector()

    def update_config(
        self,
        api_url: str,
        api_token: str,
        profile: Optional[Dict[str, Any]] = None,
        discovered: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Dynamically update connection credentials, profile, and DCC adapters while running."""
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        if profile is not None:
            self.profile = dict(profile)
            self.poll_interval = max(2, min(30, int(self.profile.get("poll_interval", 5) or 5)))
            self.pause_after_current = str(self.profile.get("after_task", "continue")).lower() == "pause"
        if discovered is not None:
            self.discovered = discovered
            self.adapter_factory = AdapterFactory(discovered)
        self.client = RenderHiveApiClient(self.api_url, self.api_token)
        self.force_profile_refresh = True

    def get_headers(self) -> Dict[str, str]:
        return self.client.get_headers()

    def collect_system_info(self) -> Dict[str, object]:
        virtual_memory = psutil.virtual_memory()
        disk_data = collect_disk_metrics()
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
            "disk_total_bytes": disk_data.get("disk_total_bytes", 0),
            "disk_used_bytes": disk_data.get("disk_used_bytes", 0),
            "disk_free_bytes": disk_data.get("disk_free_bytes", 0),
            "disk_percent": disk_data.get("disk_percent", 0.0),
            "disk_drives": disk_data.get("disk_drives", []),
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
            "cpu_name": get_cpu_name(),
        }

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
        # Store live snapshot for dispatch scheduling payload
        self._last_system_info = dict(info)
        return info

    def heartbeat_payload(self) -> Dict[str, object]:
        system_info = self.collect_system_info()
        tags = build_capability_tags(self.discovered)
        tags.extend(split_csv(self.profile.get("custom_tags")))
        tags = list(dict.fromkeys(tags))
        payload: Dict[str, object] = {
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
        # Synchronize explicit custom pool assignments if configured in the local profile
        local_pools = split_csv(self.profile.get("pool_names") or self.profile.get("custom_pools") or self.profile.get("pools"))
        if local_pools:
            payload["pool_names"] = local_pools
        return payload

    def send_heartbeat(self) -> bool:
        payload = self.heartbeat_payload()
        self.system_info_signal.emit(payload.get("system_info") or {})
        try:
            response = self.client.ping(payload, timeout=8.0)
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
            record = self.client.fetch_worker_record(HOSTNAME)
            if record:
                self.server_worker_signal.emit(record)
        except Exception:
            pass

    def fetch_job_detail(self, job_id: str) -> Dict[str, Any]:
        return self.client.fetch_job_detail(job_id)

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

    def run_task(self, raw_task: Dict[str, object]) -> Tuple[int, str, str, float, str, int]:
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
            return -2, "", str(error), 0.0, "", 0
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
            return -3, "", str(error), 0.0, "", 0

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

        # Auto-fallback to CPU rendering if Arnold GPU or OptiX initialization failed (regardless of exit code)
        if is_arnold:
            try:
                if result.log_path and os.path.isfile(result.log_path):
                    with open(result.log_path, "r", encoding="utf-8", errors="replace") as log_r:
                        log_contents = log_r.read()
                    gpu_failure_patterns = [
                        "Unable to load Optix library",
                        "GPU rendering is not available",
                        "Failed to initialize GPU",
                        "OptiX error",
                        "CUDA error",
                    ]
                    if any(p.lower() in log_contents.lower() for p in gpu_failure_patterns) and not result.output_image_path:
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
                "peak_memory_mb": result.peak_memory_mb,
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
        return (
            result.exit_code,
            display_log,
            result.error_tail,
            duration,
            result.output_image_path,
            result.peak_memory_mb,
            result.peak_cpu_percent,
            result.output_file_size_bytes,
        )

    def report_status(
        self,
        task_id: str,
        exit_status: int,
        log_path: str = "",
        error_tail: str = "",
        duration_seconds: float = 0.0,
        output_image_path: str = "",
        max_memory_used_mb: int = 0,
        peak_cpu_percent: float = 0.0,
        file_size_bytes: int = 0,
    ) -> None:
        try:
            response = self.client.report_task_status(
                task_id=task_id,
                exit_status=exit_status,
                log_path=log_path,
                error_tail=error_tail,
                duration_seconds=duration_seconds,
                output_image_path=output_image_path,
                worker_hostname=HOSTNAME,
                max_memory_used_mb=max_memory_used_mb,
                peak_cpu_percent=peak_cpu_percent,
                file_size_bytes=file_size_bytes,
            )
            if not (200 <= response.status_code < 300):
                self.log_signal.emit("Failed to report task status: HTTP {}".format(response.status_code))
        except Exception as error:
            self.log_signal.emit("Error reporting task status: {}".format(error))

    def run(self) -> None:
        self.log_signal.emit("Starting RenderHive Worker {} on {}...".format(WORKER_VERSION, HOSTNAME))
        summary = format_installations_summary(self.discovered)
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
                # Send live system telemetry snapshot to assist backend AI scheduler
                response = self.client.dispatch(
                    worker_name=HOSTNAME,
                    tags=build_capability_tags(self.discovered),
                    capabilities=build_capabilities(self.discovered),
                    capabilities_snapshot=self._last_system_info,
                )
                self.connection_signal.emit(True)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "").lower()
                    raw_text = (response.text or "").strip()
                    if "text/html" in content_type or raw_text.startswith("<!DOCTYPE") or raw_text.startswith("<html"):
                        self.log_signal.emit(
                            "Dispatch error: Server at {} returned HTML instead of a JSON API response. "
                            "Please check your API URL in Settings.".format(self.api_url)
                        )
                        time.sleep(float(self.poll_interval))
                        continue

                    if not raw_text:
                        time.sleep(float(self.poll_interval))
                        continue

                    try:
                        task = response.json()
                    except Exception as json_err:
                        self.log_signal.emit(
                            "Dispatch error: Invalid JSON response ({}) from {}".format(json_err, self.api_url)
                        )
                        time.sleep(float(self.poll_interval))
                        continue

                    if not isinstance(task, dict) or not (task.get("id") or task.get("task_id")):
                        time.sleep(float(self.poll_interval))
                        continue

                    task_id = task.get("id", task.get("task_id", "unknown"))
                    self.status_signal.emit("RENDERING")
                    self.scheduler_signal.emit("RUNNING TASK")
                    (
                        exit_status,
                        log_path,
                        error_tail,
                        duration,
                        out_img,
                        peak_mem,
                        peak_cpu,
                        file_size,
                    ) = self.run_task(task)
                    self.report_status(
                        str(task_id),
                        exit_status,
                        log_path=log_path,
                        error_tail=error_tail,
                        duration_seconds=duration,
                        output_image_path=out_img,
                        max_memory_used_mb=peak_mem,
                        peak_cpu_percent=peak_cpu,
                        file_size_bytes=file_size,
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
