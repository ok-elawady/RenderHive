from __future__ import print_function

import compileall
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    result = {
        "syntax": False,
        "tests": False,
        "required_files": False,
        "source_hygiene": False,
    }
    result["syntax"] = bool(compileall.compile_dir(ROOT, quiet=1, force=True))
    required = [
        "renderhive_maya_submitter.py",
        os.path.join("api", "client.py"),
        os.path.join("core", "diagnostics.py"),
        os.path.join("ui", "qt_submitter_window.py"),
        os.path.join("ui", "common_widgets.py"),
        os.path.join("ui", "targeting_widgets.py"),
        os.path.join("ui", "icons", "check_mark.png"),
        os.path.join("ui", "worker_data.py"),
        os.path.join("ui", "runtime_registry.py"),
        os.path.join("ui", "controllers", "__init__.py"),
        os.path.join("ui", "controllers", "api_controller.py"),
        os.path.join("ui", "controllers", "targeting_controller.py"),
        os.path.join("ui", "controllers", "dependency_controller.py"),
        os.path.join("ui", "job_dependency_widgets.py"),
        os.path.join("submission", "__init__.py"),
        os.path.join("submission", "task_builder.py"),
        os.path.join("submission", "task_validation.py"),
        os.path.join("ui", "pages", "job_page.py"),
        os.path.join("ui", "pages", "render_page.py"),
        os.path.join("ui", "pages", "validation_page.py"),
        os.path.join("ui", "pages", "tools_page.py"),
        os.path.join("validation", "validator.py"),
        os.path.join("validation", "submission_checks.py"),
    ]
    result["required_files"] = all(os.path.isfile(os.path.join(ROOT, item)) for item in required)

    runtime_sources = [
        os.path.join(ROOT, "ui", "qt_submitter_window.py"),
        os.path.join(ROOT, "ui", "targeting_widgets.py"),
        os.path.join(ROOT, "api", "maya_bridge.py"),
        os.path.join(ROOT, "validation", "scene_checks.py"),
    ]
    source_chunks = []
    for path in runtime_sources:
        with open(path, "r", encoding="utf-8") as handle:
            source_chunks.append(handle.read())
    source_text = "\n".join(source_chunks)
    banned = (
        "_renderhive_legacy_validate_task",
        "def validate_submission_task",
        "class WorkerSelectionDialog",
        "class WorkerMultiSelect",
        "class ApiWorkerPoolManagerDialog",
        "def get_api_layer_frames",
        "def get_api_layer_frame",
    )
    result["source_hygiene"] = not any(token in source_text for token in banned)

    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", os.path.join(ROOT, "tests"), "-v"],
        cwd=ROOT,
    )
    result["tests"] = completed.returncode == 0
    result["ok"] = all(result.values())
    print(json.dumps(result, indent=4))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
