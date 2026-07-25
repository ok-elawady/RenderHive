from __future__ import print_function

import compileall
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    result = {"syntax": False, "tests": False, "required_files": False}
    result["syntax"] = bool(compileall.compile_dir(ROOT, quiet=1, force=True))
    required = [
        "renderhive_maya_submitter.py",
        os.path.join("api", "client.py"),
        os.path.join("core", "diagnostics.py"),
        os.path.join("ui", "qt_submitter_window.py"),
    ]
    result["required_files"] = all(os.path.isfile(os.path.join(ROOT, item)) for item in required)
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
