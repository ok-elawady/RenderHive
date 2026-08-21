"""RenderHive multi-DCC worker application with production dashboard UI.

The worker keeps the existing Maya/Houdini adapter architecture while exposing
Deadline-class operational information through a RenderHive-specific interface.
"""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from daemon.worker_thread import WorkerThread, format_installations_summary
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.theme import APP_STYLESHEET
from version import WORKER_VERSION

# Export for backward-compatibility with tests that import from app
__all__ = [
    "MainWindow",
    "SettingsDialog",
    "WorkerThread",
    "format_installations_summary",
    "main",
]


def _acquire_single_instance_lock():
    """Acquire a single instance lock resilient to crashes.
    
    Uses a Windows Named Mutex on NT which the OS kernel automatically
    releases if the process crashes or is killed, falling back to QSharedMemory.
    """
    if os.name == "nt":
        mutex_name = f"Global\\RenderHiveWorkerSingleton_{WORKER_VERSION}"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if last_error == ERROR_ALREADY_EXISTS:
            return None
        return mutex
    else:
        shared_memory = QSharedMemory("RenderHiveWorkerSingleton")
        if not shared_memory.create(1):
            return None
        return shared_memory


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RenderHive Worker")
    app.setOrganizationName("RenderHive")
    app.setOrganizationDomain("renderhive.io")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    lock = _acquire_single_instance_lock()
    if lock is None:
        QMessageBox.warning(None, "Already Running", "RenderHive Worker is already running.")
        return 0

    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "RenderHive Worker"
            )
        except Exception:
            pass

    from core.font_loader import load_application_fonts

    load_application_fonts(app)
    app.setStyleSheet(APP_STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
