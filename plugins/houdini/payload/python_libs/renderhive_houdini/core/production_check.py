"""Local production-readiness checks for the running Houdini integration."""

from __future__ import absolute_import

import os

from renderhive_houdini.core.paths import runtime_logs_dir, state_database_path
from renderhive_houdini.ui.qt_compat import binding_name
from renderhive_houdini.version import __version__


def run_check(context=None, api_config=None, state_store=None):
    checks = []
    def add(name, ok, details=""):
        checks.append({"name": name, "passed": bool(ok), "details": str(details or "")})

    add("Plugin version", bool(__version__), __version__)
    add("Qt binding", binding_name() in ("PySide2", "PySide6"), binding_name())
    add("Runtime log directory", os.path.isdir(runtime_logs_dir()), runtime_logs_dir())
    add("State database", state_store.integrity_ok() if state_store else os.path.isfile(state_database_path()), state_database_path())
    add("HIP file saved", bool(context and context.hip_path and not context.is_new_file), getattr(context, "hip_path", ""))
    add("Project path", bool(context and context.project_path), getattr(context, "project_path", ""))
    add("Backend configuration", bool(api_config and api_config.get("base_url")), (api_config or {}).get("_config_source", ""))
    add("Authentication token", bool(api_config and (api_config.get("auth") or {}).get("token")), "Configured" if api_config and (api_config.get("auth") or {}).get("token") else "Missing")
    return {
        "passed": all(item["passed"] for item in checks),
        "passed_count": len([item for item in checks if item["passed"]]),
        "failed_count": len([item for item in checks if not item["passed"]]),
        "checks": checks,
    }
