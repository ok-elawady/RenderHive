"""Resolve files in source and PyInstaller builds."""

from __future__ import annotations

import os
import sys


def application_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled_root() -> str:
    return str(getattr(sys, "_MEIPASS", application_root()))


def bundled_path(*parts: str) -> str:
    return os.path.join(bundled_root(), *parts)


def writable_log_root() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(local_app_data, "RenderHive", "Worker", "logs")
    os.makedirs(path, exist_ok=True)
    return path
