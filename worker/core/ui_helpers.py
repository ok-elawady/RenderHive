"""Pure helper functions used by the RenderHive Worker UI."""

from __future__ import annotations

import getpass
import os
import re
import socket
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


_FRAME_PATTERNS = [
    re.compile(r"\b(?:rendering\s+)?frame\s*[:#=]?\s*(-?\d+)\b", re.IGNORECASE),
    re.compile(r"\bframe\s+(-?\d+)\s+(?:completed|done|finished)\b", re.IGNORECASE),
    re.compile(r"\b(?:image|sample)\s+at\s+frame\s+(-?\d+)\b", re.IGNORECASE),
]


def format_bytes(value: Any) -> str:
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0.0
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while abs(amount) >= 1024.0 and index < len(units) - 1:
        amount /= 1024.0
        index += 1
    if index == 0:
        return "{} {}".format(int(round(amount)), units[index])
    return "{:.1f} {}".format(amount, units[index])


def format_duration(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds or 0)))
    except Exception:
        total = 0
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return "{}d {:02d}h {:02d}m".format(days, hours, minutes)
    return "{:02d}h {:02d}m {:02d}s".format(hours, minutes, secs)


def split_csv(value: Any) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        raw_items: Iterable[Any] = value
    else:
        raw_items = str(value or "").replace(";", ",").split(",")
    result: List[str] = []
    seen = set()
    for item in raw_items:
        text = str(item or "").strip()
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def local_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""


def mac_address() -> str:
    value = uuid.getnode()
    return ":".join("{:02X}".format((value >> shift) & 0xFF) for shift in range(40, -1, -8))


def machine_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or ""


def safe_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_task_ui_payload(raw_task: Dict[str, Any], normalized: Any) -> Dict[str, Any]:
    raw = safe_dict(raw_task)
    job = safe_dict(raw.get("job"))
    layer = safe_dict(raw.get("layer"))
    scene_info = safe_dict(raw.get("scene_info"))
    if not scene_info:
        scene_info = safe_dict(layer.get("scene_info"))

    visible_name = safe_text(job.get("visible_name"), job.get("name"), raw.get("job_name"), raw.get("name"))
    task_name = safe_text(raw.get("name"), raw.get("task_name"), getattr(normalized, "task_id", ""))
    frame_start = int(getattr(normalized, "frame_start", 1))
    frame_end = int(getattr(normalized, "frame_end", frame_start))
    frame_step = max(1, int(getattr(normalized, "frame_step", 1)))
    total_frames = max(1, ((frame_end - frame_start) // frame_step) + 1) if frame_end >= frame_start else 1

    return {
        "job_id": safe_text(job.get("id"), raw.get("job_id")),
        "job_name": visible_name or "Unnamed Job",
        "job_user": safe_text(job.get("user"), raw.get("user")),
        "department": safe_text(job.get("department"), raw.get("department")),
        "project": safe_text(job.get("project"), raw.get("project")),
        "priority": safe_text(job.get("priority"), raw.get("priority")),
        "submit_date": safe_text(job.get("created_at"), job.get("submit_date"), raw.get("submit_date")),
        "notes": safe_text(job.get("notes"), scene_info.get("notes")),
        "pool": safe_text(job.get("pool"), job.get("included_pools"), raw.get("pool")),
        "group": safe_text(job.get("group"), raw.get("group")),
        "task_id": safe_text(getattr(normalized, "task_id", ""), raw.get("id")),
        "task_name": task_name or "Task",
        "layer_name": safe_text(layer.get("name"), raw.get("layer_name")),
        "dcc": safe_text(getattr(normalized, "dcc", "")).title(),
        "dcc_version": safe_text(getattr(normalized, "dcc_version", "")),
        "renderer": safe_text(getattr(normalized, "renderer", "")),
        "execution_mode": safe_text(getattr(normalized, "execution_mode", "")).upper(),
        "scene_path": safe_text(getattr(normalized, "scene_path", "")),
        "project_path": safe_text(getattr(normalized, "project_path", "")),
        "output_path": safe_text(getattr(normalized, "output_path", "")),
        "render_node": safe_text(getattr(normalized, "render_node", "")),
        "camera": safe_text(getattr(normalized, "camera", "")),
        "command": safe_text(getattr(normalized, "command", "")),
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_step": frame_step,
        "frame_range": "{}-{} x{}".format(frame_start, frame_end, frame_step),
        "total_frames": total_frames,
        "status": "STARTING",
        "progress": 0,
    }


def merge_job_detail(payload: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(payload or {})
    source = safe_dict(detail)
    mapping = {
        "job_name": safe_text(source.get("visible_name"), source.get("name")),
        "job_user": safe_text(source.get("user")),
        "department": safe_text(source.get("department")),
        "project": safe_text(source.get("project")),
        "priority": safe_text(source.get("priority")),
        "submit_date": safe_text(source.get("created_at")),
        "notes": safe_text(source.get("notes")),
    }
    included = source.get("included_pools")
    excluded = source.get("excluded_pools")
    if included:
        mapping["pool"] = _join_named_items(included)
    elif excluded:
        mapping["pool"] = "All except: {}".format(_join_named_items(excluded))
    for key, value in mapping.items():
        if value:
            result[key] = value
    return result


def _join_named_items(items: Any) -> str:
    if not isinstance(items, list):
        return safe_text(items)
    names = []
    for item in items:
        if isinstance(item, dict):
            text = safe_text(item.get("name"), item.get("id"))
        else:
            text = safe_text(item)
        if text:
            names.append(text)
    return ", ".join(names)


def extract_progress_frame(line: Any, frame_start: int, frame_end: int) -> Optional[int]:
    text = str(line or "")
    low = min(int(frame_start), int(frame_end))
    high = max(int(frame_start), int(frame_end))
    for pattern in _FRAME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            frame = int(match.group(1))
        except Exception:
            continue
        if low <= frame <= high:
            return frame
    return None


def frame_progress_percent(frame: int, frame_start: int, frame_end: int, frame_step: int = 1) -> int:
    start = int(frame_start)
    end = int(frame_end)
    step = max(1, int(frame_step))
    if end <= start:
        return 100
    total = max(1, ((end - start) // step) + 1)
    completed = max(1, min(total, ((int(frame) - start) // step) + 1))
    return max(0, min(100, int(round((completed / float(total)) * 100.0))))


def select_worker_record(response_data: Any, hostname: str) -> Dict[str, Any]:
    if isinstance(response_data, dict):
        items = response_data.get("results")
        if not isinstance(items, list):
            if safe_text(response_data.get("hostname")).lower() == str(hostname or "").lower():
                return response_data
            items = []
    elif isinstance(response_data, list):
        items = response_data
    else:
        items = []

    target = str(hostname or "").strip().lower()
    for item in items:
        if isinstance(item, dict) and safe_text(item.get("hostname")).lower() == target:
            return item
    return {}


def pool_names_from_worker(worker: Dict[str, Any]) -> List[str]:
    pools = worker.get("pools") if isinstance(worker, dict) else []
    if not isinstance(pools, list):
        return []
    result = []
    for pool in pools:
        if isinstance(pool, dict):
            name = safe_text(pool.get("name"), pool.get("id"))
        else:
            name = safe_text(pool)
        if name:
            result.append(name)
    return result


def format_timestamp(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return "—"
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return text


def get_cpu_name() -> str:
    """Return the human-readable CPU brand/marketing model name."""
    if os.name == "nt":
        try:
            import winreg  # type: ignore

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            cleaned = " ".join(str(val or "").strip().split())
            if cleaned:
                return cleaned
        except Exception:
            pass
    elif os.name == "posix":
        try:
            if os.path.isfile("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if "model name" in line:
                            return line.split(":", 1)[1].strip()
        except Exception:
            pass
        try:
            import subprocess
            output = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if output:
                return output
        except Exception:
            pass

    import platform
    return platform.processor() or platform.machine() or "Generic CPU"


def collect_disk_metrics() -> Dict[str, Any]:
    """Collect aggregated disk metrics across all mounted local drives, plus per-drive details."""
    import psutil

    total = 0
    used = 0
    free = 0
    drives: List[Dict[str, Any]] = []
    seen = set()

    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        partitions = []

    for p in partitions:
        if os.name == "nt" and ("cdrom" in p.opts or not p.fstype):
            continue
        mount = p.mountpoint
        if mount in seen:
            continue
        try:
            usage = psutil.disk_usage(mount)
            if usage.total == 0:
                continue
            seen.add(mount)
            total += usage.total
            used += usage.used
            free += usage.free
            drives.append({
                "mount": mount,
                "device": p.device or mount,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except Exception:
            continue

    if not seen:
        try:
            root_path = (os.environ.get("SystemDrive") or "C:") + "\\" if os.name == "nt" else "/"
            usage = psutil.disk_usage(root_path)
            total = usage.total
            used = usage.used
            free = usage.free
            drives.append({
                "mount": root_path,
                "device": root_path,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except Exception:
            pass

    percent = round((used / total * 100), 1) if total > 0 else 0.0

    return {
        "disk_total_bytes": total,
        "disk_used_bytes": used,
        "disk_free_bytes": free,
        "disk_percent": percent,
        "disk_drives": drives,
    }
