"""
RenderHive Server Manager — PySide6 System Tray Application

Manages all RenderHive server-side Windows services:
  - RenderHive-Postgres
  - RenderHive-Redis
  - RenderHive-API
  - RenderHive-Nginx
"""

import sys
import os
import subprocess
import webbrowser
import ctypes
import re
from pathlib import Path

# Add worker project dir to sys.path during dev so we can import ui and core
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent.parent / "worker"))

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QAction, QMouseEvent, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QMessageBox,
    QSystemTrayIcon, QMenu, QFrame, QScrollArea,
    QSizePolicy, QStackedWidget, QButtonGroup, QDialog
)

from ui.theme import APP_STYLESHEET
from ui.widgets import SegmentNavButton, SectionCard, InfoGrid, StatusChip, PathBox
from core.ui_helpers import local_ip_address
from ui.icons import get_icon, SVG_ICONS

# Inject additional SVG icons into the shared registry locally (without modifying worker files)
SVG_ICONS.update({
    "external-link": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M15 3h6v6"/>'
        '<path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
        '</svg>'
    ),
    "alert-triangle": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
        '<path d="M12 9v4"/>'
        '<path d="M12 17h.01"/>'
        '</svg>'
    ),
    "x-circle": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="m15 9-6 6"/>'
        '<path d="m9 9 6 6"/>'
        '</svg>'
    ),
    "check-circle": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/>'
        '</svg>'
    ),
    "key": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/>'
        '<path d="m21 2-9.6 9.6"/>'
        '<circle cx="7.5" cy="15.5" r="5.5"/>'
        '</svg>'
    ),
})

# Inject Manager-specific service states into the shared StatusChip class locally
StatusChip.STYLES.update({
    "RUNNING":  ("#3DDC84", "●"),
    "STARTING": ("#FFB84D", "◌"),
    "STOPPING": ("#FFB84D", "◌"),
    "STOPPED":  ("#FF5D73", "●"),
    "UNKNOWN":  ("#A1A7BB", "●"),
})

APP_VERSION = "1.0.0"

SERVICES = {
    "PostgreSQL":    "RenderHive-Postgres",
    "Redis":         "RenderHive-Redis",
    "API Server":    "RenderHive-API",
    "Celery Worker": "RenderHive-Celery-Worker",
    "Celery Beat":   "RenderHive-Celery-Beat",
    "nginx":         "RenderHive-Nginx",
    "AI Service":    "RenderHive-AI",
}

DASHBOARD_URL = "http://renderhive.local"
API_URL = "http://server.renderhive.local"

if getattr(sys, "frozen", False):
    INSTALL_DIR = Path(sys.executable).parent.parent
else:
    INSTALL_DIR = Path(__file__).parent

ENV_FILE = INSTALL_DIR / "RenderHive.env"
TOKEN_FILE = INSTALL_DIR / "farm_token.txt"
LOG_DIR = INSTALL_DIR / "logs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_sc(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["sc"] + args,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode, result.stdout
    except Exception as e:
        return -1, str(e)

def get_service_state(service_name: str) -> str:
    code, out = run_sc(["query", service_name])
    if code != 0:
        return "UNKNOWN"
    m = re.search(r"STATE\s*:.*?(\b\w+\b)\s*$", out, re.MULTILINE)
    if m:
        return m.group(1).upper()
    return "UNKNOWN"

def start_service(service_name: str) -> bool:
    code, _ = run_sc(["start", service_name])
    return code == 0

def stop_service(service_name: str) -> bool:
    code, _ = run_sc(["stop", service_name])
    return code == 0

def read_env() -> dict:
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env

def read_farm_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    return "(not found — check the API service logs)"

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def auto_elevate():
    if not is_admin():
        import ctypes
        import sys
        import shlex
        if getattr(sys, 'frozen', False):
            args = " ".join(shlex.quote(arg) for arg in sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
        else:
            args = " ".join(shlex.quote(arg) for arg in sys.argv)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
        sys.exit(0)


def ensure_local_hosts():
    """Ensure renderhive.local and server.renderhive.local are mapped to 127.0.0.1 on the server machine."""
    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    if not hosts_path.exists():
        return
    try:
        content = hosts_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        target_domains = {
            "renderhive.local": "127.0.0.1 renderhive.local",
            "server.renderhive.local": "127.0.0.1 server.renderhive.local",
        }

        new_lines = []
        found_domains = set()
        modified = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                new_lines.append(line)
                continue

            parts = stripped.split()
            if len(parts) >= 2:
                ip, domain = parts[0], parts[1].lower()
                if domain in target_domains:
                    found_domains.add(domain)
                    # If pointing to a virtual adapter (e.g. 172.x) or not 127.0.0.1, fix it
                    if ip != "127.0.0.1":
                        new_lines.append(target_domains[domain])
                        modified = True
                    else:
                        new_lines.append(line)
                    continue
            new_lines.append(line)

        for domain, correct_entry in target_domains.items():
            if domain not in found_domains:
                new_lines.append(correct_entry)
                modified = True

        if modified:
            hosts_path.write_text("\n".join(new_lines) + "\n", encoding="ascii")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Background service polling thread
# ---------------------------------------------------------------------------

class ServicePoller(QThread):
    states_updated = Signal(dict)

    def __init__(self, interval_ms: int = 3000, parent=None):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self._running = True

    def run(self):
        while self._running:
            states = {label: get_service_state(svc) for label, svc in SERVICES.items()}
            self.states_updated.emit(states)
            self.msleep(self.interval_ms)

    def stop(self):
        self._running = False


# ---------------------------------------------------------------------------
# Service Card Widget (Modern)
# ---------------------------------------------------------------------------

STATE_COLORS = {
    "RUNNING":  "#3DDC84",
    "STOPPED":  "#FF5D73",
    "STARTING": "#FFB84D",
    "STOPPING": "#FFB84D",
    "UNKNOWN":  "#A1A7BB",
}

STATE_LABELS = {
    "RUNNING":  "RUNNING",
    "STOPPED":  "STOPPED",
    "STARTING": "STARTING",
    "STOPPING": "STOPPING",
    "UNKNOWN":  "UNKNOWN",
}

class ModernServiceCard(QFrame):
    def __init__(self, label: str, service_name: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.service_name = service_name
        self.setObjectName("StatCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        name_lbl = QLabel(label)
        name_lbl.setObjectName("SectionTitle")
        layout.addWidget(name_lbl)

        layout.addStretch()

        self.state_lbl = StatusChip("UNKNOWN")
        layout.addWidget(self.state_lbl)

        self.start_btn = QPushButton("Start")
        # No object name inherits default Primary (purple) button style
        self.start_btn.setFixedWidth(72)
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("DestructiveTonalBtn")
        self.stop_btn.setFixedWidth(72)
        self.stop_btn.clicked.connect(self._stop)
        layout.addWidget(self.stop_btn)

    def update_state(self, state: str):
        self.state_lbl.set_status(state)
        running = (state == "RUNNING")
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _start(self):
        if not is_admin():
            RenderHiveMessageDialog.show_message(self, "Admin Required", "Starting services requires Administrator privileges.", icon_name="warning")
            return
        self.start_btn.setEnabled(False)
        start_service(self.service_name)

    def _stop(self):
        if not is_admin():
            RenderHiveMessageDialog.show_message(self, "Admin Required", "Stopping services requires Administrator privileges.", icon_name="warning")
            return
        self.stop_btn.setEnabled(False)
        stop_service(self.service_name)


# ---------------------------------------------------------------------------
# Main Window (Modern Frameless)
# ---------------------------------------------------------------------------

class OpenablePathBox(PathBox):
    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        header = self.layout().itemAt(0).layout()
        
        # Align title label horizontally with the buttons
        header.setAlignment(Qt.AlignVCenter)
        
        # Increase margin between header (buttons) and the field itself below
        self.layout().setSpacing(12)
        
        self.open_btn = QPushButton("  Open")
        self.open_btn.setObjectName("SecondaryBtn")
        self.open_btn.setIcon(get_icon("external-link", "#CBD5E1", 12))
        self.open_btn.setFixedHeight(26)
        self.open_btn.setStyleSheet("min-height: 26px; max-height: 26px; padding: 0 10px; font-size: 12px; margin-right: 4px;")
        self.open_btn.clicked.connect(self._open_path)
        
        # Insert before the copy button
        header.insertWidget(header.count() - 1, self.open_btn)

    def _open_path(self):
        path = self.path_label.text().strip()
        if path and path != "—":
            target = path
            if not os.path.isdir(target):
                target = os.path.dirname(target)
                
            # Fallback to nearest existing parent directory if it doesn't exist yet
            while target and not os.path.exists(target):
                parent = os.path.dirname(target)
                if parent == target:
                    break
                target = parent
                
            if target and os.path.exists(target):
                os.startfile(target)


class RenderHiveMessageDialog(QDialog):
    """Custom premium dialog replacing generic QMessageBox."""

    def __init__(self, title, message, icon_name="info", buttons=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        
        self._apply_window_theme()
        
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor("#080A0E"))
        pal.setColor(QPalette.Base, QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header Frame ──
        header_frame = QFrame()
        header_frame.setObjectName("DialogHeader")
        header_row = QHBoxLayout(header_frame)
        header_row.setContentsMargins(24, 18, 24, 18)
        header_row.setSpacing(12)
        
        icon_color = "#3B82F6" # default info blue
        lucide_icon = icon_name
        if icon_name == "info":
            icon_color = "#3B82F6"
            lucide_icon = "info"
        elif icon_name == "warning":
            icon_color = "#F59E0B"
            lucide_icon = "alert-triangle"
        elif icon_name in ("error", "critical"):
            icon_color = "#EF4444"
            lucide_icon = "x-circle"
        elif icon_name == "success":
            icon_color = "#10B981"
            lucide_icon = "check-circle"

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon(lucide_icon, icon_color, 24).pixmap(24, 24))
        header_row.addWidget(icon_lbl)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #FFFFFF;")
        header_row.addWidget(title_lbl, 1)
        
        root.addWidget(header_frame)
        
        # ── Body Frame ──
        body_frame = QFrame()
        body_layout = QVBoxLayout(body_frame)
        body_layout.setContentsMargins(24, 24, 24, 24)
        body_layout.setSpacing(20)

        # Message
        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet("font-size: 13px; color: #CBD5E1;")
        msg_lbl.setWordWrap(True)
        body_layout.addWidget(msg_lbl)
        
        body_layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        self.clicked_button = None
        if not buttons:
            buttons = [("OK", "primary")]
            
        for btn_text, btn_role in buttons:
            btn = QPushButton("  " + btn_text + "  ")
            if btn_role == "secondary":
                btn.setObjectName("SecondaryBtn")
            elif btn_role == "destructive":
                btn.setObjectName("DestructiveTonalBtn")
            btn.setCursor(Qt.PointingHandCursor)
            
            # Using PySide6 partial/lambda
            btn.clicked.connect(lambda checked=False, t=btn_text: self._on_btn_clicked(t))
            btn_layout.addWidget(btn)
            
        body_layout.addLayout(btn_layout)
        root.addWidget(body_frame, 1)

    def _on_btn_clicked(self, text):
        self.clicked_button = text
        self.accept()
        
    def showEvent(self, event):
        super().showEvent(event)
        self._apply_window_theme()
        
    def _apply_window_theme(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes.wintypes as wintypes
            hwnd = wintypes.HWND(int(self.winId()))
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(0x00170E0B)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(0x00E1D5CB)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(ctypes.c_int(0x0036251E)), 4)
        except Exception:
            pass

    @classmethod
    def show_message(cls, parent, title, message, icon_name="info", buttons=None):
        dlg = cls(title, message, icon_name, buttons, parent)
        dlg.exec()
        return dlg.clicked_button


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RenderHive Server Manager")
        self.setMinimumSize(800, 600)
        self.resize(800, 600)

        # Look for multi-resolution icon first
        icon_path = str(INSTALL_DIR / "assets" / "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = str(INSTALL_DIR / "assets" / "icon.png")
        if not os.path.exists(icon_path):
            icon_path = str(INSTALL_DIR / "assets" / "icon.svg")
            
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))

        self._quitting = False
        ensure_local_hosts()
        self._setup_tray(icon_path)
        self._build_ui(icon_path)
        self._apply_native_dwm_styling()
        self._start_poller()

    def _open_dashboard(self):
        ensure_local_hosts()
        webbrowser.open(DASHBOARD_URL)

    def _setup_tray(self, icon_path: str):
        self.tray = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        else:
            self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()
        show_act = QAction("Show Manager", self)
        show_act.triggered.connect(self.showNormal)
        tray_menu.addAction(show_act)

        dashboard_act = QAction("Open Dashboard", self)
        dashboard_act.triggered.connect(self._open_dashboard)
        tray_menu.addAction(dashboard_act)

        tray_menu.addSeparator()

        start_all_act = QAction("Start All Services", self)
        start_all_act.triggered.connect(self._start_all)
        tray_menu.addAction(start_all_act)

        stop_all_act = QAction("Stop All Services", self)
        stop_all_act.triggered.connect(self._stop_all)
        tray_menu.addAction(stop_all_act)

        tray_menu.addSeparator()

        quit_act = QAction("Quit Manager", self)
        quit_act.triggered.connect(self._quit)
        tray_menu.addAction(quit_act)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _apply_native_dwm_styling(self, target=None):
        """Seamlessly match native OS titlebar and window borders to pro dark theme (#0B0E17)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes.wintypes as wintypes

            widget = target or self
            hwnd = wintypes.HWND(int(widget.winId()))

            # Enable Immersive Dark Mode (Win 11 & Win 10 20H1+)
            DWMWA_USE_IMMERSIVE_DARK_MODE_1 = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_2 = 19
            dark_val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_1, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
            )
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_2, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
            )

            # Match native caption color to #0B0E17 (COLORREF: 0x00BBGGRR -> 0x00170E0B)
            DWMWA_CAPTION_COLOR = 35
            caption_color = ctypes.c_int(0x00170E0B)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption_color), ctypes.sizeof(caption_color)
            )

            # Match native title text color to #CBD5E1 (COLORREF: 0x00E1D5CB)
            DWMWA_TEXT_COLOR = 36
            text_color = ctypes.c_int(0x00E1D5CB)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text_color), ctypes.sizeof(text_color)
            )

            # Match subtle native border color to #1E2536 (COLORREF: 0x0036251E)
            DWMWA_BORDER_COLOR = 34
            border_color = ctypes.c_int(0x0036251E)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border_color), ctypes.sizeof(border_color)
            )
        except Exception:
            pass

    def _build_ui(self, icon_path: str):
        root_frame = QFrame(self)
        root_frame.setObjectName("RootFrame")
        self.setCentralWidget(root_frame)
        
        # We apply the studio background to the root frame
        root_frame.setAutoFillBackground(True)
        cpal = root_frame.palette()
        cpal.setColor(QPalette.ColorRole.Window, QColor("#080A0E"))
        cpal.setColor(QPalette.ColorRole.Base, QColor("#080A0E"))
        root_frame.setPalette(cpal)

        main_layout = QVBoxLayout(root_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Segmented Nav Header
        header_bar = QFrame()
        header_bar.setObjectName("TopHeaderBar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(14, 9, 14, 9)
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignVCenter)
        
        nav_container = QFrame()
        nav_container.setObjectName("NavSegmentContainer")
        nav_container.setFixedHeight(32)
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(2, 2, 2, 2)
        nav_layout.setSpacing(2)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        
        btn_services = SegmentNavButton("server", "Services")
        btn_config = SegmentNavButton("key", "Credentials")
        btn_logs = SegmentNavButton("terminal", "Logs")
        
        self.nav_group.addButton(btn_services, 0)
        self.nav_group.addButton(btn_config, 1)
        self.nav_group.addButton(btn_logs, 2)
        
        btn_services.setChecked(True)
        
        self.nav_group.idClicked.connect(self._switch_tab)
        
        nav_layout.addWidget(btn_services)
        nav_layout.addWidget(btn_config)
        nav_layout.addWidget(btn_logs)
        
        header_layout.addWidget(nav_container)
        header_layout.addStretch()



        self.dashboard_btn = QPushButton("  Open Dashboard")
        self.dashboard_btn.setIcon(get_icon("external-link", "#080A0F", 14))
        self.dashboard_btn.setCursor(Qt.PointingHandCursor)
        self.dashboard_btn.clicked.connect(self._open_dashboard)
        self.dashboard_btn.setEnabled(False) # Default disabled until poller fires
        header_layout.addWidget(self.dashboard_btn)

        content_layout.addWidget(header_bar)

        # Stacked Widget
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainContentStack")
        
        self.stack.addWidget(self._build_services_tab())
        self.stack.addWidget(self._build_config_tab())
        self.stack.addWidget(self._build_logs_tab())
        
        content_layout.addWidget(self.stack)

        # ── Native Full-Width Bottom Status Bar ──────────────────
        bottom_bar = QFrame()
        bottom_bar.setObjectName("BottomStatusBar")
        bottom_bar.setFixedHeight(30)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 0, 12, 0)
        bottom_layout.setSpacing(6)
        bottom_layout.setAlignment(Qt.AlignVCenter)

        self.status_chip = StatusChip("OFFLINE")
        bottom_layout.addWidget(self.status_chip)

        div1 = QLabel("│")
        div1.setObjectName("StatusBarDivider")
        bottom_layout.addWidget(div1)

        self.status_desc_label = QLabel("Initializing RenderHive Manager...")
        self.status_desc_label.setObjectName("StatusBarHint")
        bottom_layout.addWidget(self.status_desc_label, 1)

        div2 = QLabel("│")
        div2.setObjectName("StatusBarDivider")
        bottom_layout.addWidget(div2)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("StatusBarDcc")
        bottom_layout.addWidget(version_label)

        content_layout.addWidget(bottom_bar)
        main_layout.addLayout(content_layout)

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)

    def _build_services_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        self.overall_status_lbl = QLabel("Checking services…")
        self.overall_status_lbl.setObjectName("MutedLabel")
        header_layout.addWidget(self.overall_status_lbl)
        header_layout.addStretch()

        start_all_btn = QPushButton("Start All")
        start_all_btn.setObjectName("SecondaryBtn")
        start_all_btn.clicked.connect(self._start_all)
        header_layout.addWidget(start_all_btn)

        stop_all_btn = QPushButton("Stop All")
        stop_all_btn.setObjectName("DestructiveTonalBtn")
        stop_all_btn.clicked.connect(self._stop_all)
        header_layout.addWidget(stop_all_btn)

        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        self.service_cards: dict[str, ModernServiceCard] = {}
        for label, svc_name in SERVICES.items():
            card = ModernServiceCard(label, svc_name)
            self.service_cards[label] = card
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return w

    def _build_config_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(24)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(24)

        env = read_env()
        token = read_farm_token()

        # Network
        net_card = SectionCard("Network Configuration", "URLs and IPs used by RenderHive")
        net_grid = InfoGrid([
            ("dashboard", "Dashboard URL"),
            ("api", "API URL"),
            ("ip", "Server IP")
        ])
        net_grid.set_values({
            "dashboard": DASHBOARD_URL,
            "api": API_URL,
            "ip": local_ip_address()
        })
        net_card.add_widget(net_grid)
        inner.addWidget(net_card)

        # Auth
        auth_card = SectionCard("Administrator Account", "Dashboard login credentials")
        auth_grid = InfoGrid([
            ("user", "Username"),
            ("email", "Email")
        ])
        auth_grid.set_values({
            "user": env.get("DJANGO_SUPERUSER_USERNAME", "admin"),
            "email": env.get("DJANGO_SUPERUSER_EMAIL", "")
        })
        auth_card.add_widget(auth_grid)
        
        inner.addWidget(auth_card)

        # Token
        token_card = SectionCard("Farm Service Token", "Used to authenticate worker nodes")
        token_box = PathBox("API Token")
        token_box.set_path(token)
        token_card.add_widget(token_box)
        note = QLabel("Copy this token into the Worker daemon Settings.")
        note.setObjectName("MutedLabel")
        token_card.add_widget(note)
        inner.addWidget(token_card)

        # Paths
        paths_card = SectionCard("Installation Paths", "Local file system paths")
        dir_box = OpenablePathBox("Install Directory")
        dir_box.set_path(str(INSTALL_DIR))
        paths_card.add_widget(dir_box)

        env_box = OpenablePathBox("Environment File")
        env_box.set_path(str(ENV_FILE))
        paths_card.add_widget(env_box)

        logs_box = OpenablePathBox("Logs Directory")
        logs_box.set_path(str(LOG_DIR))
        paths_card.add_widget(logs_box)
        inner.addWidget(paths_card)

        inner.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return w

    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        toolbar = QHBoxLayout()
        lbl = QLabel("Live tail of service logs:")
        lbl.setObjectName("MutedLabel")
        toolbar.addWidget(lbl)
        toolbar.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.clicked.connect(self._clear_log)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background: #080A0F; color: #CBD5E1; font-family: 'JetBrains Mono', Consolas, monospace; "
            "font-size: 13px; border: 1px solid #1E2536; border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(self.log_view)

        self._log_positions: dict[str, int] = {}
        self._log_timer = QTimer(self)
        self._log_timer.setInterval(2000)
        self._log_timer.timeout.connect(self._tail_logs)
        self._log_timer.start()

        return w

    # ------------------------------------------------------------------
    # Polling & Logs
    # ------------------------------------------------------------------

    def _start_poller(self):
        self.poller = ServicePoller(interval_ms=3000, parent=self)
        self.poller.states_updated.connect(self._on_states_updated)
        self.poller.start()

    def _on_states_updated(self, states: dict):
        for label, card in self.service_cards.items():
            state = states.get(label, "UNKNOWN")
            card.update_state(state)

        all_running = all(s == "RUNNING" for s in states.values())
        all_stopped = all(s in ("STOPPED", "UNKNOWN") for s in states.values())
        n_running = sum(1 for s in states.values() if s == "RUNNING")
        total = len(states)

        if all_running:
            self.overall_status_lbl.setText(f"All {total} services running ✓")
            self.overall_status_lbl.setStyleSheet("color: #4ADE80; font-weight: 600; background: transparent;")
            self.tray.setToolTip("RenderHive Server — All services running")
            self.status_chip.set_status("ONLINE")
            self.status_desc_label.setText("System operational. All backend services are running.")
            self.dashboard_btn.setEnabled(True)
        elif all_stopped:
            self.overall_status_lbl.setText("All services stopped")
            self.overall_status_lbl.setStyleSheet("color: #F87171; font-weight: 600; background: transparent;")
            self.tray.setToolTip("RenderHive Server — Stopped")
            self.status_chip.set_status("ERROR")
            self.status_desc_label.setText("System halted. All backend services are currently stopped.")
            self.dashboard_btn.setEnabled(False)
        else:
            self.overall_status_lbl.setText(f"{n_running}/{total} services running")
            self.overall_status_lbl.setStyleSheet("color: #FBBF24; font-weight: 600; background: transparent;")
            self.tray.setToolTip(f"RenderHive Server — {n_running}/{total} running")
            self.status_chip.set_status("WARNING")
            self.status_desc_label.setText(f"Degraded state. Only {n_running} of {total} services are running.")
            self.dashboard_btn.setEnabled(False)

    def _tail_logs(self):
        log_files = {
            "API":           LOG_DIR / "api.log",
            "Celery Worker": LOG_DIR / "celery-worker.log",
            "Celery Beat":   LOG_DIR / "celery-beat.log",
            "nginx":         LOG_DIR / "nginx-error.log",
            "Postgres":      LOG_DIR / "postgres-stderr.log",
            "Redis":         LOG_DIR / "redis-stderr.log",
        }
        new_text = []
        for name, path in log_files.items():
            if not path.exists():
                continue
            pos = self._log_positions.get(str(path), 0)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read(4096)
                    new_pos = f.tell()
                if chunk:
                    self._log_positions[str(path)] = new_pos
                    for line in chunk.splitlines():
                        new_text.append(f"[{name}] {line}")
            except OSError:
                pass

        if new_text:
            self.log_view.append("\n".join(new_text))
            sb = self.log_view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _clear_log(self):
        self.log_view.clear()
        self._log_positions.clear()

    # ------------------------------------------------------------------
    # Service control
    # ------------------------------------------------------------------

    def _start_all(self):
        if not is_admin():
            RenderHiveMessageDialog.show_message(self, "Admin Required", "Starting services requires Administrator privileges.", icon_name="warning")
            return
        ensure_local_hosts()
        for svc_name in SERVICES.values():
            start_service(svc_name)

    def _stop_all(self):
        if not is_admin():
            RenderHiveMessageDialog.show_message(self, "Admin Required", "Stopping services requires Administrator privileges.", icon_name="warning")
            return
        for svc_name in reversed(list(SERVICES.values())):
            stop_service(svc_name)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Tray & System Events
    # ------------------------------------------------------------------

    def show_from_tray(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(160)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.show_from_tray()

    def closeEvent(self, event):
        if hasattr(self, "_quitting") and self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()

        if hasattr(self, "tray") and self.tray and self.tray.isVisible():
            running_count = sum(
                1 for chip in getattr(self, "_chips", {}).values()
                if getattr(chip, "text", lambda: "")() == "RUNNING"
            )
            total_count = len(SERVICES)

            if running_count == total_count and total_count > 0:
                title = "Server Manager Minimized — Online"
                msg = "All RenderHive services are active and running in the background.\nClick the tray icon to restore the window."
            elif running_count > 0:
                title = f"Server Manager Minimized — {running_count}/{total_count} Services Active"
                msg = f"{running_count} of {total_count} services are running in the background.\nClick the tray icon to restore the window."
            else:
                title = "Server Manager Minimized to Tray"
                msg = "The application is running in the background.\nClick the tray icon to restore or right-click to exit."

            icon = self.tray.icon()
            if icon and not icon.isNull():
                self.tray.showMessage(
                    title,
                    msg,
                    icon,
                    3000,
                )
            else:
                self.tray.showMessage(
                    title,
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )

    def _quit(self):
        self._quitting = True
        if hasattr(self, "poller"):
            self.poller.stop()
        self._stop_all()
        QApplication.instance().quit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    auto_elevate()
    from core.font_loader import load_application_fonts
    
    app = QApplication(sys.argv)
    app.setApplicationName("RenderHive Server Manager")
    app.setOrganizationName("RenderHive")
    app.setOrganizationDomain("renderhive.io")

    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "RenderHive Server Manager"
            )
        except Exception:
            pass

    load_application_fonts(app)
    app.setStyleSheet(APP_STYLESHEET)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
