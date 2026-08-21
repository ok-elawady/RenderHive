from __future__ import print_function

import ast
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_ROOT = os.path.join(ROOT, "payload", "python_libs")


def _python_sources():
    paths = []
    for base, _, files in os.walk(ROOT):
        for name in files:
            if name.endswith(".py"):
                paths.append(os.path.join(base, name))
    return sorted(paths)


def _syntax_ok(paths):
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            ast.parse(handle.read(), filename=path)
    return True


def _package_hygiene_ok():
    for base, dirs, files in os.walk(ROOT):
        if "__pycache__" in dirs or ".pytest_cache" in dirs:
            return False
        if any(name.endswith((".pyc", ".pyo")) for name in files):
            return False
    return True


def main():
    result = {
        "syntax": False,
        "tests": False,
        "required_files": False,
        "source_hygiene": False,
        "package_hygiene": False,
    }
    sources = _python_sources()
    result["syntax"] = _syntax_ok(sources)

    required = [
        os.path.join("contracts", "renderhive_api_0_2_0.yaml"),
        os.path.join("package", "renderhive.json.template"),
        os.path.join("payload", "MainMenuCommon.xml"),
        os.path.join("payload", "toolbar", "RenderHive.shelf"),
        os.path.join("payload", "config", "Icons", "renderhive.svg"),
        os.path.join("payload", "config", "Icons", "renderhive.png"),
        os.path.join("payload", "icons", "renderhive_shelf_icon.png"),
        os.path.join("payload", "python_panels", "renderhive.pypanel"),
        os.path.join("payload", "icons", "renderhive_header_logo.png"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "api", "client.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "api", "contract.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "core", "task_builder.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "main_window.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "job_dependency_widgets.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "icons", "check_mark.png"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "pages", "job_page.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "pages", "render_page.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "pages", "validation_page.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "ui", "pages", "tools_page.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "worker", "render_rop.py"),
        os.path.join("payload", "python_libs", "renderhive_houdini", "worker", "render_husk.py"),
    ]
    result["required_files"] = all(os.path.isfile(os.path.join(ROOT, item)) for item in required)

    runtime_root = os.path.join(ROOT, "payload", "python_libs", "renderhive_houdini")
    runtime_sources = [path for path in sources if path.startswith(runtime_root + os.sep)]
    source_text = "\n".join(open(path, "r", encoding="utf-8").read() for path in runtime_sources)
    ui_sources = [path for path in runtime_sources if os.path.join("ui", "") in path]
    ui_text = "\n".join(open(path, "r", encoding="utf-8").read() for path in ui_sources)
    removed_ui_controls = ("Start Suspended", "Machine Limit", "Allowed Workers", "Denied Workers")
    dead_api_aliases = ("def list_layer_frames", "def get_layer_frame")
    result["source_hygiene"] = (
        not any(token in ui_text for token in removed_ui_controls)
        and not any(token in source_text for token in dead_api_aliases)
    )
    result["package_hygiene"] = _package_hygiene_ok()

    env = dict(os.environ)
    env["PYTHONPATH"] = LIB_ROOT
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
    )
    result["tests"] = completed.returncode == 0
    result["ok"] = all(result.values())
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
