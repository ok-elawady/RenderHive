"""Cross-vendor GPU discovery and telemetry for RenderHive Worker.

The worker prefers NVIDIA's CLI for live telemetry, then falls back to a
lightweight Windows display-controller query so the UI still reports AMD,
Intel, and NVIDIA adapters even when ``nvidia-smi`` is not on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


_IGNORED_ADAPTER_NAMES = (
    "microsoft basic display",
    "microsoft basic render",
    "remote display adapter",
    "virtual display",
    "parsec virtual",
    "indirect display",
)


def _unique_existing(paths: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in paths:
        if not raw:
            continue
        normalized = os.path.normcase(os.path.abspath(os.path.expandvars(raw)))
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(normalized):
            result.append(normalized)
    return result


def nvidia_smi_candidates(environ: Mapping[str, str] | None = None) -> List[str]:
    """Return existing ``nvidia-smi`` candidates in priority order."""

    env = dict(os.environ if environ is None else environ)
    candidates: List[str] = []

    discovered = shutil.which("nvidia-smi")
    if discovered:
        candidates.append(discovered)

    for key in ("SystemRoot", "WINDIR"):
        root = env.get(key)
        if root:
            candidates.append(os.path.join(root, "System32", "nvidia-smi.exe"))

    for key in ("ProgramW6432", "ProgramFiles"):
        root = env.get(key)
        if root:
            candidates.append(
                os.path.join(root, "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
            )

    nv_smi_dir = env.get("NVSMI_DIR")
    if nv_smi_dir:
        candidates.append(os.path.join(nv_smi_dir, "nvidia-smi.exe"))

    return _unique_existing(candidates)


def parse_nvidia_smi_csv(text: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in str(text or "").strip().splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4 or not parts[0]:
            continue
        try:
            total = max(0, int(float(parts[1])))
            used = max(0, int(float(parts[2])))
            utilization = max(0.0, min(100.0, float(parts[3])))
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "name": parts[0],
                "vram_mb": total,
                "vram_used_mb": min(used, total) if total else used,
                "utilization_percent": utilization,
                "telemetry_available": True,
            }
        )
    return rows


def _powershell_executable() -> str:
    return shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh") or ""


def _normalize_cim_payload(payload: object) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        items: Sequence[object] = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        return []

    rows: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or item.get("name") or "").strip()
        if not name:
            continue
        lowered = name.lower()
        if any(token in lowered for token in _IGNORED_ADAPTER_NAMES):
            continue
        key = lowered
        if key in seen:
            continue
        seen.add(key)

        # Win32_VideoController.AdapterRAM is not reliable above 4 GB on every
        # driver, so expose it only as a best-effort value.
        raw_ram = item.get("AdapterRAM", item.get("adapter_ram"))
        try:
            vram_mb = max(0, int(raw_ram or 0) // (1024 * 1024))
        except (TypeError, ValueError):
            vram_mb = 0

        rows.append(
            {
                "name": name,
                "vram_mb": vram_mb,
                "vram_used_mb": 0,
                "utilization_percent": None,
                "telemetry_available": False,
            }
        )
    return rows


def query_windows_video_controllers(timeout: float = 5.0) -> List[Dict[str, Any]]:
    """Query installed display adapters without requiring third-party modules."""

    if os.name != "nt":
        return []
    powershell = _powershell_executable()
    if not powershell:
        return []

    script = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        output = subprocess.check_output(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            creationflags=creationflags,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return _normalize_cim_payload(json.loads(output.strip() or "[]"))
    except Exception:
        return []


def summarize_gpu_rows(rows: Sequence[Mapping[str, Any]], source: str) -> Dict[str, Any]:
    normalized = [dict(row) for row in rows if row.get("name")]
    if not normalized:
        return {
            "gpus": [],
            "gpu_models": [],
            "gpu_detection_source": "none",
            "gpu_telemetry_available": False,
        }

    first = normalized[0]
    return {
        "gpus": normalized,
        "gpu_models": [str(row.get("name")) for row in normalized],
        "gpu_name": str(first.get("name") or ""),
        "gpu_vram_mb": int(first.get("vram_mb") or 0),
        "gpu_vram_used_mb": int(first.get("vram_used_mb") or 0),
        "gpu_percent": first.get("utilization_percent"),
        "gpu_detection_source": source,
        "gpu_telemetry_available": bool(first.get("telemetry_available")),
    }


class GPUDetector:
    """Cached GPU detector suitable for frequent worker heartbeats."""

    def __init__(self, static_refresh_seconds: float = 300.0):
        self.static_refresh_seconds = max(30.0, float(static_refresh_seconds))
        candidates = nvidia_smi_candidates()
        self.nvidia_smi = candidates[0] if candidates else ""
        self._static_rows: List[Dict[str, Any]] = []
        self._last_static_query = 0.0
        self._last_known_summary: Dict[str, Any] = {}

    def _query_nvidia(self) -> List[Dict[str, Any]]:
        if not self.nvidia_smi or not os.path.isfile(self.nvidia_smi):
            return []
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            output = subprocess.check_output(
                [
                    self.nvidia_smi,
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                creationflags=creationflags,
                text=True,
                encoding="utf-8",
                errors="replace",
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return parse_nvidia_smi_csv(output)
        except Exception:
            return []

    def query(self) -> Dict[str, Any]:
        nvidia_rows = self._query_nvidia()
        if nvidia_rows:
            summary = summarize_gpu_rows(nvidia_rows, "nvidia-smi")
            self._last_known_summary = dict(summary)
            return summary

        now = time.monotonic()
        if not self._static_rows or now - self._last_static_query >= self.static_refresh_seconds:
            self._static_rows = query_windows_video_controllers()
            self._last_static_query = now

        if self._static_rows:
            summary = summarize_gpu_rows(self._static_rows, "windows-cim")
            self._last_known_summary = dict(summary)
            return summary

        if self._last_known_summary:
            return dict(self._last_known_summary)

        return summarize_gpu_rows([], "none")
