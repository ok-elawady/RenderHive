"""Modern Full-Width Studio Dashboard for RenderHive Multi-DCC Worker.

Faithfully implements the modern Studio App layout from the Next.js frontend:
- Custom frameless studio titlebar with seamless 8-zone edge-resizing, top-bar resizing, and balanced padding
- Top Segmented Pill Navigation Bar (Active Task, Node Telemetry, Output Log) with matching icon colors
- Full-width viewport with KPI metric cards, progress hero stage, and copyable paths
- 4-Gauge live hardware telemetry (CPU, RAM, GPU/VRAM, Storage)
- Full-page VFX Terminal Console with colorized log streams, search filter, and auto-scroll control
- Compact Bottom Studio Status Bar with persistent status badges, live event preview, and non-overflowing refresh button
- Smooth geometry and opacity animations on window resizing, maximize/restore, and minimizing
- Generous spacing and WCAG 2.1 AA/AAA accessible high-contrast legibility
"""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def get_plugins_dir() -> Path:
    """Resolve the plugins directory across dev checkouts, PyInstaller frozen bundles, and Inno Setup installs."""
    candidates = []
    
    # 1. PyInstaller frozen runtime (_MEIPASS and executable directory)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "plugins")
            candidates.append(Path(meipass) / "_internal" / "plugins")
            candidates.append(Path(meipass).parent / "plugins")
            candidates.append(Path(meipass).parent / "_internal" / "plugins")
            
        try:
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir / "plugins")
            candidates.append(exe_dir / "_internal" / "plugins")
            candidates.append(exe_dir.parent / "plugins")
            candidates.append(exe_dir.parent / "_internal" / "plugins")
        except Exception:
            pass

    # 2. Source / development checkout
    try:
        source_root = Path(__file__).resolve().parent.parent.parent
        candidates.append(source_root / "plugins")
    except Exception:
        pass

    try:
        source_parent = Path(__file__).resolve().parent.parent
        candidates.append(source_parent / "plugins")
    except Exception:
        pass

    # 3. Current working directory
    try:
        candidates.append(Path.cwd() / "plugins")
        candidates.append(Path.cwd() / "_internal" / "plugins")
        candidates.append(Path.cwd().parent / "plugins")
    except Exception:
        pass

    # 4. Standard Windows / Program Files / LocalAppData install locations
    for env_var in ("PROGRAMFILES", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA"):
        val = os.environ.get(env_var)
        if val:
            candidates.append(Path(val) / "RenderHive" / "Worker" / "_internal" / "plugins")
            candidates.append(Path(val) / "RenderHive" / "Worker" / "plugins")
            candidates.append(Path(val) / "RenderHive" / "plugins")

    # Return the first candidate that contains at least maya or houdini plugins
    for c in candidates:
        try:
            if c.is_dir() and ((c / "maya").is_dir() or (c / "houdini").is_dir()):
                return c
        except Exception:
            pass

    # Secondary check: any existing directory in candidates
    for c in candidates:
        try:
            if c.is_dir():
                return c
        except Exception:
            pass

    return candidates[0] if candidates else Path("plugins")


_PLUGINS_DIR = get_plugins_dir()
import psutil
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, QSettings, QTimer, Qt, QUrl, Slot, QThread, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QDesktopServices, QIcon, QMouseEvent, QPaintEvent, QPainter, QPalette, QResizeEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.dcc_discovery import DCCInstallation, discover_all
from core.gpu_info import GPUDetector
from core.runtime_paths import writable_log_root
from core.smooth_progress import SmoothProgressValue
from core.ui_helpers import (
    collect_disk_metrics,
    format_bytes,
    format_duration,
    format_timestamp,
    get_cpu_name,
    local_ip_address,
    mac_address,
    machine_user,
    pool_names_from_worker,
    safe_dict,
    safe_text,
)
from daemon.worker_thread import WorkerThread, format_installations_summary
from ui.icons import get_icon
from ui.settings_dialog import SettingsDialog
from ui.title_bar import CustomTitleBar
from ui.widgets import EmptyState, InfoGrid, PathBox, ResourceMeter, SectionCard, SegmentNavButton, StatCard, StatusChip
from version import WORKER_VERSION

HOSTNAME = socket.gethostname()
RESIZE_MARGIN = 6


def _disk_root() -> str:
    if os.name == "nt":
        return (os.environ.get("SystemDrive") or "C:") + "\\"
    return "/"


def _installation_rows(discovered: Dict[str, Sequence[DCCInstallation]]) -> List[List[str]]:
    rows: List[List[str]] = []
    for dcc in ("maya", "houdini"):
        for item in discovered.get(dcc) or []:
            if dcc == "maya":
                tools = [name for name in ("render", "mayapy", "maya") if item.executables.get(name)]
            else:
                tools = [name for name in ("hython", "husk", "houdini") if item.executables.get(name)]
            rows.append([dcc.title(), item.version, ", ".join(tools) or "Unavailable", item.root])
    return rows


class PointerCursorFilter(QObject):
    """Event filter ensuring all clickable controls (buttons, tabs, checkboxes) use PointingHandCursor."""

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Show, QEvent.Type.Polish):
            if isinstance(obj, (QAbstractButton, QTabBar)):
                obj.setCursor(Qt.PointingHandCursor)
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RenderHive Worker {}".format(WORKER_VERSION))
        self.resize(920, 600)
        self.setMinimumSize(780, 500)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._cursor_filter = PointerCursorFilter(self)
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.installEventFilter(self._cursor_filter)

        self.is_quitting = False
        self.worker_status = "OFFLINE"
        self.scheduler_status = "STOPPED"
        self.backend_connected = False
        self.worker_started_monotonic = 0.0
        self.current_task: Dict[str, Any] = {}
        self.current_task_started = 0.0
        self.current_progress_percent = 0
        self.current_progress_target = 0
        self.progress_animator = SmoothProgressValue(0.0, 0.0)
        self.current_progress_phase = "Idle"
        self.current_progress_frame = None
        self.current_progress_total_frames = 1
        self.current_progress_eta_seconds = None
        self.last_system_info: Dict[str, Any] = {}
        self.server_worker: Dict[str, Any] = {}
        self.current_log_path = ""
        self.auto_scroll_locked = False
        self._history_drawer_open = False
        self._history_entries: List[Dict[str, Any]] = []
        self.title_bar = None

        self.settings = QSettings("RenderHive", "WorkerDaemon")
        self.worker_thread: Optional[WorkerThread] = None
        self.discovered = self.discover_dccs()
        self._cached_cpu_name = get_cpu_name()
        self.local_gpu_detector = GPUDetector()
        self._cached_gpu_info: Dict[str, Any] = self.local_gpu_detector.query()
        self._last_local_gpu_query = time.monotonic()

        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        show_action = QAction("Show RenderHive Worker", self)
        show_action.setIcon(get_icon("play", "#CBD5E1", 13))
        show_action.triggered.connect(self.show_from_tray)
        pause_action = QAction("Pause / Resume Dispatch", self)
        pause_action.setIcon(get_icon("pause", "#CBD5E1", 13))
        pause_action.triggered.connect(self.toggle_dispatch_pause)
        settings_action = QAction("Settings", self)
        settings_action.setIcon(get_icon("settings", "#CBD5E1", 13))
        settings_action.triggered.connect(self.open_settings)
        quit_action = QAction("Quit", self)
        quit_action.setIcon(get_icon("x", "#CBD5E1", 13))
        quit_action.triggered.connect(self.quit_app)
        tray_menu = QMenu(self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(pause_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        QApplication.instance().aboutToQuit.connect(self.stop_worker)

        self._plugin_workers = {}
        self._plugin_install_btns = {}
        self._plugin_uninstall_btns = {}
        self._plugin_alert_titles = {}
        self._plugin_alert_descs = {}
        self._plugin_alert_icons = {}
        self._plugin_alert_frames = {}
        self._dcc_path_inputs = {}

        self._build_ui(icon_path)
        # Populate plugin status chips immediately so they reflect reality on first launch
        QTimer.singleShot(0, self._refresh_plugin_status)
        geometry = self.settings.value("studio_geometry_v141")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass
        # Always start on the main Active Task dashboard
        try:
            self._nav_group.buttons()[0].setChecked(True)
            self.main_stack.setCurrentIndex(0)
        except Exception:
            pass

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(1000)
        self.ui_timer.timeout.connect(self.update_live_ui)
        self.ui_timer.start()

        self.progress_animation_timer = QTimer(self)
        self.progress_animation_timer.setInterval(25)
        self.progress_animation_timer.timeout.connect(self._animate_progress_tick)
        self.progress_animation_timer.start()

        self.refresh_dcc_tables()
        self.refresh_local_snapshot()
        self.log("Worker UI initialized. Ready for dispatch.")

        auto_start = str(self.settings.value("auto_start", "false")).lower() == "true"
        start_minimized = str(self.settings.value("start_minimized", "false")).lower() == "true"
        if start_minimized:
            QTimer.singleShot(0, self.hide)
        if auto_start:
            QTimer.singleShot(250, self.start_worker)

    def _build_ui(self, icon_path: str) -> None:
        central = QFrame()
        central.setObjectName("RootFrame")
        central.setMouseTracking(True)
        central.setAutoFillBackground(True)
        cpal = central.palette()
        cpal.setColor(QPalette.ColorRole.Window, QColor("#080A0E"))
        cpal.setColor(QPalette.ColorRole.Base, QColor("#080A0E"))
        central.setPalette(cpal)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top Header Navigation & Control Bar (Full-Width Studio Header) ──
        top_header = QFrame()
        top_header.setObjectName("TopHeaderBar")
        top_layout = QHBoxLayout(top_header)
        top_layout.setContentsMargins(14, 9, 14, 9)
        top_layout.setSpacing(8)
        top_layout.setAlignment(Qt.AlignVCenter)

        # Segmented Pill Navigation Container (Left Side)
        nav_container = QFrame()
        nav_container.setObjectName("NavSegmentContainer")
        nav_container.setFixedHeight(32)
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(2, 2, 2, 2)
        nav_layout.setSpacing(2)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        self.nav_dash_btn = SegmentNavButton("play", "Active Task")
        self.nav_dash_btn.setFixedHeight(28)
        self.nav_dash_btn.setChecked(True)
        self._nav_group.addButton(self.nav_dash_btn, 0)
        nav_layout.addWidget(self.nav_dash_btn)

        self.nav_telemetry_btn = SegmentNavButton("cpu", "Node Telemetry")
        self.nav_telemetry_btn.setFixedHeight(28)
        self._nav_group.addButton(self.nav_telemetry_btn, 1)
        nav_layout.addWidget(self.nav_telemetry_btn)

        self.nav_logs_btn = SegmentNavButton("terminal", "Output Log")
        self.nav_logs_btn.setFixedHeight(28)
        self._nav_group.addButton(self.nav_logs_btn, 2)
        nav_layout.addWidget(self.nav_logs_btn)
        self.nav_dcc_btn = SegmentNavButton("package", "Integrations")
        self.nav_dcc_btn.setFixedHeight(28)
        self._nav_group.addButton(self.nav_dcc_btn, 3)
        nav_layout.addWidget(self.nav_dcc_btn)

        self._nav_group.idClicked.connect(self._on_nav_tab_changed)
        top_layout.addWidget(nav_container)

        # Stretch pushes controls to the right
        top_layout.addStretch(1)

        # Joined Pause Button Group with Vertical Divider
        self.pause_group = QFrame()
        self.pause_group.setObjectName("PauseButtonGroup")
        self.pause_group.setFixedHeight(32)
        pause_layout = QHBoxLayout(self.pause_group)
        pause_layout.setContentsMargins(1, 0, 1, 0)
        pause_layout.setSpacing(0)

        self.pause_dispatch_btn = QPushButton()
        self.pause_dispatch_btn.setObjectName("JoinedLeftBtn")
        self.pause_dispatch_btn.setIcon(get_icon("pause", "#475569", 13))
        self.pause_dispatch_btn.setFixedSize(30, 30)
        self.pause_dispatch_btn.setToolTip("Pause Dispatch")
        self.pause_dispatch_btn.setAccessibleName("Pause or Resume Job Dispatch")
        self.pause_dispatch_btn.clicked.connect(self.toggle_dispatch_pause)
        self.pause_dispatch_btn.setEnabled(False)
        pause_layout.addWidget(self.pause_dispatch_btn)

        self.pause_divider = QFrame()
        self.pause_divider.setObjectName("JoinedDivider")
        self.pause_divider.setFixedHeight(22)
        pause_layout.addWidget(self.pause_divider)

        self.after_task_btn = QPushButton("Pause After Task")
        self.after_task_btn.setObjectName("JoinedRightBtn")
        self.after_task_btn.setFixedHeight(30)
        self.after_task_btn.setCheckable(True)
        self.after_task_btn.setToolTip("Pause daemon after current task finishes")
        self.after_task_btn.setAccessibleName("Pause Daemon After Current Task Completes")
        self.after_task_btn.clicked.connect(self.toggle_pause_after_task)
        self.after_task_btn.setEnabled(False)
        pause_layout.addWidget(self.after_task_btn)

        top_layout.addWidget(self.pause_group)

        # Dynamic Start / Stop Worker Button
        self.start_btn = QPushButton("  Start Worker")
        self.start_btn.setIcon(get_icon("play", "#080A0F", 12))
        self.start_btn.setFixedSize(126, 32)
        self.start_btn.setAccessibleName("Start Worker Daemon")
        self.start_btn.clicked.connect(self.toggle_worker_daemon)
        self.stop_btn = self.start_btn  # Alias for backward compatibility
        top_layout.addWidget(self.start_btn)

        # Settings Icon Button
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("SecondaryBtn")
        self.settings_btn.setIcon(get_icon("settings", "#FFFFFF", 14))
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setToolTip("Worker Settings")
        self.settings_btn.setAccessibleName("Open Settings Dialog")
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn)

        outer.addWidget(top_header)

        # ── Window Body with Generous Page Padding ──
        body = QWidget()
        body.setMouseTracking(True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)

        # ── Main Content Viewport Stack ──────────────────────────
        self.main_stack = QStackedWidget()
        self.main_stack.setObjectName("MainContentStack")
        self.main_stack.addWidget(self.build_job_page())
        self.main_stack.addWidget(self.build_telemetry_page())
        self.main_stack.addWidget(self.build_terminal_page())
        self.main_stack.addWidget(self.build_plugins_page())
        body_layout.addWidget(self.main_stack, 1)

        outer.addWidget(body, 1)

        # ── Native Full-Width Bottom Status Bar ──────────────────
        bottom_bar = QFrame()
        bottom_bar.setObjectName("BottomStatusBar")
        bottom_bar.setFixedHeight(30)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 0, 12, 0)
        bottom_layout.setSpacing(6)
        bottom_layout.setAlignment(Qt.AlignVCenter)

        # Unified Daemon Status Chip (Embedded on far left of bottom bar)
        self.status_chip = StatusChip("OFFLINE")
        self.conn_chip = self.status_chip
        bottom_layout.addWidget(self.status_chip)

        div0 = QLabel("│")
        div0.setObjectName("StatusBarDivider")
        bottom_layout.addWidget(div0)

        # DCC summary
        self.header_dcc_label = QLabel(self.short_dcc_summary().replace("\n", "  •  "))
        self.header_dcc_label.setObjectName("StatusBarDcc")
        self.header_dcc_label.setToolTip(format_installations_summary(self.discovered))
        bottom_layout.addWidget(self.header_dcc_label)

        div1 = QLabel("│")
        div1.setObjectName("StatusBarDivider")
        bottom_layout.addWidget(div1)

        # Live log event preview
        self.log_preview_label = QLabel("Ready")
        self.log_preview_label.setObjectName("StatusBarHint")
        bottom_layout.addWidget(self.log_preview_label, 1)

        # Quick refresh button
        self.refresh_btn = QPushButton("  Refresh")
        self.refresh_btn.setObjectName("StatusBarBtn")
        self.refresh_btn.setIcon(get_icon("refresh", "#CBD5E1", 11))
        self.refresh_btn.setAccessibleName("Refresh Server Data and Profile")
        self.refresh_btn.clicked.connect(self.refresh_server_data)
        bottom_layout.addWidget(self.refresh_btn)

        div2 = QLabel("│")
        div2.setObjectName("StatusBarDivider")
        bottom_layout.addWidget(div2)

        # Version label on far right
        self.footer_version_label = QLabel("v{}".format(WORKER_VERSION))
        self.footer_version_label.setObjectName("StatusBarDcc")
        bottom_layout.addWidget(self.footer_version_label)

        outer.addWidget(bottom_bar)

    def _on_nav_tab_changed(self, tab_id: int) -> None:
        self.main_stack.setCurrentIndex(tab_id)
        if tab_id == 3:
            self._refresh_plugin_status()

    def animate_minimize(self) -> None:
        """Minimize the window."""
        self.showMinimized()

    def toggle_maximize_window(self) -> None:
        """Toggle between maximized and normal window state."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_window_theme()

    def _apply_window_theme(self, target: Optional[QWidget] = None) -> None:
        """Seamlessly match native OS titlebar and window borders to pro dark theme (#0B0E17)."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
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

    def _get_edge_at(self, pos: QPoint) -> Optional[str]:
        return None



    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout(self.width())

    def _update_responsive_layout(self, width: int) -> None:
        if not hasattr(self, "history_container") or not hasattr(self, "history_toggle_btn"):
            return
        is_compact = width < 920
        self.history_toggle_btn.setVisible(is_compact)
        self.history_container.setVisible(not is_compact)
        if not is_compact:
            self.history_toggle_btn.setChecked(False)

    def toggle_history_drawer(self) -> None:
        if self.width() >= 920:
            return
            
        dlg = QDialog(self)
        dlg.setWindowTitle("Session Task History")
        dlg.resize(920, 540)
        dlg.setMinimumSize(780, 400)
        
        # Apply dark theme and DWM native window styling to dialog
        dlg.show()
        self._apply_window_theme(dlg)
        
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Separate dialog table component (clean edge-to-edge, no card wrapper)
        dlg_table = self.create_history_table(is_dialog=True)
        if hasattr(self, "_history_entries"):
            for data in reversed(self._history_entries):
                self._render_history_row(dlg_table, data, 0)
            
        layout.addWidget(dlg_table)
        
        # Check button visually when dialog opens
        self.history_toggle_btn.setChecked(True)
        
        dlg.exec()
        
        self.history_toggle_btn.setChecked(False)

    # ── Interactive Edge Resizing for Frameless Window ────────
    # ── Cursor feedback for resize zones (cosmetic only — actual resizing done by WM_NCHITTEST) ──
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.isMaximized():
            px, py = event.pos().x(), event.pos().y()
            w, h = self.width(), self.height()
            m = RESIZE_MARGIN
            top = py <= m
            bottom = py >= h - m
            left = px <= m
            right = px >= w - m
            if (top and left) or (bottom and right):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (top and right) or (bottom and left):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif left or right:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif top or bottom:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)

    def page_container(self, title: str = ""):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        page.setObjectName("PageRoot")
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(12)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("SectionTitle")
            layout.addWidget(title_label)
        return scroll, layout

    # ── Page 0: Active Render Dashboard ───────────────────────
    def build_job_page(self) -> QWidget:
        page, layout = self.page_container()
        self.job_state_stack = QStackedWidget()
        self.job_state_stack.setObjectName("JobStateStack")

        # ── Standby / Idle State ──
        empty_page = QWidget()
        empty_page.setObjectName("EmptyStatePage")
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(16, 16, 16, 16)
        empty_layout.addStretch(1)
        self.job_empty = EmptyState(
            "Worker Standby — Ready for Dispatch",
            "The worker daemon is stopped. Start the worker to connect to the backend and begin processing render tasks.",
        )
        self.job_empty.setMaximumWidth(480)
        empty_row = QHBoxLayout()
        empty_row.addStretch(1)
        empty_row.addWidget(self.job_empty)
        empty_row.addStretch(1)
        empty_layout.addLayout(empty_row)
        empty_layout.addStretch(1)
        self.job_state_stack.addWidget(empty_page)

        # ── Active Rendering State ──
        self.active_page = QWidget()
        self.active_page.setObjectName("ActiveJobPage")
        self.active_page.installEventFilter(self)
        self.active_layout = QHBoxLayout(self.active_page)
        self.active_layout.setContentsMargins(0, 0, 0, 0)
        self.active_layout.setSpacing(12)

        # ── LEFT COLUMN: Session Task History (Docked or Side Sheet Drawer) ──
        self.history_container = QWidget(self.active_page)
        self.history_container.setObjectName("HistoryContainer")
        history_layout = QVBoxLayout(self.history_container)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(0)

        self.history_card = SectionCard("Session Task History", "Tasks completed in this session — double-click row to copy log")
        self.history_table = self.create_history_table()
        self.history_card.add_widget(self.history_table, stretch=1)
        history_layout.addWidget(self.history_card, stretch=1)

        self.active_layout.addWidget(self.history_container, stretch=50)

        # ── RIGHT COLUMN: Active Task Hero & Cards ──
        self.active_cards_container = QWidget()
        self.active_cards_container.setObjectName("ActiveCardsContainer")
        right_col = QVBoxLayout(self.active_cards_container)
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(12)

        # 1. Hero Progress Panel
        progress_card = QFrame()
        progress_card.setObjectName("HeroCard")
        progress_card.setStyleSheet("#HeroCard { background-color: #171A24; border: 1px solid #2A3143; border-radius: 8px; }")
        progress_card.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(16, 14, 16, 14)
        progress_layout.setSpacing(10)
        
        progress_header = QHBoxLayout()
        self.job_title_label = QLabel("Current Job")
        self.job_title_label.setObjectName("PageTitle")
        self.job_title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #FFFFFF;")
        
        self.job_status_chip = StatusChip("OFFLINE")

        self.history_toggle_btn = QPushButton("  History (0)")
        self.history_toggle_btn.setObjectName("SecondaryBtn")
        self.history_toggle_btn.setIcon(get_icon("layers", "#9C73F2", 12))
        self.history_toggle_btn.setToolTip("Toggle Session Task History drawer")
        self.history_toggle_btn.setAccessibleName("Toggle Session Task History Drawer")
        self.history_toggle_btn.setFixedHeight(28)
        self.history_toggle_btn.setCheckable(True)
        self.history_toggle_btn.clicked.connect(self.toggle_history_drawer)
        self.history_toggle_btn.setVisible(False)
        
        self.cancel_task_btn = QPushButton("  Cancel Task")
        self.cancel_task_btn.setObjectName("DestructiveTonalBtn")
        self.cancel_task_btn.setIcon(get_icon("x", "#F87171", 11))
        self.cancel_task_btn.setAccessibleName("Cancel Currently Running Task")
        self.cancel_task_btn.clicked.connect(self.cancel_current_task)
        self.cancel_task_btn.setEnabled(False)
        self.cancel_task_btn.setFixedHeight(28)
        
        progress_header.addWidget(self.job_title_label)
        progress_header.addSpacing(8)
        progress_header.addWidget(self.job_status_chip)
        progress_header.addStretch(1)
        progress_header.addWidget(self.history_toggle_btn)
        progress_header.addSpacing(6)
        progress_header.addWidget(self.cancel_task_btn)
        progress_layout.addLayout(progress_header)

        self.job_progress = QProgressBar()
        self.job_progress.setFixedHeight(10)
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(0)
        self.job_progress.setTextVisible(False)
        progress_layout.addWidget(self.job_progress)

        progress_meta = QHBoxLayout()
        self.job_phase_label = QLabel("Phase: Preparing Task")
        self.job_phase_label.setObjectName("AccentLabel")
        self.job_phase_label.setStyleSheet("font-weight: 600; color: #9C73F2; font-size: 12px;")
        
        self.job_frame_label = QLabel("Frame: — / —")
        self.job_frame_label.setStyleSheet("font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; color: #CBD5E1;")
        
        self.job_elapsed_label = QLabel("Elapsed: 00h 00m 00s")
        self.job_elapsed_label.setStyleSheet("font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; color: #CBD5E1;")
        
        self.job_eta_label = QLabel("ETA: Estimating…")
        self.job_eta_label.setStyleSheet("font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; color: #CBD5E1;")
        
        self.job_percent_label = QLabel("0%")
        self.job_percent_label.setObjectName("ProgressPercent")
        self.job_percent_label.setAlignment(Qt.AlignCenter)
        self.job_percent_label.setFixedHeight(22)
        
        progress_meta.addWidget(self.job_phase_label)
        progress_meta.addSpacing(16)
        progress_meta.addWidget(self.job_frame_label)
        progress_meta.addStretch(1)
        progress_meta.addWidget(self.job_elapsed_label)
        progress_meta.addSpacing(16)
        progress_meta.addWidget(self.job_eta_label)
        progress_meta.addSpacing(16)
        progress_meta.addWidget(self.job_percent_label)
        progress_layout.addLayout(progress_meta)

        right_col.addWidget(progress_card)

        # 2. Active Task File Locations
        paths_card = SectionCard("Active Task File Locations")
        self.scene_path_box = PathBox("Scene File")
        self.output_path_box = PathBox("Output File / Folder")
        self.log_path_box = PathBox("Task Log File")
        paths_card.add_widget(self.scene_path_box)
        paths_card.add_widget(self.output_path_box)
        paths_card.add_widget(self.log_path_box)
        right_col.addWidget(paths_card)

        # 3. Active Task Specifications
        specs_card = SectionCard("Active Task Specifications")
        self.task_info = InfoGrid(
            [
                ("job_name", "Job Name"),
                ("job_user", "Submitted By"),
                ("department", "Department"),
                ("priority", "Priority"),
                ("task_id", "Task ID"),
                ("frame_range", "Frame Range"),
                ("dcc", "Application"),
                ("dcc_version", "Version"),
                ("renderer", "Renderer"),
                ("execution_mode", "Exec Mode"),
                ("phase", "Phase"),
                ("exit_code", "Exit Code"),
            ],
            columns=2,
        )
        specs_card.add_widget(self.task_info)
        right_col.addWidget(specs_card)
        right_col.addStretch(1)

        self.active_layout.addWidget(self.active_cards_container, stretch=58)

        self.job_state_stack.addWidget(self.active_page)
        layout.addWidget(self.job_state_stack)

        return page

    # ── Page 1: System Telemetry & Specs ──────────────────────
    def build_telemetry_page(self) -> QWidget:
        page, layout = self.page_container()

        # Live Hardware Telemetry (4 Gauges)
        metrics_card = SectionCard("Live Hardware Workload")
        metrics = QGridLayout()
        metrics.setSpacing(12)
        self.cpu_meter = ResourceMeter("CPU WORKLOAD")
        self.memory_meter = ResourceMeter("SYSTEM MEMORY (RAM)")
        self.disk_meter = ResourceMeter("LOCAL DISK STORAGE")
        self.gpu_meter = ResourceMeter("GPU & VRAM METRICS")
        metrics.addWidget(self.cpu_meter, 0, 0)
        metrics.addWidget(self.memory_meter, 0, 1)
        metrics.addWidget(self.disk_meter, 1, 0)
        metrics.addWidget(self.gpu_meter, 1, 1)
        metrics_card.add_layout(metrics)
        layout.addWidget(metrics_card)

        # Node Identity & Machine Specs
        details_row = QHBoxLayout()
        details_row.setSpacing(12)

        schedule_card = SectionCard("Worker Node Identity")
        self.worker_schedule_info = InfoGrid(
            [
                ("worker_status", "Worker Status"),
                ("scheduler_status", "Scheduler"),
                ("backend", "Backend"),
                ("running_time", "Running Time"),
                ("after_task", "After Task"),
                ("pools", "Assigned Pools"),
                ("completed", "Completed"),
                ("failed", "Failed"),
            ],
            columns=2,
        )
        schedule_card.add_widget(self.worker_schedule_info)
        details_row.addWidget(schedule_card, 1)

        specs_card = SectionCard("Hardware Specifications")
        self.worker_specs_info = InfoGrid(
            [
                ("os", "Operating System"),
                ("user", "User"),
                ("cpu", "CPU"),
                ("memory", "Memory"),
                ("gpu", "GPU"),
                ("ip", "IP Address"),
                ("disk", "Free Disk"),
                ("last_ping", "Last Ping"),
            ],
            columns=2,
        )
        specs_card.add_widget(self.worker_specs_info)
        details_row.addWidget(specs_card, 1)
        layout.addLayout(details_row)

        # Detected DCC Applications Table
        dcc_card = SectionCard("Detected DCC Applications")
        self.dcc_table = self.create_dcc_table()
        self.dcc_table.setMinimumHeight(130)
        dcc_card.add_widget(self.dcc_table)
        dcc_btn_row = QHBoxLayout()
        dcc_btn_row.addStretch()
        refresh_dcc_btn = QPushButton("  Refresh Detection")
        refresh_dcc_btn.setObjectName("SecondaryBtn")
        refresh_dcc_btn.setIcon(get_icon("refresh", "#FFFFFF", 12))
        refresh_dcc_btn.setAccessibleName("Refresh DCC Detection")
        refresh_dcc_btn.clicked.connect(self.refresh_dcc_tables)
        dcc_btn_row.addWidget(refresh_dcc_btn)
        dcc_card.add_layout(dcc_btn_row)
        layout.addWidget(dcc_card)
        layout.addStretch()

        return page

    # ── Page 2: Live Terminal Console ─────────────────────────

    # ── Page 4: Integrations ──────────────────────────────────────
    def build_plugins_page(self) -> QWidget:
        page, layout = self.page_container()

        horiz_layout = QHBoxLayout()
        horiz_layout.setSpacing(12)
        layout.addLayout(horiz_layout)

        for dcc_key, dcc_label, install_path_fn, icon_name in [
            ("maya",    "Maya",    self._maya_install_path, "maya"),
            ("houdini", "Houdini", self._houdini_install_path, "houdini"),
        ]:
            card = SectionCard(f"{dcc_label}", f"RenderHive submitter for {dcc_label}", icon_name=icon_name)
            card.setMinimumWidth(380)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            # Structured Info Alert Banner
            alert_frame = QFrame()
            alert_frame.setObjectName("InfoAlert")
            alert_layout = QHBoxLayout(alert_frame)
            alert_layout.setContentsMargins(14, 12, 14, 12)
            alert_layout.setSpacing(12)
            
            alert_text_layout = QVBoxLayout()
            alert_text_layout.setContentsMargins(0, 0, 0, 0)
            alert_text_layout.setSpacing(3)
            
            title_lbl = QLabel("—")
            title_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
            self._plugin_alert_titles[dcc_key] = title_lbl
            alert_text_layout.addWidget(title_lbl)
            
            desc_lbl = QLabel("—")
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("font-size: 12px;")
            self._plugin_alert_descs[dcc_key] = desc_lbl
            alert_text_layout.addWidget(desc_lbl)
            
            alert_layout.addLayout(alert_text_layout, 1)
            
            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._plugin_alert_icons[dcc_key] = icon_lbl
            alert_layout.addWidget(icon_lbl)
            
            self._plugin_alert_frames[dcc_key] = alert_frame
            card.add_widget(alert_frame)

            # DCC Exe Path config
            path_form = QVBoxLayout()
            path_form.setSpacing(4)
            lbl = QLabel(f"{dcc_label} Directory")
            lbl.setObjectName("FieldLabel")
            path_form.addWidget(lbl)
            
            path_row = QHBoxLayout()
            path_input = QLineEdit()
            
            detected = self.discovered.get(dcc_key)
            if detected and len(detected) > 0:
                path_input.setPlaceholderText(f"Auto-detected: {detected[0].root}")
            else:
                path_input.setPlaceholderText(f"Could not auto-detect {dcc_label} path...")
                
            path_input.setText(self.settings.value(f"{dcc_key}_custom_path", ""))
            
            browse_btn = QPushButton(" Browse")
            browse_btn.setObjectName("SecondaryBtn")
            browse_btn.setIcon(get_icon("folder", "#CBD5E1", 12))
            
            browse_btn.clicked.connect(lambda _=False, k=dcc_key, inp=path_input: self._browse_dcc_path(k, inp))
            path_input.textChanged.connect(lambda text, k=dcc_key: self._save_dcc_path(k, text))
            
            self._dcc_path_inputs[dcc_key] = path_input
            path_row.addWidget(path_input, 1)
            path_row.addWidget(browse_btn)
            path_form.addLayout(path_row)
            
            path_form.setContentsMargins(0, 8, 0, 8)
            card.add_layout(path_form)

            # Button row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            btn_row.addStretch()

            open_btn = QPushButton("  Open Folder")
            open_btn.setObjectName("SecondaryBtn")
            open_btn.setIcon(get_icon("folder", "#FFFFFF", 12))
            open_btn.setAccessibleName(f"Open {dcc_label} Plugin Folder")
            _path_fn = install_path_fn
            open_btn.clicked.connect(lambda _=False, fn=_path_fn: self._open_plugin_folder(fn()))
            btn_row.addWidget(open_btn)

            install_btn = QPushButton("  Install / Update")
            install_btn.setIcon(get_icon("download", "#080A0F", 12))
            install_btn.setAccessibleName(f"Install or Update {dcc_label} Plugin")
            install_btn.clicked.connect(lambda _=False, k=dcc_key: self._run_plugin_install(k))
            self._plugin_install_btns[dcc_key] = install_btn
            btn_row.addWidget(install_btn)

            uninstall_btn = QPushButton("  Uninstall")
            uninstall_btn.setIcon(get_icon("trash", "#F87171", 12))
            uninstall_btn.setAccessibleName(f"Uninstall {dcc_label} Plugin")
            uninstall_btn.setStyleSheet("QPushButton { color: #F87171; background: transparent; border: 1px solid #451a20; } QPushButton:hover { background: #451a20; }")
            uninstall_btn.clicked.connect(lambda _=False, k=dcc_key: self._run_plugin_uninstall(k))
            self._plugin_uninstall_btns[dcc_key] = uninstall_btn
            btn_row.addWidget(uninstall_btn)

            card.add_layout(btn_row)
            horiz_layout.addWidget(card)

        layout.addStretch(1)

        return page

    def _browse_dcc_path(self, dcc_key: str, input_widget: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select DCC Installation Directory")
        if folder:
            input_widget.setText(folder)

    def _save_dcc_path(self, dcc_key: str, text: str) -> None:
        self.settings.setValue(f"{dcc_key}_custom_path", text)

    def _maya_install_path(self) -> Optional[Path]:
        """Return the expected Maya plugin install directory."""
        if os.name == "nt":
            base = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "maya" / "scripts"
        else:
            base = Path.home() / "maya" / "scripts"
        return base / "RenderHive"

    def _houdini_install_path(self) -> Optional[Path]:
        """Return the first detected Houdini runtime install directory, if any."""
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        runtime_parent = local / "RenderHive" / "Houdini"
        if runtime_parent.is_dir():
            # Return first version sub-folder that exists
            for child in sorted(runtime_parent.iterdir()):
                if child.is_dir():
                    return child
        return runtime_parent  # not yet installed; return parent for display

    def _refresh_plugin_status(self) -> None:
        """Update the status chip and path label for each DCC plugin."""
        import json as _json
        
        for dcc_key, path_fn in [
            ("maya",    self._maya_install_path),
            ("houdini", self._houdini_install_path),
        ]:
            path = path_fn()
            title_lbl = self._plugin_alert_titles.get(dcc_key)
            desc_lbl  = self._plugin_alert_descs.get(dcc_key)
            icon_lbl  = self._plugin_alert_icons.get(dcc_key)
            frame     = self._plugin_alert_frames.get(dcc_key)
            
            is_installed = False
            version = ""
            
            if dcc_key == "maya":
                if path and path.is_dir():
                    info_file = path / "renderhive_install_info.json"
                    if info_file.is_file():
                        try:
                            data = _json.loads(info_file.read_text(encoding="utf-8"))
                            version = data.get("plugin_version") or data.get("installed_version") or ""
                            is_installed = True
                        except Exception:
                            pass
            elif dcc_key == "houdini":
                # Houdini writes to ~/Documents/houdiniX.Y/packages/renderhive.json
                docs = Path.home() / "Documents"
                if docs.is_dir():
                    for item in docs.glob("houdini*.*"):
                        if item.is_dir():
                            pkg = item / "packages" / "renderhive.json"
                            if pkg.is_file():
                                try:
                                    data = _json.loads(pkg.read_text(encoding="utf-8"))
                                    # the package points to the runtime root
                                    for env in data.get("env", []):
                                        if "RENDERHIVE_HOUDINI_ROOT" in env:
                                            root_str = env["RENDERHIVE_HOUDINI_ROOT"]
                                            if Path(root_str).is_dir():
                                                is_installed = True
                                                version = Path(root_str).name # the folder is the version
                                            break
                                except Exception:
                                    pass
                        if is_installed:
                            break

            dcc_name = "Maya" if dcc_key == "maya" else "Houdini"
            if is_installed:
                if title_lbl:
                    title_lbl.setText(f"Plugin Installed{' (v' + version + ')' if version else ''}")
                    title_lbl.setStyleSheet("color: #4ADE80; font-weight: 600; font-size: 13px;")
                if desc_lbl:
                    display_path = str(path).replace('\\', '\\\u200B')
                    desc_lbl.setText(display_path)
                    desc_lbl.setStyleSheet("color: #86EFAC; font-size: 12px;")
                if icon_lbl:
                    icon_lbl.setPixmap(get_icon("check", "#4ADE80", 20).pixmap(20, 20))
                if frame:
                    frame.setStyleSheet("QFrame#InfoAlert { background: rgba(74, 222, 128, 0.09); border: 1px solid rgba(74, 222, 128, 0.32); border-radius: 6px; }")
            else:
                if title_lbl:
                    title_lbl.setText("Plugin Not Installed")
                    title_lbl.setStyleSheet("color: #F1F5F9; font-weight: 600; font-size: 13px;")
                if desc_lbl:
                    desc_lbl.setText(f"Click Install below to enable direct scene submission from {dcc_name}.")
                    desc_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
                if icon_lbl:
                    icon_lbl.setPixmap(get_icon("help-circle", "#64748B", 20).pixmap(20, 20))
                if frame:
                    frame.setStyleSheet("QFrame#InfoAlert { background: #13161F; border: 1px solid #242936; border-radius: 6px; }")

    def _open_plugin_folder(self, path) -> None:
        if path is None:
            return
        path = Path(path)
        target = path if path.is_dir() else path.parent
        # Walk up to the first existing parent
        while not target.exists():
            parent = target.parent
            if parent == target:
                break
            target = parent
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _run_plugin_install(self, dcc_key: str) -> None:
        if dcc_key in self._plugin_workers and self._plugin_workers[dcc_key].isRunning():
            return  # already in progress

        btn = self._plugin_install_btns.get(dcc_key)
        if btn:
            btn.setEnabled(False)

        worker = PluginInstallWorker(dcc_key, "", parent=self)
        worker.progress.connect(lambda key, line: self.log(f"[{key.upper()} Install] {line}"))
        worker.finished.connect(self._on_plugin_install_finished)
        self._plugin_workers[dcc_key] = worker
        worker.start()

    def _run_plugin_uninstall(self, dcc_key: str) -> None:
        if dcc_key in self._plugin_workers and self._plugin_workers[dcc_key].isRunning():
            return
            
        dcc_label = "Maya" if dcc_key == "maya" else "Houdini"
        
        reply = QMessageBox.question(
            self,
            f"Uninstall {dcc_label} Plugin",
            f"Are you sure you want to uninstall the RenderHive plugin for {dcc_label}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        btn = self._plugin_install_btns.get(dcc_key)
        un_btn = self._plugin_uninstall_btns.get(dcc_key)
        
        if btn:
            btn.setEnabled(False)
        if un_btn:
            un_btn.setEnabled(False)

        worker = PluginUninstallWorker(dcc_key, parent=self)
        worker.progress.connect(lambda key, line: self.log(f"[{key.upper()} Uninstall] {line}"))
        worker.finished.connect(self._on_plugin_install_finished) # Reuse the same finish handler
        self._plugin_workers[dcc_key] = worker
        worker.start()

    def _on_plugin_install_finished(self, dcc_key: str, success: bool, message: str) -> None:
        btn = self._plugin_install_btns.get(dcc_key)
        un_btn = self._plugin_uninstall_btns.get(dcc_key)
        if btn:
            btn.setEnabled(True)
        if un_btn:
            un_btn.setEnabled(True)
        label = "Maya" if dcc_key == "maya" else "Houdini"
        if success:
            self.log(f"[{label} Install/Uninstall] ✓ {message}")
        else:
            self.log(f"[{label} Install/Uninstall] ✗ {message}")
        self._refresh_plugin_status()


    def build_terminal_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Terminal Toolbar
        log_tools = QHBoxLayout()
        log_tools.setSpacing(8)
        self.log_search_input = QLineEdit()
        self.log_search_input.setObjectName("LogFilterInput")
        self.log_search_input.setFixedHeight(32)
        self.log_search_input.setPlaceholderText("Filter logs (regex or text)...")
        self.log_search_input.setAccessibleName("Log Filter Input")
        self.log_search_input.returnPressed.connect(self.find_in_log)
        log_tools.addWidget(self.log_search_input, 1)

        self.scroll_lock_btn = QPushButton("  Auto-Scroll: ON")
        self.scroll_lock_btn.setObjectName("SecondaryBtn")
        self.scroll_lock_btn.setIcon(get_icon("lock", "#FFFFFF", 12))
        self.scroll_lock_btn.setCheckable(True)
        self.scroll_lock_btn.setChecked(True)
        self.scroll_lock_btn.setAccessibleName("Toggle Log Auto-Scroll")
        self.scroll_lock_btn.clicked.connect(self.toggle_auto_scroll)
        log_tools.addWidget(self.scroll_lock_btn)

        copy_btn = QPushButton("  Copy")
        copy_btn.setObjectName("SecondaryBtn")
        copy_btn.setIcon(get_icon("copy", "#FFFFFF", 12))
        copy_btn.setAccessibleName("Copy Terminal Log")
        copy_btn.clicked.connect(self.copy_log_view)
        log_tools.addWidget(copy_btn)

        clear_btn = QPushButton("  Clear")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.setIcon(get_icon("trash", "#FFFFFF", 12))
        clear_btn.setAccessibleName("Clear Terminal Console")
        clear_btn.clicked.connect(self.clear_log_view)
        log_tools.addWidget(clear_btn)

        open_btn = QPushButton("  Open Folder")
        open_btn.setObjectName("SecondaryBtn")
        open_btn.setIcon(get_icon("folder", "#FFFFFF", 12))
        open_btn.setAccessibleName("Open Log Files Folder")
        open_btn.clicked.connect(self.open_log_folder)
        log_tools.addWidget(open_btn)
        layout.addLayout(log_tools)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(10000)
        self.log_console.setAccessibleName("Terminal Output Log View")
        layout.addWidget(self.log_console, 1)

        return page

    def create_dcc_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Application", "Version", "Executables", "Install Root"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_dcc_context_menu)
        table.cellDoubleClicked.connect(self._on_dcc_row_double_clicked)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        return table

    def create_history_table(self, is_dialog: bool = False) -> QTableWidget:
        table = QTableWidget(0, 6)
        headers = ["Job Name", "Application", "Frames", "Duration", "Status", "Finished"]
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        if is_dialog:
            table.setObjectName("DialogHistoryTable")
            table.setStyleSheet("QTableWidget { background-color: #080A0E; border: none; border-radius: 0px; }")
        else:
            table.setObjectName("HistoryTable")

        table.customContextMenuRequested.connect(lambda pos, t=table: self._show_history_context_menu(pos, t))
        table.cellDoubleClicked.connect(lambda r, c, t=table: self._on_history_row_double_clicked(r, c, t))

        # Explicit header text alignments
        if table.horizontalHeaderItem(0):
            table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if table.horizontalHeaderItem(1):
            table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if table.horizontalHeaderItem(2):
            table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if table.horizontalHeaderItem(3):
            table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if table.horizontalHeaderItem(4):
            table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if table.horizontalHeaderItem(5):
            table.horizontalHeaderItem(5).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setMinimumHeight(150)
        return table

    def _render_history_row(self, table: QTableWidget, data: Dict[str, Any], row: int = 0) -> None:
        table.insertRow(row)

        finish_time = safe_text(data.get("finish_time")) or time.strftime("%H:%M:%S")
        data["finish_time"] = finish_time
        job_display = safe_text(data.get("job_name") or data.get("job_id") or data.get("task_id"), "—")
        dcc = "{} {}".format(safe_text(data.get("dcc"), ""), safe_text(data.get("renderer"), "")).strip() or "—"
        frames = safe_text(data.get("frame_range"), "—")
        duration = format_duration(data.get("duration_seconds") or 0)
        status = safe_text(data.get("status"), "FAILED").upper()

        job_item = QTableWidgetItem(job_display)
        job_item.setData(Qt.ItemDataRole.UserRole, dict(data))
        job_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        dcc_item = QTableWidgetItem(dcc)
        dcc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        frames_item = QTableWidgetItem(frames)
        frames_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        duration_item = QTableWidgetItem(duration)
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        status_item = QTableWidgetItem("● " + status.title())
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        time_item = QTableWidgetItem(finish_time)
        time_item.setData(Qt.ItemDataRole.UserRole, dict(data))
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if status == "SUCCEEDED":
            status_item.setForeground(QColor("#4ADE80"))
        else:
            status_item.setForeground(QColor("#F87171"))

        log_path = safe_text(data.get("log_path"))
        output_path = safe_text(data.get("output_path"))
        tooltip = "Job: {}\nTask ID: {}\nStatus: {}\nDuration: {}\nScene: {}\nOutput: {}\nLog: {}\n\nRight-click for actions • Double-click to open log".format(
            job_display,
            safe_text(data.get("task_id")),
            status,
            duration,
            safe_text(data.get("scene_path")),
            output_path,
            log_path,
        )
        for item in (job_item, dcc_item, frames_item, duration_item, status_item, time_item):
            item.setToolTip(tooltip)

        table.setItem(row, 0, job_item)
        table.setItem(row, 1, dcc_item)
        table.setItem(row, 2, frames_item)
        table.setItem(row, 3, duration_item)
        table.setItem(row, 4, status_item)
        table.setItem(row, 5, time_item)

    def add_history_entry(self, data: Dict[str, Any]) -> None:
        if not hasattr(self, "_history_entries"):
            self._history_entries = []
        self._history_entries.insert(0, dict(data))

        if hasattr(self, "history_table"):
            self._render_history_row(self.history_table, data, 0)
            if hasattr(self, "history_toggle_btn"):
                self.history_toggle_btn.setText("  History ({})".format(self.history_table.rowCount()))

    def _show_history_context_menu(self, pos: QPoint, source_table: Optional[QTableWidget] = None) -> None:
        table = source_table or getattr(self, "history_table", None)
        if not table:
            return
        row = table.rowAt(pos.y())
        if row < 0:
            return
        item = table.item(row, 0) or table.item(row, 1)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole) or {}

        status = safe_text(data.get("status"), "UNKNOWN").upper()
        log_path = safe_text(data.get("log_path"))
        output_path = safe_text(data.get("output_path"))
        scene_path = safe_text(data.get("scene_path"))
        task_id = safe_text(data.get("task_id"))
        job_name = safe_text(data.get("job_name"))

        menu = QMenu(self)

        # ── Primary Actions (Enabled/Disabled based on Task State & File Presence) ──
        has_log_file = bool(log_path and log_path != "—" and os.path.exists(log_path))
        act_open_log = menu.addAction(get_icon("terminal", "#CBD5E1", 13), "Open Task Log File")
        act_open_log.setEnabled(has_log_file)
        if has_log_file:
            act_open_log.triggered.connect(lambda: self._open_path(log_path))

        has_output = bool(output_path and output_path != "—" and (os.path.exists(output_path) or os.path.exists(os.path.dirname(output_path))))
        act_open_output = menu.addAction(get_icon("folder", "#CBD5E1", 13), "Reveal Output in File Explorer")
        act_open_output.setEnabled(has_output and status == "SUCCEEDED")
        if has_output:
            act_open_output.triggered.connect(lambda: self._reveal_in_explorer(output_path))

        has_scene = bool(scene_path and scene_path != "—" and os.path.exists(scene_path))
        act_open_scene = menu.addAction(get_icon("film", "#CBD5E1", 13), "Reveal Scene in File Explorer")
        act_open_scene.setEnabled(has_scene)
        if has_scene:
            act_open_scene.triggered.connect(lambda: self._reveal_in_explorer(scene_path))

        menu.addSeparator()

        # ── Copy Actions ──
        act_copy_log = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Task Log Path")
        act_copy_log.setEnabled(bool(log_path and log_path != "—"))
        if log_path:
            act_copy_log.triggered.connect(lambda: self._copy_to_clipboard(log_path, "Log path"))

        act_copy_output = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Output Path")
        act_copy_output.setEnabled(bool(output_path and output_path != "—"))
        if output_path:
            act_copy_output.triggered.connect(lambda: self._copy_to_clipboard(output_path, "Output path"))

        act_copy_scene = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Scene Path")
        act_copy_scene.setEnabled(bool(scene_path and scene_path != "—"))
        if scene_path:
            act_copy_scene.triggered.connect(lambda: self._copy_to_clipboard(scene_path, "Scene path"))

        act_copy_id = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Task ID")
        act_copy_id.setEnabled(bool(task_id and task_id != "—"))
        if task_id:
            act_copy_id.triggered.connect(lambda: self._copy_to_clipboard(task_id, "Task ID"))

        act_copy_job = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Job Name")
        act_copy_job.setEnabled(bool(job_name and job_name != "—"))
        if job_name:
            act_copy_job.triggered.connect(lambda: self._copy_to_clipboard(job_name, "Job name"))

        menu.exec(table.viewport().mapToGlobal(pos))

    def _show_dcc_context_menu(self, pos: QPoint) -> None:
        if not hasattr(self, "dcc_table"):
            return
        row = self.dcc_table.rowAt(pos.y())
        if row < 0:
            return
        app_name = self.dcc_table.item(row, 0).text() if self.dcc_table.item(row, 0) else "DCC"
        version = self.dcc_table.item(row, 1).text() if self.dcc_table.item(row, 1) else ""
        execs = self.dcc_table.item(row, 2).text() if self.dcc_table.item(row, 2) else ""
        root = self.dcc_table.item(row, 3).text() if self.dcc_table.item(row, 3) else ""

        menu = QMenu(self)

        has_root = bool(root and root != "—" and os.path.exists(root))
        act_open_root = menu.addAction(get_icon("folder", "#CBD5E1", 13), "Open {} Installation Folder".format(app_name))
        act_open_root.setEnabled(has_root)
        if has_root:
            act_open_root.triggered.connect(lambda: self._open_path(root))

        menu.addSeparator()

        act_copy_root = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Installation Path")
        act_copy_root.setEnabled(bool(root and root != "—"))
        if root:
            act_copy_root.triggered.connect(lambda: self._copy_to_clipboard(root, "Install path"))

        act_copy_execs = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Executables")
        act_copy_execs.setEnabled(bool(execs and execs != "Unavailable"))
        if execs:
            act_copy_execs.triggered.connect(lambda: self._copy_to_clipboard(execs, "Executables"))

        act_copy_version = menu.addAction(get_icon("copy", "#CBD5E1", 12), "Copy Version ({})".format(version))
        act_copy_version.setEnabled(bool(version and version != "—"))
        if version:
            act_copy_version.triggered.connect(lambda: self._copy_to_clipboard(version, "Version"))

        menu.exec(self.dcc_table.viewport().mapToGlobal(pos))

    def _on_dcc_row_double_clicked(self, row: int, col: int) -> None:
        if not hasattr(self, "dcc_table"):
            return
        root_item = self.dcc_table.item(row, 3)
        if root_item and root_item.text() and os.path.exists(root_item.text()):
            self._open_path(root_item.text())
        elif root_item and root_item.text() and root_item.text() != "—":
            self._copy_to_clipboard(root_item.text(), "Install path")

    def _on_history_row_double_clicked(self, row: int, col: int, source_table: Optional[QTableWidget] = None) -> None:
        table = source_table or getattr(self, "history_table", None)
        if not table:
            return
        item = table.item(row, 0) or table.item(row, 1)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole) or {}
        log_path = safe_text(data.get("log_path"))
        if log_path and os.path.exists(log_path):
            self._open_path(log_path)
        elif log_path and log_path != "—":
            self._copy_to_clipboard(log_path, "Log path")

    def _open_path(self, target_path: str) -> None:
        if not target_path:
            return
        clean = os.path.normpath(target_path)
        try:
            if os.name == "nt":
                os.startfile(clean)
            else:
                subprocess.Popen(["xdg-open", clean])
            self.log("Opened path: {}".format(clean))
        except Exception as exc:
            self.log("Failed to open path {}: {}".format(clean, exc))

    def _reveal_in_explorer(self, target_path: str) -> None:
        if not target_path:
            return
        clean = os.path.normpath(target_path)
        try:
            if os.name == "nt":
                if os.path.isfile(clean):
                    subprocess.Popen(["explorer", "/select,", clean])
                elif os.path.isdir(clean):
                    subprocess.Popen(["explorer", clean])
                elif os.path.exists(os.path.dirname(clean)):
                    subprocess.Popen(["explorer", os.path.dirname(clean)])
            else:
                target_dir = clean if os.path.isdir(clean) else os.path.dirname(clean)
                subprocess.Popen(["xdg-open", target_dir])
            self.log("Revealed in explorer: {}".format(clean))
        except Exception as exc:
            self.log("Failed to reveal path {}: {}".format(clean, exc))

    def _copy_to_clipboard(self, text: str, label: str = "Value") -> None:
        if text and text != "—":
            QApplication.clipboard().setText(str(text).strip())
            self.log("Copied {} to clipboard: {}".format(label, text))

    def _update_empty_state_metadata(self) -> None:
        if hasattr(self, "job_empty"):
            dcc_parts = []
            maya_v = [i.version for i in self.discovered.get("maya") or []]
            if maya_v:
                dcc_parts.append("Maya {}".format(", ".join(maya_v)))
            houdini_v = [i.version for i in self.discovered.get("houdini") or []]
            if houdini_v:
                dcc_parts.append("Houdini {}".format(", ".join(houdini_v)))
            dcc_text = " • ".join(dcc_parts) if dcc_parts else "No DCCs detected"
            api_url = str(self.settings.value("api_url", "") or "").strip()
            self.job_empty.set_metadata(
                hostname=HOSTNAME,
                dccs=dcc_text,
                endpoint=api_url or "Coordinator Offline",
            )

    def discover_dccs(self) -> Dict[str, List[DCCInstallation]]:
        maya_raw = str(self.settings.value("maya_custom_path", "") or "").strip()
        houdini_raw = str(self.settings.value("houdini_custom_path", "") or "").strip()
        maya_roots = [p.strip() for p in maya_raw.replace(";", ",").split(",") if p.strip()]
        houdini_roots = [p.strip() for p in houdini_raw.replace(";", ",").split(",") if p.strip()]
        return discover_all(extra_maya_roots=maya_roots, extra_houdini_roots=houdini_roots)

    def refresh_dcc_tables(self) -> None:
        self.discovered = self.discover_dccs()
        summary = self.short_dcc_summary().replace("\n", "  •  ")
        detail = format_installations_summary(self.discovered)
        if hasattr(self, "header_dcc_label"):
            self.header_dcc_label.setText(summary)
            self.header_dcc_label.setToolTip(detail)
        if hasattr(self, "dcc_table"):
            rows = _installation_rows(self.discovered)
            self.dcc_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.dcc_table.setItem(row_index, column_index, item)
        self._update_empty_state_metadata()

    def short_dcc_summary(self) -> str:
        maya_versions = [item.version for item in self.discovered.get("maya") or []]
        houdini_versions = [item.version for item in self.discovered.get("houdini") or []]
        lines = []
        lines.append("Maya {}".format(", ".join(maya_versions)) if maya_versions else "Maya unavailable")
        lines.append("Houdini {}".format(", ".join(houdini_versions)) if houdini_versions else "Houdini unavailable")
        return "\n".join(lines)

    def worker_profile(self) -> Dict[str, Any]:
        return {
            "description": self.settings.value("description", ""),
            "comment": self.settings.value("comment", ""),
            "region": self.settings.value("region", "Default"),
            "custom_tags": self.settings.value("custom_tags", ""),
            "pool_names": self.settings.value("custom_pools", ""),
            "poll_interval": int(self.settings.value("poll_interval", 5) or 5),
            "after_task": self.settings.value("after_task", "continue"),
            "start_paused": False,
        }

    @Slot(str)
    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        text = str(message or "")
        lines = text.splitlines() or [""]
        for line in lines:
            formatted_line = "[{}] {}".format(timestamp, line)
            cursor = self.log_console.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)

            # Color-code errors / warnings / success / dispatch with high contrast
            char_format = QTextCharFormat()
            lowered = line.lower()
            if "error" in lowered or "fail" in lowered or "fatal" in lowered:
                char_format.setForeground(QColor("#F87171"))
            elif "warning" in lowered or "retry" in lowered:
                char_format.setForeground(QColor("#FBBF24"))
            elif "success" in lowered or "completed" in lowered:
                char_format.setForeground(QColor("#4ADE80"))
            elif "executing" in lowered or "received task" in lowered:
                char_format.setForeground(QColor("#C084FC"))
            else:
                char_format.setForeground(QColor("#E2E8F0"))

            cursor.insertText(formatted_line + "\n", char_format)
            
            if hasattr(self, "dashboard_log"):
                dash_cursor = self.dashboard_log.textCursor()
                dash_cursor.movePosition(QTextCursor.MoveOperation.End)
                dash_cursor.insertText(formatted_line + "\n", char_format)

        if not self.auto_scroll_locked:
            cursor = self.log_console.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_console.setTextCursor(cursor)
            
            if hasattr(self, "dashboard_log"):
                dash_cursor = self.dashboard_log.textCursor()
                dash_cursor.movePosition(QTextCursor.MoveOperation.End)
                self.dashboard_log.setTextCursor(dash_cursor)

        if hasattr(self, "log_preview_label"):
            latest = lines[-1].strip() or "Ready"
            self.log_preview_label.setText(latest)
            self.log_preview_label.setToolTip(text)

    def toggle_auto_scroll(self, checked: bool) -> None:
        self.auto_scroll_locked = not checked
        self.scroll_lock_btn.setText("Auto-Scroll: ON" if checked else "Auto-Scroll: OFF")
        self.scroll_lock_btn.setIcon(get_icon("lock" if checked else "unlock", "#FFFFFF", 12))

    def _update_unified_status(self) -> None:
        """Combine daemon execution, backend connectivity, and task activity into one smart status badge."""
        is_running = self.worker_thread is not None and self.worker_thread.isRunning()
        if not is_running:
            self.status_chip.set_status("OFFLINE", custom_text="○ Offline")
            self.status_chip.setToolTip("Worker daemon is stopped")
            self.worker_schedule_info.set_value("worker_status", "Offline")
            self.worker_schedule_info.set_value("backend", "No")
            if hasattr(self, "dash_node_info"):
                self.dash_node_info.set_value("worker_status", "Offline")
                self.dash_node_info.set_value("backend", "No")
            if hasattr(self, "job_empty"):
                self.job_empty.set_content(
                    "Worker Standby — Ready for Dispatch",
                    "The worker daemon is stopped. Start the worker to connect to the backend and begin processing render tasks.",
                    status_mode="OFFLINE",
                )
            return

        if not self.backend_connected:
            self.status_chip.set_status("DISCONNECTED", custom_text="● Disconnected")
            self.status_chip.setToolTip("Worker is active but cannot connect to backend API")
            self.worker_schedule_info.set_value("worker_status", "Connecting…")
            self.worker_schedule_info.set_value("backend", "No")
            if hasattr(self, "dash_node_info"):
                self.dash_node_info.set_value("worker_status", "Connecting…")
                self.dash_node_info.set_value("backend", "No")
            if hasattr(self, "job_empty"):
                self.job_empty.set_content(
                    "Connecting to Backend…",
                    "Attempting to authenticate and register with the backend. Please ensure the server is reachable.",
                    status_mode="OFFLINE",
                )
        elif self.worker_status == "RENDERING" or self.current_task_started > 0:
            self.status_chip.set_status("RENDERING", custom_text="● Rendering")
            self.status_chip.setToolTip("Worker is actively executing a render task")
            self.worker_schedule_info.set_value("worker_status", "Rendering")
            self.worker_schedule_info.set_value("backend", "Connected")
            if hasattr(self, "dash_node_info"):
                self.dash_node_info.set_value("worker_status", "Rendering")
                self.dash_node_info.set_value("backend", "Connected")
        elif self.scheduler_status == "PAUSED":
            self.status_chip.set_status("PAUSED", custom_text="● Paused")
            self.status_chip.setToolTip("Worker is online but task dispatch is paused")
            self.worker_schedule_info.set_value("worker_status", "Paused")
            self.worker_schedule_info.set_value("backend", "Connected")
            if hasattr(self, "dash_node_info"):
                self.dash_node_info.set_value("worker_status", "Paused")
                self.dash_node_info.set_value("backend", "Connected")
            if hasattr(self, "job_empty"):
                self.job_empty.set_content(
                    "Dispatch Paused",
                    "The worker daemon is online, but task dispatch is currently suspended.",
                    status_mode="PAUSED",
                )
        elif self.worker_status == "ERROR":
            self.status_chip.set_status("ERROR", custom_text="● Error")
            self.status_chip.setToolTip("Worker encountered an error")
            self.worker_schedule_info.set_value("worker_status", "Error")
            self.worker_schedule_info.set_value("backend", "Connected")
            if hasattr(self, "dash_node_info"):
                self.dash_node_info.set_value("worker_status", "Error")
                self.dash_node_info.set_value("backend", "Connected")
            if hasattr(self, "job_empty"):
                self.job_empty.set_content(
                    "Worker Error",
                    "An error occurred while connecting or executing. Please check the Output Log for details.",
                    status_mode="ERROR",
                )
        else:
            self.status_chip.set_status("ONLINE", custom_text="● Ready")
            self.status_chip.setToolTip("Connected to backend and waiting for dispatch tasks")
            self.worker_schedule_info.set_value("worker_status", "Ready")
            self.worker_schedule_info.set_value("backend", "Connected")
            if hasattr(self, "dash_node_info"):
                self.dash_node_info.set_value("worker_status", "Ready")
                self.dash_node_info.set_value("backend", "Connected")
            if hasattr(self, "job_empty"):
                self.job_empty.set_content(
                    "Worker Online — Polling Job Queue",
                    "Connected to the RenderHive backend. Actively polling for compatible Maya and Houdini tasks.",
                    status_mode="ONLINE",
                )

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.worker_status = str(status or "OFFLINE").upper()
        self._update_unified_status()

    @Slot(str)
    def update_scheduler(self, status: str) -> None:
        self.scheduler_status = str(status or "STOPPED").upper()
        self.worker_schedule_info.set_value("scheduler_status", self.scheduler_status.title())
        if hasattr(self, "dash_node_info"):
            self.dash_node_info.set_value("scheduler_status", self.scheduler_status.title())
        self.pause_dispatch_btn.setText("")
        self.pause_dispatch_btn.setToolTip("Resume Dispatch" if self.scheduler_status == "PAUSED" else "Pause Dispatch")
        icon_color = "#FFFFFF" if (self.worker_thread and self.worker_thread.isRunning()) else "#475569"
        self.pause_dispatch_btn.setIcon(get_icon("play" if self.scheduler_status == "PAUSED" else "pause", icon_color, 13))
        self._update_unified_status()

    def update_connection(self, connected: bool) -> None:
        self.backend_connected = bool(connected)
        self._update_unified_status()

    @Slot(object)
    def update_system_info(self, info: object) -> None:
        self.last_system_info = safe_dict(info)
        self.apply_system_info(self.last_system_info)

    @Slot(object)
    def update_server_worker(self, worker: object) -> None:
        self.server_worker = safe_dict(worker)
        pools = pool_names_from_worker(self.server_worker)
        self.worker_schedule_info.set_value("pools", ", ".join(pools) if pools else "Unassigned")
        if hasattr(self, "dash_node_info"):
            self.dash_node_info.set_value("pools", ", ".join(pools) if pools else "Unassigned")
        self.worker_specs_info.set_value("last_ping", format_timestamp(self.server_worker.get("last_ping")))
        tags = self.server_worker.get("tags")
        self.worker_schedule_info.set_value("groups", ", ".join(tags or []) if tags else "—")

    @Slot(object)
    def on_task_started(self, payload: object) -> None:
        self.current_task = safe_dict(payload)
        self.current_task_started = time.monotonic()
        initial_target = max(1, min(100, int(self.current_task.get("progress") or 1)))
        self.current_progress_percent = 1
        self.current_progress_target = initial_target
        self.progress_animator.reset(1.0)
        self.progress_animator.set_target(initial_target)
        self.current_progress_phase = safe_text(self.current_task.get("phase"), "Preparing Task")
        self.current_progress_frame = self.current_task.get("current_frame")
        self.current_progress_total_frames = max(1, int(self.current_task.get("total_frames") or 1))
        self.current_progress_eta_seconds = None
        self.job_state_stack.setCurrentIndex(1)
        self.job_title_label.setText(safe_text(self.current_task.get("job_name"), "Current Job"))
        self.job_status_chip.set_status("RENDERING")
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(self.progress_animator.bar_value)
        self.job_percent_label.setText("{}%".format(self.current_progress_percent))
        self.job_phase_label.setText("Phase: {}".format(self.current_progress_phase))
        self.job_frame_label.setText("Frame: {}".format(self._progress_frame_text()))
        self.job_elapsed_label.setText("Elapsed: 00h 00m 00s")
        self.job_eta_label.setText("ETA: Estimating…")
        
        self.cancel_task_btn.setEnabled(True)
        self.cancel_task_btn.setIcon(get_icon("x", "#F87171", 11))
        self._update_unified_status()
        self.task_info.set_values(self.current_task)
        self.scene_path_box.set_path(safe_text(self.current_task.get("scene_path")))
        self.output_path_box.set_path(safe_text(self.current_task.get("output_path")))
        self.log_path_box.set_path(safe_text(self.current_task.get("log_path")))

    @Slot(object)
    def on_task_progress(self, payload: object) -> None:
        data = safe_dict(payload)
        percent = max(0, min(100, int(data.get("percent") or 0)))
        phase = safe_text(data.get("phase"), self.current_progress_phase, "Rendering")
        self.current_progress_target = max(self.current_progress_target, percent)
        self.progress_animator.set_target(self.current_progress_target)
        self.current_progress_phase = phase
        self.current_progress_frame = data.get("current_frame")
        self.current_progress_total_frames = max(1, int(data.get("total_frames") or self.current_progress_total_frames or 1))
        eta = data.get("eta_seconds")
        try:
            self.current_progress_eta_seconds = max(0.0, float(eta)) if eta is not None else None
        except Exception:
            self.current_progress_eta_seconds = None

        self.current_task.update(data)
        self.job_phase_label.setText("Phase: {}".format(phase))
        self.job_frame_label.setText("Frame: {}".format(self._progress_frame_text()))
        self.job_eta_label.setText("ETA: {}".format(self._progress_eta_text().replace("Remaining: ", "")))
        
        # Calculate and update elapsed time
        elapsed = time.monotonic() - self.current_task_started
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.job_elapsed_label.setText("Elapsed: {:02d}h {:02d}m {:02d}s".format(hours, minutes, seconds))
        self.task_info.set_values(data)

    @Slot(object)
    def on_task_finished(self, payload: object) -> None:
        data = safe_dict(payload)
        self.current_task = data
        self.current_task_started = 0.0
        final_target = max(0, min(100, int(data.get("progress") or 0)))
        self.current_progress_target = 100 if safe_text(data.get("status"), "FAILED").upper() == "SUCCEEDED" else max(self.current_progress_target, final_target)
        self.progress_animator.set_target(self.current_progress_target)
        self.current_progress_phase = safe_text(data.get("phase"), data.get("status"), "Finished")
        self.current_progress_frame = data.get("current_frame")
        self.current_progress_total_frames = max(1, int(data.get("total_frames") or 1))
        self.current_progress_eta_seconds = None
        status = safe_text(data.get("status"), "FAILED").upper()
        self.job_status_chip.set_status("SUCCEEDED" if status == "SUCCEEDED" else "ERROR")
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(self.progress_animator.bar_value)
        self.job_percent_label.setText("{}%".format(self.current_progress_percent))
        self.job_phase_label.setText("Phase: {}".format("Complete" if status == "SUCCEEDED" else self.current_progress_phase))
        self.job_frame_label.setText("Frame: {}".format(self._progress_frame_text()))
        self.job_eta_label.setText("ETA: {}".format("00h 00m 00s" if status == "SUCCEEDED" else "—"))
        
        elapsed = time.monotonic() - self.current_task_started if self.current_task_started > 0 else 0
        if "duration_seconds" in data:
            elapsed = data["duration_seconds"]
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.job_elapsed_label.setText("Elapsed: {:02d}h {:02d}m {:02d}s".format(hours, minutes, seconds))

        self.cancel_task_btn.setEnabled(False)
        self.cancel_task_btn.setIcon(get_icon("x", "#475569", 11))
        self._update_unified_status()
        self.task_info.set_values(data)
        self.scene_path_box.set_path(safe_text(data.get("scene_path")))
        self.output_path_box.set_path(safe_text(data.get("output_path")))
        self.log_path_box.set_path(safe_text(data.get("log_path")))
        self.current_log_path = safe_text(data.get("log_path"))

        completed = int(self.settings.value("completed_tasks", 0) or 0)
        failed = int(self.settings.value("failed_tasks", 0) or 0)
        if status == "SUCCEEDED":
            completed += 1
        else:
            failed += 1
        self.settings.setValue("completed_tasks", completed)
        self.settings.setValue("failed_tasks", failed)
        self.worker_schedule_info.set_value("completed", completed)
        self.worker_schedule_info.set_value("failed", failed)
        if hasattr(self, "dash_node_info"):
            self.dash_node_info.set_value("completed", completed)
            self.dash_node_info.set_value("failed", failed)

        self.add_history_entry(data)

    def apply_system_info(self, info: Dict[str, Any]) -> None:
        if not info:
            return
        cpu_percent = float(info.get("cpu_percent") or 0)
        memory_percent = float(info.get("memory_percent") or 0)
        disk_percent = float(info.get("disk_percent") or 0)
        gpu_percent = float(info.get("gpu_percent") or 0)
        total_memory = int(info.get("total_memory_mb") or 0) * 1024 * 1024
        used_memory = int(info.get("memory_used_mb") or 0) * 1024 * 1024
        self.cpu_meter.set_metric(
            cpu_percent,
            "{} logical cores".format(info.get("cpu_count") or "—"),
        )
        self.memory_meter.set_metric(
            memory_percent,
            "{} / {}".format(format_bytes(used_memory), format_bytes(total_memory)),
        )
        drives = info.get("disk_drives") or []
        free_bytes = int(info.get("disk_free_bytes") or 0)
        total_bytes = int(info.get("disk_total_bytes") or 0)
        num_drives = len(drives)

        if num_drives > 1:
            disk_detail = "{} free of {} ({} drives)".format(
                format_bytes(free_bytes),
                format_bytes(total_bytes),
                num_drives,
            )
            drive_tooltip = "  •  ".join(
                "{}: {} free ({}%)".format(
                    d.get("mount", "").rstrip("\\"),
                    format_bytes(d.get("free", 0)),
                    int(round(d.get("percent", 0))),
                )
                for d in drives
            )
        else:
            disk_detail = "{} free of {}".format(
                format_bytes(free_bytes),
                format_bytes(total_bytes),
            )
            drive_tooltip = disk_detail

        self.disk_meter.set_metric(disk_percent, disk_detail)
        self.disk_meter.setToolTip(drive_tooltip)
        if hasattr(self, "dash_disk_meter"):
            self.dash_disk_meter.set_metric(disk_percent, disk_detail)
            self.dash_disk_meter.setToolTip(drive_tooltip)

        gpu_name = safe_text(info.get("gpu_name")) or safe_text(self._cached_gpu_info.get("gpu_name")) or "Not detected"
        gpu_detail = gpu_name
        vram_mb = int(info.get("gpu_vram_mb") or self._cached_gpu_info.get("gpu_vram_mb") or 0)
        vram_used_mb = int(info.get("gpu_vram_used_mb") or self._cached_gpu_info.get("gpu_vram_used_mb") or 0)
        telemetry_available = bool(info.get("gpu_telemetry_available") or self._cached_gpu_info.get("gpu_telemetry_available"))

        if vram_mb:
            if telemetry_available:
                gpu_detail = "{}  •  {} / {} VRAM".format(
                    gpu_name,
                    format_bytes(vram_used_mb * 1024 * 1024),
                    format_bytes(vram_mb * 1024 * 1024),
                )
            else:
                gpu_detail = "{}  •  {} VRAM".format(
                    gpu_name,
                    format_bytes(vram_mb * 1024 * 1024),
                )
        if gpu_name != "Not detected" and not telemetry_available:
            self.gpu_meter.set_unavailable(gpu_detail + "  •  Usage unavailable")
            if hasattr(self, "dash_gpu_meter"):
                self.dash_gpu_meter.set_unavailable(gpu_detail + "  •  Usage unavailable")
        elif gpu_name == "Not detected":
            self.gpu_meter.set_unavailable("No GPU detected")
            if hasattr(self, "dash_gpu_meter"):
                self.dash_gpu_meter.set_unavailable("No GPU detected")
        else:
            self.gpu_meter.set_metric(gpu_percent, gpu_detail)
            if hasattr(self, "dash_gpu_meter"):
                self.dash_gpu_meter.set_metric(gpu_percent, gpu_detail)

        cpu_name = safe_text(info.get("cpu_name"), self._cached_cpu_name, get_cpu_name())
        self.worker_specs_info.set_values(
            {
                "os": safe_text(info.get("operating_system"), info.get("platform")),
                "user": safe_text(info.get("machine_user")),
                "cpu": cpu_name,
                "cores": "{} / {}".format(
                    info.get("cpu_count") or "—",
                    info.get("physical_cpu_count") or "—",
                ),
                "memory": "{} / {} ({}%)".format(
                    format_bytes(used_memory),
                    format_bytes(total_memory),
                    int(round(memory_percent)),
                ),
                "ip": safe_text(info.get("ip_address")),
                "mac": safe_text(info.get("mac_address")),
                "disk": disk_detail,
                "gpu": gpu_name,
                "gpu_usage": (
                    "{}%".format(int(round(gpu_percent)))
                    if gpu_name != "Not detected" and telemetry_available
                    else ("N/A" if gpu_name != "Not detected" else "—")
                ),
                "worker_version": safe_text(info.get("worker_version"), WORKER_VERSION),
            }
        )

    def refresh_local_snapshot(self) -> None:
        try:
            memory = psutil.virtual_memory()
            disk_data = collect_disk_metrics()
            snapshot = dict(self.last_system_info)
            now = time.monotonic()
            if now - self._last_local_gpu_query >= 2.0:
                snapshot.update(self.local_gpu_detector.query())
                self._cached_gpu_info = dict(self.local_gpu_detector.query())
                self._last_local_gpu_query = now
            elif self._cached_gpu_info:
                snapshot.update(self._cached_gpu_info)

            snapshot.update(
                {
                    "operating_system": "{} {}".format(platform.system(), platform.release()).strip(),
                    "machine_user": machine_user(),
                    "cpu_name": self._cached_cpu_name or get_cpu_name(),
                    "cpu_count": psutil.cpu_count(logical=True),
                    "physical_cpu_count": psutil.cpu_count(logical=False),
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "memory_percent": memory.percent,
                    "memory_used_mb": (memory.total - memory.available) // (1024 * 1024),
                    "total_memory_mb": memory.total // (1024 * 1024),
                    "disk_total_bytes": disk_data.get("disk_total_bytes", 0),
                    "disk_used_bytes": disk_data.get("disk_used_bytes", 0),
                    "disk_free_bytes": disk_data.get("disk_free_bytes", 0),
                    "disk_percent": disk_data.get("disk_percent", 0.0),
                    "disk_drives": disk_data.get("disk_drives", []),
                    "ip_address": local_ip_address(),
                    "mac_address": mac_address(),
                    "worker_version": WORKER_VERSION,
                }
            )
            self.last_system_info = snapshot
            self.apply_system_info(snapshot)
        except Exception:
            pass

    def _apply_progress_visual(self) -> None:
        self.current_progress_percent = self.progress_animator.display_percent
        self.job_progress.setRange(0, 1000)
        self.job_progress.setValue(self.progress_animator.bar_value)
        self.job_percent_label.setText("{}%".format(self.current_progress_percent))
        if hasattr(self, "kpi_frames"):
            self.kpi_frames.set_value(self._progress_frame_text(), "{}%".format(self.current_progress_percent))
        if self.current_task:
            self.current_task["progress"] = self.current_progress_percent
            self.current_task["progress_display"] = "{}%".format(self.current_progress_percent)
            self.current_task["progress_target"] = self.current_progress_target

    def _animate_progress_tick(self) -> None:
        if not self.current_task:
            return
        self.progress_animator.set_target(self.current_progress_target)
        step = 0.80 if self.current_progress_target >= 100 else 0.50
        previous = self.progress_animator.current
        current = self.progress_animator.tick(step=step)
        if current != previous or self.current_progress_percent != self.progress_animator.display_percent:
            self._apply_progress_visual()

    def _progress_frame_text(self) -> str:
        total = max(1, int(self.current_progress_total_frames or 1))
        frame = self.current_progress_frame
        if frame is None:
            completed = int(self.current_task.get("completed_frames") or 0) if self.current_task else 0
            if completed > 0:
                return "Frames {} / {}".format(min(completed, total), total)
            return "Frame — / {}".format(total)

        try:
            start = int(self.current_task.get("frame_start") or frame)
            step = max(1, int(self.current_task.get("frame_step") or 1))
            index = ((int(frame) - start) // step) + 1
            index = max(1, min(total, index))
        except Exception:
            index = max(1, int(self.current_task.get("completed_frames") or 0) + 1)
        return "Frame {} / {}".format(index, total)

    def _progress_eta_text(self) -> str:
        eta_percent = max(self.current_progress_percent, self.current_progress_target)
        if eta_percent >= 100:
            return "Remaining: 00h 00m 00s"
        if not self.current_task_started or eta_percent < 5:
            return "Remaining: Estimating…"

        elapsed = max(0.0, time.monotonic() - self.current_task_started)
        completed = int(self.current_task.get("completed_frames") or 0) if self.current_task else 0
        total = max(1, int(self.current_progress_total_frames or 1))
        if total > 1 and completed > 0:
            remaining = (elapsed / float(completed)) * max(0, total - completed)
        else:
            remaining = elapsed * (
                (100.0 - float(eta_percent))
                / max(1.0, float(eta_percent))
            )
        remaining = max(0.0, min(remaining, 7.0 * 24.0 * 60.0 * 60.0))
        return "Remaining: ~{}".format(format_duration(remaining))

    def update_live_ui(self) -> None:
        self.refresh_local_snapshot()
        if self.worker_started_monotonic:
            runtime = time.monotonic() - self.worker_started_monotonic
        else:
            runtime = 0
        self.worker_schedule_info.set_value("running_time", format_duration(runtime))
        self.worker_schedule_info.set_value(
            "after_task",
            "Pause" if self.after_task_btn.isChecked() else "Continue",
        )
        if hasattr(self, "dash_node_info"):
            self.dash_node_info.set_value("running_time", format_duration(runtime))
            self.dash_node_info.set_value("after_task", "Pause" if self.after_task_btn.isChecked() else "Continue")
            self.dash_node_info.set_value("completed", int(self.settings.value("completed_tasks", 0) or 0))
            self.dash_node_info.set_value("failed", int(self.settings.value("failed_tasks", 0) or 0))

        if self.current_task_started:
            elapsed = time.monotonic() - self.current_task_started
            elapsed_str = format_duration(elapsed)
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            self.job_elapsed_label.setText("Elapsed: {:02d}h {:02d}m {:02d}s".format(hours, minutes, seconds))
            self.job_eta_label.setText("ETA: {}".format(self._progress_eta_text().replace("Remaining: ", "")))
            if hasattr(self, "kpi_elapsed"):
                self.kpi_elapsed.set_value(elapsed_str)
            if hasattr(self, "kpi_remaining"):
                self.kpi_remaining.set_value(self._progress_eta_text().replace("Remaining: ", ""))
            self._apply_progress_visual()
            self.job_phase_label.setText("Phase: {}".format(self.current_progress_phase))
            self.job_frame_label.setText("Frame: {}".format(self._progress_frame_text()))
        profile = self.worker_profile()
        self.worker_schedule_info.set_values(
            {
                "region": safe_text(profile.get("region"), "Default"),
                "description": safe_text(profile.get("description"), "—"),
                "comment": safe_text(profile.get("comment"), "—"),
                "dequeue_mode": "Compatible Jobs",
                "concurrent_limit": "1 (single DCC process)",
                "completed": int(self.settings.value("completed_tasks", 0) or 0),
                "failed": int(self.settings.value("failed_tasks", 0) or 0),
            }
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.discovered = self.discover_dccs()
            self.refresh_dcc_tables()
            api_url = str(self.settings.value("api_url", "") or "").strip()
            api_token = str(self.settings.value("api_token", "") or "").strip()
            profile = self.worker_profile()
            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.update_config(api_url, api_token, profile, self.discovered)
                self.log("Backend configuration updated live. New settings applied immediately.")
            else:
                self.log("Settings saved.")

    def start_worker(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            return
        api_url = str(self.settings.value("api_url", "") or "").strip()
        api_token = str(self.settings.value("api_token", "") or "").strip()
        if not api_url or not api_token:
            QMessageBox.warning(
                self,
                "Missing Configuration",
                "Open Settings and provide the Backend API URL and Token.",
            )
            return

        self.discovered = self.discover_dccs()
        self.refresh_dcc_tables()
        profile = self.worker_profile()
        self.worker_thread = WorkerThread(api_url, api_token, self.discovered, profile)
        self.worker_thread.log_signal.connect(self.log)
        self.worker_thread.status_signal.connect(self.update_status)
        self.worker_thread.scheduler_signal.connect(self.update_scheduler)
        self.worker_thread.connection_signal.connect(self.update_connection)
        self.worker_thread.system_info_signal.connect(self.update_system_info)
        self.worker_thread.server_worker_signal.connect(self.update_server_worker)
        self.worker_thread.task_started_signal.connect(self.on_task_started)
        self.worker_thread.task_progress_signal.connect(self.on_task_progress)
        self.worker_thread.task_finished_signal.connect(self.on_task_finished)
        self.worker_thread.capabilities_signal.connect(lambda text: self.header_dcc_label.setToolTip(text))
        self.worker_thread.finished.connect(self.on_worker_finished)
        self.worker_thread.start()

        self.worker_started_monotonic = time.monotonic()
        self.backend_connected = False
        self.worker_status = "CONNECTING"
        self._update_unified_status()
        self.start_btn.setText("  Stop Worker")
        self.start_btn.setObjectName("DestructiveBtn")
        self.start_btn.setIcon(get_icon("stop", "#080A0F", 12))
        self.start_btn.setAccessibleName("Stop Worker Daemon")
        self.start_btn.setEnabled(True)
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.pause_dispatch_btn.setEnabled(True)
        self.pause_dispatch_btn.setText("")
        self.pause_dispatch_btn.setToolTip("Pause Dispatch")
        self.pause_dispatch_btn.setIcon(get_icon("pause", "#FFFFFF", 13))
        self.after_task_btn.setEnabled(True)
        self.after_task_btn.setText("Pause After Task")
        self.after_task_btn.setIcon(QIcon())
        self.after_task_btn.setChecked(str(profile.get("after_task")) == "pause")

    def toggle_worker_daemon(self) -> None:
        """Toggle between starting and stopping the worker daemon."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.stop_worker()
        else:
            self.start_worker()

    def stop_worker(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()

    def on_worker_finished(self) -> None:
        self.start_btn.setText("  Start Worker")
        self.start_btn.setObjectName("")
        self.start_btn.setIcon(get_icon("play", "#080A0F", 12))
        self.start_btn.setAccessibleName("Start Worker Daemon")
        self.start_btn.setEnabled(True)
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.pause_dispatch_btn.setEnabled(False)
        self.pause_dispatch_btn.setText("")
        self.pause_dispatch_btn.setToolTip("Pause Dispatch")
        self.pause_dispatch_btn.setIcon(get_icon("pause", "#475569", 13))
        self.after_task_btn.setEnabled(False)
        self.after_task_btn.setText("Pause After Task")
        self.after_task_btn.setIcon(QIcon())
        self.worker_started_monotonic = 0.0
        self.update_status("OFFLINE")
        self.update_scheduler("STOPPED")
        self.update_connection(False)
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    def toggle_dispatch_pause(self) -> None:
        if not self.worker_thread or not self.worker_thread.isRunning():
            return
        should_pause = self.scheduler_status != "PAUSED"
        self.worker_thread.set_dispatch_paused(should_pause)

    def toggle_pause_after_task(self, checked: bool) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.set_pause_after_current(bool(checked))
        self.settings.setValue("after_task", "pause" if checked else "continue")

    def cancel_current_task(self) -> None:
        if not self.worker_thread or not self.current_task_started:
            return
        answer = QMessageBox.question(
            self,
            "Cancel Current Task",
            "Stop the running DCC process and report this task as failed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.worker_thread.cancel_current_task()

    def refresh_server_data(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.request_profile_refresh()
            self.log("Server data refresh requested.")
        else:
            self.log("Start the worker before refreshing server assignments.")

    def open_log_folder(self) -> None:
        path = writable_log_root()
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def clear_log_view(self) -> None:
        self.log_console.clear()

    def copy_log_view(self) -> None:
        QApplication.clipboard().setText(self.log_console.toPlainText())

    def find_in_log(self) -> None:
        text = self.log_search_input.text().strip()
        if not text:
            return
        if not self.log_console.find(text):
            cursor = self.log_console.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_console.setTextCursor(cursor)
            self.log_console.find(text)

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

    def on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self.show_from_tray()

    def quit_app(self) -> None:
        self.is_quitting = True
        self.stop_worker()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.wait(5000)
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        self.settings.setValue("studio_geometry_v141", self.saveGeometry())
        self.settings.setValue("studio_tab_v141", self.main_stack.currentIndex())
        if self.is_quitting or os.environ.get("RENDERHIVE_TESTING") == "1":
            event.accept()
            return
        event.ignore()
        self.hide()

        if hasattr(self, "tray_icon") and self.tray_icon and self.tray_icon.isVisible():
            is_running = self.worker_thread is not None and self.worker_thread.isRunning()
            if is_running and self.current_task_started > 0:
                title = "Worker Minimized — Task in Progress"
                msg = "Active render task will continue executing in the background.\nClick the tray icon to restore the window."
            elif is_running:
                title = "Worker Minimized — Online"
                msg = "Worker daemon is actively listening for tasks in the background.\nClick the tray icon to restore the window."
            else:
                title = "Worker Minimized to Tray"
                msg = "The application is running in the background.\nClick the tray icon to restore or right-click to exit."

            icon = self.tray_icon.icon()
            if icon and not icon.isNull():
                self.tray_icon.showMessage(
                    title,
                    msg,
                    icon,
                    3000,
                )
            else:
                self.tray_icon.showMessage(
                    title,
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )


class PluginInstallWorker(QThread):
    """Background thread that installs a DCC plugin without blocking the UI."""

    finished = Signal(str, bool, str)   # dcc_key, success, message
    progress = Signal(str, str)          # dcc_key, log_line

    def __init__(self, dcc: str, target_dir: str, parent=None):
        super().__init__(parent)
        self._dcc = dcc          # "maya" or "houdini"
        self._target_dir = target_dir

    def run(self):
        dcc = self._dcc
        try:
            if dcc == "maya":
                self._install_maya()
            elif dcc == "houdini":
                self._install_houdini()
            else:
                raise RuntimeError(f"Unknown DCC: {dcc}")
            self.finished.emit(dcc, True, "Plugin installed successfully.")
        except Exception as exc:
            self.finished.emit(dcc, False, str(exc))

    def _install_maya(self):
        """Copy the Maya plugin into Maya scripts and register native Maya Module (.mod)."""
        import datetime
        import json
        import shutil

        source_dir = get_plugins_dir() / "maya"
        if not source_dir.is_dir():
            raise RuntimeError(f"Maya plugin source not found at: {source_dir}")

        maya_roots = []
        if os.name == "nt":
            for env_k in ("USERPROFILE", "OneDrive", "OneDriveConsumer"):
                val = os.environ.get(env_k)
                if val:
                    maya_roots.append(Path(val) / "Documents" / "maya")
                    maya_roots.append(Path(val) / "maya")
            maya_roots.append(Path.home() / "Documents" / "maya")
        else:
            maya_roots.append(Path.home() / "maya")

        maya_root = next((r for r in maya_roots if r.is_dir()), maya_roots[0])
        maya_scripts = maya_root / "scripts"
        install_dir = maya_scripts / "RenderHive"

        _IGNORED = {
            "__pycache__", ".git", ".idea", ".vscode", ".venv", "venv",
            "backup", "backups", "logs", "reports", "tests", "tools", "contracts",
        }
        def _ignore(directory, names):
            result = []
            for n in names:
                low = n.lower()
                if (n in _IGNORED or low.startswith("backup_")
                        or low.endswith((".zip", ".pyc", ".md", ".yaml", ".yml"))):
                    result.append(n)
            return result

        parent = install_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        stage_dir = Path(tempfile.mkdtemp(prefix="RenderHive_stage_", dir=str(parent)))
        backup_dir = None
        try:
            shutil.rmtree(str(stage_dir))
            shutil.copytree(str(source_dir), str(stage_dir), ignore=_ignore)

            if install_dir.is_dir():
                stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = Path(str(install_dir) + f"_backup_{stamp}")
                install_dir.rename(backup_dir)

            stage_dir.rename(install_dir)
        except Exception:
            if install_dir.is_dir():
                shutil.rmtree(str(install_dir), ignore_errors=True)
            if backup_dir and backup_dir.is_dir():
                backup_dir.rename(install_dir)
            raise
        finally:
            if stage_dir.is_dir():
                shutil.rmtree(str(stage_dir), ignore_errors=True)

        self.progress.emit("maya", f"Copied plugin to: {install_dir}")

        # 1. Clean any legacy userSetup.py entries (we no longer modify userSetup.py!)
        BEGIN = "# >>> RenderHive Maya startup >>>"
        END   = "# <<< RenderHive Maya startup <<<"
        candidate_setups = [maya_scripts / "userSetup.py"]
        for v_dir in maya_root.glob("*"):
            if v_dir.is_dir() and (v_dir / "scripts" / "userSetup.py").is_file():
                candidate_setups.append(v_dir / "scripts" / "userSetup.py")

        for setup_path in candidate_setups:
            if setup_path.is_file():
                try:
                    content = setup_path.read_text(encoding="utf-8")
                    start = content.find(BEGIN)
                    if start >= 0:
                        end = content.find(END, start)
                        if end >= 0:
                            end += len(END)
                            cleaned = (content[:start] + content[end:]).strip()
                        else:
                            cleaned = content[:start].rstrip()
                        if cleaned:
                            setup_path.write_text(cleaned + "\n", encoding="utf-8")
                        else:
                            setup_path.unlink()
                        self.progress.emit("maya", f"Cleaned legacy userSetup: {setup_path}")
                except Exception:
                    pass

        # 2. Register native Maya Module (.mod)
        plugin_version = "1.0.0"
        version_file = source_dir / "api" / "version.py"
        if version_file.is_file():
            for line in version_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("PLUGIN_VERSION"):
                    plugin_version = line.split("=", 1)[1].strip().strip("\"'")
                    break

        norm_install_dir = str(install_dir).replace("\\", "/")
        mod_content = (
            f"+ RenderHive {plugin_version} {norm_install_dir}\n"
            "icons: icons\n"
            "scripts: .\n"
        )
        modules_dir = maya_root / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)
        mod_file = modules_dir / "RenderHive.mod"
        mod_file.write_text(mod_content, encoding="utf-8")
        self.progress.emit("maya", f"Registered module at: {mod_file}")

        # 3. Generate native shelf_RenderHive.mel across all detected Maya versions
        try:
            icon_path_str = str(install_dir / "icons" / "renderhive_shelf_icon.png").replace("\\", "/")
            shelf_command = (
                f"import sys\\n"
                f"_rh_path = '{norm_install_dir}'\\n"
                f"if _rh_path not in sys.path: sys.path.insert(0, _rh_path)\\n"
                f"import renderhive_maya_submitter\\n"
                f"renderhive_maya_submitter.show_submitter()"
            )
            mel_content = f"""global proc shelf_RenderHive () {{
    global string $gBuffStr;
    global string $gBuffStr0;
    global string $gBuffStr1;

    shelfButton
        -enableCommandRepeat 1
        -flexibleWidthType 3
        -flexibleWidthValue 32
        -enable 1
        -width 35
        -height 34
        -manage 1
        -visible 1
        -preventOverride 0
        -annotation "Open RenderHive Maya Submitter"
        -enableBackground 0
        -backgroundColor 0 0 0 
        -highlightColor 0.32549 0.317647 0.368627 
        -align "center" 
        -label "RenderHive" 
        -labelOffset 0
        -rotation 0
        -flipX 0
        -flipY 0
        -useAlpha 1
        -font "plainLabelFont" 
        -imageOverlayLabel "" 
        -overlayLabelColor 0.8 0.8 0.8 
        -overlayLabelBackColor 0 0 0 0.5 
        -image "{icon_path_str}" 
        -image1 "{icon_path_str}" 
        -style "iconOnly" 
        -marginWidth 0
        -marginHeight 1
        -command "{shelf_command}" 
        -sourceType "python" 
        -commandRepeatable 1
        -flat 1
    ;
}}
"""
            for version_dir in maya_root.glob("*"):
                if version_dir.is_dir() and version_dir.name.isdigit():
                    shelves_dir = version_dir / "prefs" / "shelves"
                    shelves_dir.mkdir(parents=True, exist_ok=True)
                    (shelves_dir / "shelf_RenderHive.mel").write_text(mel_content, encoding="utf-8")
                    self.progress.emit("maya", f"Generated shelf file: {shelves_dir / 'shelf_RenderHive.mel'}")
        except Exception as exc:
            self.progress.emit("maya", f"Shelf generation warning: {exc}")

        try:
            info = {
                "source_dir": str(source_dir),
                "install_dir": str(install_dir),
                "plugin_version": plugin_version,
            }
            (install_dir / "renderhive_install_info.json").write_text(
                json.dumps(info, indent=4), encoding="utf-8"
            )
        except Exception:
            pass

    def _install_houdini(self):
        """Delegate to the existing houdini installer module bundled in plugins/."""
        import importlib.util
        source = get_plugins_dir() / "houdini"
        install_py = source / "installer" / "install.py"
        if not install_py.is_file():
            raise RuntimeError(f"Houdini installer not found at: {install_py}")

        spec = importlib.util.spec_from_file_location("_rh_houdini_install", str(install_py))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mod.assert_source(source)
        pref_dirs = mod.detect_pref_dirs([])
        if not pref_dirs:
            raise RuntimeError(
                "No supported Houdini preference folder was found.\n"
                "Open Houdini once, close it, then try again."
            )

        runtime, written = mod.install(source, pref_dirs)
        for path in written:
            self.progress.emit("houdini", f"Registered: {path}")
        self.progress.emit("houdini", f"Installed runtime to: {runtime}")


class PluginUninstallWorker(QThread):
    """Background thread that uninstalls a DCC plugin without blocking the UI."""

    finished = Signal(str, bool, str)   # dcc_key, success, message
    progress = Signal(str, str)          # dcc_key, log_line

    def __init__(self, dcc: str, parent=None):
        super().__init__(parent)
        self._dcc = dcc

    def run(self):
        dcc = self._dcc
        try:
            if dcc == "maya":
                self._uninstall_maya()
            elif dcc == "houdini":
                self._uninstall_houdini()
            else:
                raise RuntimeError(f"Unknown DCC: {dcc}")
            self.finished.emit(dcc, True, "Plugin uninstalled successfully.")
        except Exception as exc:
            self.finished.emit(dcc, False, str(exc))

    def _uninstall_maya(self):
        import re
        import shutil

        if os.name == "nt":
            maya_root = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "maya"
        else:
            maya_root = Path.home() / "maya"

        if not maya_root.is_dir():
            return

        # 1. Remove RenderHive.mod module files
        for mod_file in list(maya_root.glob("**/modules/RenderHive.mod")) + [maya_root / "modules" / "RenderHive.mod"]:
            if mod_file.is_file():
                try:
                    mod_file.unlink()
                    self.progress.emit("maya", f"Removed module file: {mod_file}")
                except Exception:
                    pass

        # 2. Remove RenderHive plugin directories and backups across global and all versioned folders
        candidate_script_dirs = [maya_root / "scripts"]
        for version_dir in maya_root.glob("*"):
            if version_dir.is_dir() and (version_dir / "scripts").is_dir():
                candidate_script_dirs.append(version_dir / "scripts")

        for script_dir in candidate_script_dirs:
            install_dir = script_dir / "RenderHive"
            if install_dir.is_dir():
                shutil.rmtree(str(install_dir), ignore_errors=True)
                self.progress.emit("maya", f"Removed plugin from: {install_dir}")

            # Clean any RenderHive_backup_* folders
            for backup in script_dir.glob("RenderHive_backup_*"):
                if backup.is_dir():
                    shutil.rmtree(str(backup), ignore_errors=True)

            # Clean legacy userSetup.py
            user_setup = script_dir / "userSetup.py"
            BEGIN = "# >>> RenderHive Maya startup >>>"
            END   = "# <<< RenderHive Maya startup <<<"
            if user_setup.is_file():
                try:
                    content = user_setup.read_text(encoding="utf-8")
                    start = content.find(BEGIN)
                    if start >= 0:
                        end = content.find(END, start)
                        if end >= 0:
                            end += len(END)
                            cleaned = (content[:start] + content[end:]).strip()
                        else:
                            cleaned = content[:start].rstrip()
                        if cleaned:
                            user_setup.write_text(cleaned + "\n", encoding="utf-8")
                        else:
                            user_setup.unlink()
                        self.progress.emit("maya", f"Cleaned startup hook in: {user_setup}")
                except Exception:
                    pass

        # 3. Clean Maya Shelves across all versions
        # Delete shelf_RenderHive.mel files
        for shelf_file in maya_root.glob("**/prefs/shelves/shelf_RenderHive.mel"):
            try:
                shelf_file.unlink()
                self.progress.emit("maya", f"Removed shelf file: {shelf_file}")
            except Exception:
                pass

        # In other shelves (e.g. shelf_Custom.mel), strip shelfButton blocks referencing RenderHive
        button_pattern = re.compile(
            r'[ \t]*shelfButton\b(?:(?!shelfButton\b|;\s*\n).)*?renderhive.*?;[ \t]*\r?\n?',
            re.IGNORECASE | re.DOTALL
        )
        for shelf_file in maya_root.glob("**/prefs/shelves/shelf_*.mel"):
            if not shelf_file.is_file():
                continue
            try:
                content = shelf_file.read_text(encoding="utf-8", errors="ignore")
                if "renderhive" in content.lower():
                    cleaned = button_pattern.sub("", content)
                    if cleaned != content:
                        shelf_file.write_text(cleaned, encoding="utf-8")
                        self.progress.emit("maya", f"Removed RenderHive shelf button from: {shelf_file}")
            except Exception:
                pass

    def _uninstall_houdini(self):
        import shutil
        docs = Path.home() / "Documents"
        if docs.is_dir():
            for item in docs.glob("houdini*.*"):
                if item.is_dir():
                    pkg = item / "packages" / "renderhive.json"
                    if pkg.is_file():
                        pkg.unlink()
                        self.progress.emit("houdini", f"Removed package descriptor: {pkg}")
        
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        runtime_parent = local / "RenderHive" / "Houdini"
        if runtime_parent.is_dir():
            shutil.rmtree(str(runtime_parent), ignore_errors=True)
            self.progress.emit("houdini", f"Removed Houdini runtime from: {runtime_parent}")
