"""Install RenderHive Houdini using the known-good Houdini package layout."""
from __future__ import print_function

import argparse
import json
import os
import re
import shutil
from pathlib import Path

SUPPORTED = {"19.5", "20.0", "20.5", "21.0"}


def version_from_source(root):
    text = (root / "payload" / "python_libs" / "renderhive_houdini" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise RuntimeError("Could not read plugin version.")
    return match.group(1)


def detect_pref_dirs(explicit):
    if explicit:
        return [Path(item).expanduser().resolve() for item in explicit]
    documents = Path.home() / "Documents"
    found = []
    if documents.is_dir():
        for item in sorted(documents.glob("houdini*.*")):
            if not item.is_dir():
                continue
            match = re.fullmatch(r"houdini(\d+\.\d+)", item.name, flags=re.IGNORECASE)
            if match and match.group(1) in SUPPORTED:
                found.append(item)
    return found


def assert_source(source):
    required = [
        source / "payload" / "MainMenuCommon.xml",
        source / "payload" / "toolbar" / "RenderHive.shelf",
        source / "payload" / "config" / "Icons" / "renderhive.svg",
        source / "payload" / "config" / "Icons" / "renderhive.png",
        source / "payload" / "python_panels" / "renderhive.pypanel",
        source / "payload" / "python_libs" / "renderhive_houdini" / "version.py",
        source / "package" / "renderhive.json.template",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("RenderHive package is incomplete:\n" + "\n".join(missing))


def install(source, pref_dirs):
    version = version_from_source(source)
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    runtime_parent = local / "RenderHive" / "Houdini"
    runtime = runtime_parent / version
    runtime_parent.mkdir(parents=True, exist_ok=True)

    if runtime.exists():
        shutil.rmtree(str(runtime))
    shutil.copytree(str(source / "payload"), str(runtime), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))

    # Runtime proof: shelf definition and icon resolver path must exist together.
    runtime_required = [
        runtime / "toolbar" / "RenderHive.shelf",
        runtime / "config" / "Icons" / "renderhive.svg",
        runtime / "config" / "Icons" / "renderhive.png",
        runtime / "python_panels" / "renderhive.pypanel",
    ]
    missing = [str(path) for path in runtime_required if not path.is_file()]
    if missing:
        raise RuntimeError("Installed runtime is incomplete:\n" + "\n".join(missing))

    template = (source / "package" / "renderhive.json.template").read_text(encoding="utf-8")
    runtime_forward = str(runtime).replace("\\", "/")
    package_data = json.loads(template.replace("__RENDERHIVE_HOUDINI_ROOT__", runtime_forward))

    written = []
    for pref in pref_dirs:
        packages = pref / "packages"
        packages.mkdir(parents=True, exist_ok=True)
        target = packages / "renderhive.json"
        target.write_text(json.dumps(package_data, indent=2), encoding="utf-8")
        written.append(target)
        print("Registered", target)

    print("Installed RenderHive Houdini", version)
    print("Runtime", runtime)
    print("Shelf", runtime / "toolbar" / "RenderHive.shelf")
    print("Shelf icon", runtime / "config" / "Icons" / "renderhive.svg")
    return runtime, written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pref-dir", action="append", default=[])
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    assert_source(source)
    pref_dirs = detect_pref_dirs(args.pref_dir)
    if not pref_dirs:
        raise RuntimeError("No supported Houdini preference folder was found. Open Houdini once, close it, then run the installer again.")
    install(source, pref_dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
