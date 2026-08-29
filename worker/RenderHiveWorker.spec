import os
from pathlib import Path

spec_dir = Path(SPECPATH)
plugins_root = spec_dir.parent / "plugins"

EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".git", ".idea", ".vscode", "tests", "tools", "backup", "backups", "reports", "logs"}
EXCLUDED_EXTS = {".pyc", ".pyo", ".log", ".tmp"}

plugin_datas = []
if plugins_root.is_dir():
    for p in plugins_root.rglob("*"):
        if p.is_file():
            parts = p.relative_to(plugins_root).parts
            if any(part in EXCLUDED_DIRS for part in parts):
                continue
            if p.suffix.lower() in EXCLUDED_EXTS:
                continue
            rel_parent = p.parent.relative_to(plugins_root).as_posix()
            target_dir = f"plugins/{rel_parent}" if rel_parent != "." else "plugins"
            plugin_datas.append((str(p), target_dir))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('render_scripts', 'render_scripts'),
    ] + plugin_datas,
    hiddenimports=[
        "core.font_loader",
        "core.gpu_info",
        "core.progress",
        "core.smooth_progress",
        "core.dcc_discovery",
        "core.process_runner",
        "core.runtime_paths",
        "core.task_normalizer",
        "core.ui_helpers",
        "daemon.api_client",
        "daemon.worker_thread",
        "adapters.base",
        "adapters.factory",
        "adapters.maya",
        "adapters.houdini",
        "ui.theme",
        "ui.icons",
        "ui.title_bar",
        "ui.widgets",
        "ui.main_window",
        "ui.settings_dialog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "http.server",
        "xmlrpc",
        "pydoc",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.QtPdf",
        "PySide6.QtVirtualKeyboard",
        "PySide6.Qt3D",
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtBluetooth",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtTest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RenderHive Worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RenderHive Worker',
)
