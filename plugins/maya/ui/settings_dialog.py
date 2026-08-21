"""Studio settings and configuration dialog for RenderHive Maya Submitter."""

from __future__ import absolute_import, print_function

import os
import sys
import time

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError

from .qt_compat import QtCore, QtGui, QtWidgets
from .icons import get_icon, icon_path
from .qt_theme import COLORS, build_stylesheet
from .font_loader import load_application_fonts

try:
    from api.config import get_env_file_path, load_env_file, write_env_file, load_config, save_config
except (ImportError, ValueError):
    from ..api.config import get_env_file_path, load_env_file, write_env_file, load_config, save_config

try:
    from core.runtime_log import get_logger
    LOGGER = get_logger("settings_dialog")
except Exception:
    LOGGER = None


class SettingsDialog(QtWidgets.QDialog):
    """Configuration modal matching the Shadcn/UI sidesheet layout from the Worker desktop client."""

    def __init__(self, submitter_window=None, parent=None):
        super(SettingsDialog, self).__init__(parent or submitter_window)
        self.submitter = submitter_window
        self.setObjectName("RenderHiveDialog")
        self.setWindowTitle("Maya Submitter Settings")
        self.setModal(True)
        self.setMinimumSize(680, 600)
        self.resize(700, 660)

        # Window background matching #080A0E (Worker Parity)
        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#080A0E"))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        load_application_fonts(self)
        self.setStyleSheet(build_stylesheet())
        self._apply_window_theme()

        # Window icon
        _icon_path = icon_path("renderhive_header_logo.png")
        if os.path.isfile(_icon_path):
            self.setWindowIcon(QtGui.QIcon(_icon_path))

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (#0B0E17 matching DWM Titlebar & Worker SheetHeader) ──
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("DialogHeader")
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(3)

        title = QtWidgets.QLabel("Maya Submitter Configuration")
        title.setObjectName("PageTitle")
        subtitle = QtWidgets.QLabel(
            "Configure network authentication, worker metadata, and dispatch behavior."
        )
        subtitle.setObjectName("MutedLabel")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_frame)



        # ── Scrollable Body Area (Sidesheet Content matching Worker) ──
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("SettingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        body = QtWidgets.QWidget()
        body.setObjectName("SettingsBody")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(18)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Load active .env and config values
        env_values = load_env_file()
        cfg = load_config()

        # ── Section 1: Backend Connection ──
        sec_conn = QtWidgets.QWidget()
        sec_conn_layout = QtWidgets.QVBoxLayout(sec_conn)
        sec_conn_layout.setContentsMargins(0, 0, 0, 0)
        sec_conn_layout.setSpacing(8)
        sec_conn_layout.addWidget(
            self._create_section_header(
                "globe",
                "BACKEND CONNECTION",
                "Server endpoint and authentication token for worker orchestration.",
            )
        )

        conn_form = QtWidgets.QFormLayout()
        conn_form.setLabelAlignment(QtCore.Qt.AlignLeft)
        conn_form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        conn_form.setHorizontalSpacing(16)
        conn_form.setVerticalSpacing(8)
        conn_form.setContentsMargins(0, 4, 0, 0)

        # Active .env Path Notice
        env_path = get_env_file_path()
        self.env_path_input = QtWidgets.QLineEdit()
        self.env_path_input.setObjectName("ReadOnlyEnvPath")
        self.env_path_input.setText(str(env_path) if env_path else "No .env detected")
        self.env_path_input.setReadOnly(True)
        self.env_path_input.setFixedHeight(34)
        self.env_path_input.setToolTip(str(env_path))
        conn_form.addRow(".env File", self.env_path_input)

        # API Endpoint
        self.endpoint_input = QtWidgets.QLineEdit()
        self.endpoint_input.setFixedHeight(34)
        self.endpoint_input.setPlaceholderText("http://127.0.0.1:8000/api")

        initial_endpoint = (
            env_values.get("RENDERHIVE_API_URL")
            or env_values.get("API_URL")
            or os.environ.get("RENDERHIVE_API_URL")
            or cfg.get("base_url")
            or "http://127.0.0.1:8000/api"
        )
        self.endpoint_input.setText(str(initial_endpoint))
        self.endpoint_input.textChanged.connect(self._on_connection_input_changed)
        conn_form.addRow("API URL", self.endpoint_input)

        # API Token / Key
        token_row = QtWidgets.QHBoxLayout()
        token_row.setContentsMargins(0, 0, 0, 0)
        token_row.setSpacing(6)

        self.token_input = QtWidgets.QLineEdit()
        self.token_input.setFixedHeight(34)
        self.token_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.token_input.setPlaceholderText("Enter worker authentication token")

        initial_token = (
            env_values.get("RENDERHIVE_API_TOKEN")
            or env_values.get("API_TOKEN")
            or env_values.get("RENDERHIVE_API_KEY")
            or os.environ.get("RENDERHIVE_API_TOKEN")
            or cfg.get("auth", {}).get("token")
            or ""
        )
        self.token_input.setText(str(initial_token))
        self.token_input.textChanged.connect(self._on_connection_input_changed)

        self.toggle_token_btn = QtWidgets.QPushButton("  Show")
        self.toggle_token_btn.setObjectName("SecondaryBtn")
        self.toggle_token_btn.setFixedHeight(34)
        self.toggle_token_btn.setMinimumWidth(68)
        self.toggle_token_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.toggle_token_btn.clicked.connect(self._toggle_token_visibility)

        token_row.addWidget(self.token_input, 1)
        token_row.addWidget(self.toggle_token_btn)

        token_container = QtWidgets.QWidget()
        token_container.setLayout(token_row)
        conn_form.addRow("API Token", token_container)

        sec_conn_layout.addLayout(conn_form)

        # Test Connection Row with Live Status Badge
        test_row = QtWidgets.QHBoxLayout()
        test_row.setSpacing(12)
        test_row.setContentsMargins(0, 4, 0, 0)

        test_btn = QtWidgets.QPushButton("  Test Connection")
        test_btn.setObjectName("SecondaryBtn")
        test_btn.setIcon(get_icon("radio", "#CBD5E1", 13))
        test_btn.setFixedHeight(34)
        test_btn.setMinimumWidth(140)
        test_btn.setCursor(QtCore.Qt.PointingHandCursor)
        test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(test_btn)

        self.test_status_lbl = QtWidgets.QLabel()
        self.test_status_lbl.setVisible(False)
        test_row.addWidget(self.test_status_lbl)
        test_row.addStretch()

        sec_conn_layout.addLayout(test_row)
        body_layout.addWidget(sec_conn)

        # Divider
        body_layout.addWidget(self._create_section_divider())

        # ── Section 2: Storage & Local Paths ──
        sec_storage = QtWidgets.QWidget()
        sec_storage_layout = QtWidgets.QVBoxLayout(sec_storage)
        sec_storage_layout.setContentsMargins(0, 0, 0, 0)
        sec_storage_layout.setSpacing(8)
        sec_storage_layout.addWidget(
            self._create_section_header(
                "folder",
                "STORAGE & LOCAL DATA",
                "Runtime log files, local state cache, and persistence directories.",
            )
        )

        storage_row = QtWidgets.QHBoxLayout()
        storage_row.setSpacing(12)
        storage_row.setContentsMargins(0, 4, 0, 0)

        open_logs_btn = QtWidgets.QPushButton("  Open Runtime Logs")
        open_logs_btn.setObjectName("SecondaryBtn")
        open_logs_btn.setIcon(get_icon("terminal", "#CBD5E1", 13))
        open_logs_btn.setFixedHeight(34)
        open_logs_btn.setCursor(QtCore.Qt.PointingHandCursor)
        if self.submitter and hasattr(self.submitter, "open_runtime_logs_folder"):
            open_logs_btn.clicked.connect(self.submitter.open_runtime_logs_folder)

        open_data_btn = QtWidgets.QPushButton("  Open Restore Data Folder")
        open_data_btn.setObjectName("SecondaryBtn")
        open_data_btn.setIcon(get_icon("folder", "#CBD5E1", 13))
        open_data_btn.setFixedHeight(34)
        open_data_btn.setCursor(QtCore.Qt.PointingHandCursor)
        if self.submitter and hasattr(self.submitter, "open_state_storage_folder"):
            open_data_btn.clicked.connect(self.submitter.open_state_storage_folder)

        storage_row.addWidget(open_logs_btn)
        storage_row.addWidget(open_data_btn)
        storage_row.addStretch()
        sec_storage_layout.addLayout(storage_row)
        body_layout.addWidget(sec_storage)

        # Divider
        body_layout.addWidget(self._create_section_divider())

        # ── Section 3: Pipeline Health & Support ──
        sec_diag = QtWidgets.QWidget()
        sec_diag_layout = QtWidgets.QVBoxLayout(sec_diag)
        sec_diag_layout.setContentsMargins(0, 0, 0, 0)
        sec_diag_layout.setSpacing(8)
        sec_diag_layout.addWidget(
            self._create_section_header(
                "shield-check",
                "PIPELINE HEALTH & SUPPORT",
                "Run environment validation or generate a full diagnostic support bundle.",
            )
        )

        diag_row = QtWidgets.QHBoxLayout()
        diag_row.setSpacing(12)
        diag_row.setContentsMargins(0, 4, 0, 0)

        health_btn = QtWidgets.QPushButton("  Run Production Check")
        health_btn.setObjectName("SecondaryBtn")
        health_btn.setIcon(get_icon("shield-check", "#CBD5E1", 13))
        health_btn.setFixedHeight(34)
        health_btn.setCursor(QtCore.Qt.PointingHandCursor)
        if self.submitter and hasattr(self.submitter, "run_production_check"):
            health_btn.clicked.connect(self.submitter.run_production_check)

        bundle_btn = QtWidgets.QPushButton("  Create Support Bundle")
        bundle_btn.setObjectName("SecondaryBtn")
        bundle_btn.setIcon(get_icon("archive", "#CBD5E1", 13))
        bundle_btn.setFixedHeight(34)
        bundle_btn.setCursor(QtCore.Qt.PointingHandCursor)
        if self.submitter and hasattr(self.submitter, "create_support_bundle"):
            bundle_btn.clicked.connect(self.submitter.create_support_bundle)

        diag_row.addWidget(health_btn)
        diag_row.addWidget(bundle_btn)
        diag_row.addStretch()
        sec_diag_layout.addLayout(diag_row)
        body_layout.addWidget(sec_diag)

        # Divider
        body_layout.addWidget(self._create_section_divider())

        # ── Section 4: Danger Zone ──
        sec_danger = QtWidgets.QWidget()
        sec_danger_layout = QtWidgets.QVBoxLayout(sec_danger)
        sec_danger_layout.setContentsMargins(0, 0, 0, 0)
        sec_danger_layout.setSpacing(8)
        sec_danger_layout.addWidget(
            self._create_section_header(
                "alert-triangle",
                "DANGER ZONE",
                "Destructive plugin maintenance actions.",
            )
        )

        danger_row = QtWidgets.QHBoxLayout()
        danger_row.setContentsMargins(0, 4, 0, 0)

        uninstall_btn = QtWidgets.QPushButton("  Uninstall RenderHive")
        uninstall_btn.setObjectName("DestructiveTonalBtn")
        uninstall_btn.setIcon(get_icon("x", COLORS["error"], 13))
        uninstall_btn.setFixedHeight(34)
        uninstall_btn.setCursor(QtCore.Qt.PointingHandCursor)
        uninstall_btn.clicked.connect(self._uninstall_plugin)
        danger_row.addWidget(uninstall_btn)
        danger_row.addStretch()

        sec_danger_layout.addLayout(danger_row)
        body_layout.addWidget(sec_danger)
        body_layout.addStretch()

        # ── Full-Width Divider above action buttons ──
        actions_divider = QtWidgets.QFrame()
        actions_divider.setObjectName("SheetDivider")
        actions_divider.setFixedHeight(1)
        root.addWidget(actions_divider)

        # ── Full-Width Dialog Footer (#0B0E17 matching DWM Titlebar) ──
        footer_frame = QtWidgets.QFrame()
        footer_frame.setObjectName("DialogFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QtWidgets.QPushButton("  Save Settings")
        save_btn.setObjectName("SubmitButton")
        save_btn.setIcon(get_icon("check", COLORS["primary_fg"], 13))
        save_btn.setFixedHeight(34)
        save_btn.setMinimumWidth(130)
        save_btn.setCursor(QtCore.Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_settings)

        footer_layout.addWidget(cancel_btn)
        footer_layout.addWidget(save_btn)
        root.addWidget(footer_frame)

    def _create_section_header(self, icon_name, title_text, desc_text=""):
        """Create a section title row matching the Worker desktop client sidesheet."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(7)
        title_row.setContentsMargins(1, 0, 0, 0)

        icon_lbl = QtWidgets.QLabel()
        icon_lbl.setPixmap(get_icon(icon_name, "#9C73F2", 14).pixmap(14, 14))
        icon_lbl.setFixedSize(14, 14)
        title_row.addWidget(icon_lbl)

        title_lbl = QtWidgets.QLabel(title_text)
        title_lbl.setObjectName("SheetSectionTitle")
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        layout.addLayout(title_row)

        if desc_text:
            desc_lbl = QtWidgets.QLabel(desc_text)
            desc_lbl.setObjectName("MutedLabel")
            desc_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; margin-top: 2px;")
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        return container

    def _create_section_divider(self):
        """Create a full-width 1px dialog separator line matching the worker."""
        divider = QtWidgets.QFrame()
        divider.setObjectName("SheetDivider")
        divider.setFixedHeight(1)
        return divider

    def _toggle_token_visibility(self):
        if self.token_input.echoMode() == QtWidgets.QLineEdit.Password:
            self.token_input.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.toggle_token_btn.setText("  Hide")
        else:
            self.token_input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.toggle_token_btn.setText("  Show")

    def _on_connection_input_changed(self):
        if hasattr(self, "test_status_lbl"):
            self.test_status_lbl.setVisible(False)

    def _set_test_status(self, status, message):
        self.test_status_lbl.setVisible(True)
        base_style = (
            "border-radius: 12px; padding: 2px 10px; "
            "font-weight: 600; font-size: 11px; "
            "font-family: 'JetBrains Mono', Consolas, monospace; "
            "min-height: 20px; max-height: 22px;"
        )
        
        if status == "success":
            self.test_status_lbl.setText("✓  " + message)
            self.test_status_lbl.setStyleSheet(
                "color: #4ADE80; background-color: rgba(74, 222, 128, 0.12); border: 1px solid rgba(74, 222, 128, 0.35); " + base_style
            )
        elif status == "testing":
            self.test_status_lbl.setText("●  " + message)
            self.test_status_lbl.setStyleSheet(
                "color: #C084FC; background-color: rgba(192, 132, 252, 0.12); border: 1px solid rgba(192, 132, 252, 0.35); " + base_style
            )
        else:
            self.test_status_lbl.setText("✕  " + message)
            self.test_status_lbl.setStyleSheet(
                "color: #F87171; background-color: rgba(248, 113, 113, 0.12); border: 1px solid rgba(248, 113, 113, 0.35); " + base_style
            )

    def _test_connection(self):
        endpoint = self.endpoint_input.text().strip()
        token = self.token_input.text().strip()

        if not endpoint:
            self._set_test_status("error", "Please enter an API endpoint URL")
            return

        if not endpoint.startswith(("http://", "https://")):
            self._set_test_status("error", "Endpoint must start with http:// or https://")
            return

        self._set_test_status("testing", "Connecting to backend…")
        QtWidgets.QApplication.processEvents()

        url = endpoint.rstrip("/")
        base_url = url[:-4] if url.endswith("/api") else url

        # Step 1: Check server health
        health_url = (base_url + "/api/health/") if not url.endswith("/api/health/") else url
        server_online = False
        t0 = time.time()
        try:
            req_health = Request(health_url)
            req_health.add_header("Accept", "application/json")
            resp_h = urlopen(req_health, timeout=3.0)
            if 200 <= resp_h.getcode() < 300:
                server_online = True
        except Exception:
            server_online = False

        # Step 2: Probe authenticated jobs endpoint
        jobs_url = url + "/jobs/?page=1" if url.endswith("/api") else (url + "/api/jobs/?page=1" if not url.endswith("/jobs/?page=1") else url)

        clean_token = token.strip()
        if clean_token.lower().startswith("token "):
            clean_token = clean_token[6:].strip()
        elif clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        try:
            req = Request(jobs_url)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "RenderHive-Maya-Submitter")
            if clean_token:
                req.add_header("Authorization", "Token " + clean_token)

            resp = urlopen(req, timeout=4.0)
            latency_ms = max(1, int((time.time() - t0) * 1000))
            code = resp.getcode()
            if 200 <= code < 300:
                self._set_test_status("success", "Connected ({}ms)".format(latency_ms))
            else:
                self._set_test_status("error", "HTTP {}".format(code))

        except HTTPError as err:
            if err.code in (401, 403):
                if server_online:
                    if not clean_token:
                        msg = "Server is online, but API Key is empty (HTTP {})".format(err.code)
                    else:
                        msg = "Server is online, but API Key was rejected (HTTP {})".format(err.code)
                else:
                    msg = "Authentication required (HTTP {}): Provide a valid API Key".format(err.code)
                self._set_test_status("error", msg)
            elif err.code == 404:
                self._set_test_status("error", "Endpoint not found (HTTP 404): Check API path")
            else:
                self._set_test_status("error", "HTTP Error {}: {}".format(err.code, err.reason))

        except URLError as err:
            self._set_test_status("error", "Connection refused: Cannot reach server at {}".format(endpoint))

        except Exception as err:
            self._set_test_status("error", "Connection error: {}".format(str(err)))

    def _save_settings(self):
        new_endpoint = self.endpoint_input.text().strip()
        new_token = self.token_input.text().strip()

        if new_token.lower().startswith("token "):
            new_token = new_token[6:].strip()
        elif new_token.lower().startswith("bearer "):
            new_token = new_token[7:].strip()

        # Update .env file
        try:
            write_env_file({
                "RENDERHIVE_API_URL": new_endpoint,
                "RENDERHIVE_API_TOKEN": new_token,
            })
        except Exception as err:
            if LOGGER:
                LOGGER.warning("Could not write .env file: %s", err)

        # Update process environment variables
        os.environ["RENDERHIVE_API_URL"] = new_endpoint
        os.environ["RENDERHIVE_API_TOKEN"] = new_token

        # Update JSON config store
        try:
            save_config({
                "base_url": new_endpoint,
                "auth": {"token": new_token},
            })
        except Exception:
            pass

        if self.submitter and hasattr(self.submitter, "api"):
            try:
                setattr(self.submitter.api, "endpoint", new_endpoint)
                setattr(self.submitter.api, "token", new_token)
                if hasattr(self.submitter, "append_activity"):
                    self.submitter.append_activity("Settings updated & saved to .env: %s" % new_endpoint)
            except Exception:
                pass

        self.accept()

    def _uninstall_plugin(self):
        if self.submitter and hasattr(self.submitter, "api") and hasattr(self.submitter.api, "uninstall_renderhive_from_maya"):
            self.submitter.api.uninstall_renderhive_from_maya()
            self.reject()

    def showEvent(self, event):
        super(SettingsDialog, self).showEvent(event)
        self._apply_window_theme()

    def _apply_window_theme(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes as wintypes
            hwnd = wintypes.HWND(int(self.winId()))
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark), ctypes.sizeof(dark))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(0x00170E0B)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(0x00E1D5CB)), 4)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(ctypes.c_int(0x00453128)), 4)
        except Exception:
            pass
