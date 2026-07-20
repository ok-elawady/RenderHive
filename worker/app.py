import sys
import os
import time
import socket
import subprocess
import requests
import psutil
import platform
import shlex
import shutil
from PySide6.QtCore import QThread, Signal, QSettings, Qt, Slot, QSharedMemory
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QDialog, QLineEdit, QFormLayout, QMessageBox,
    QSystemTrayIcon, QMenu
)
import ctypes
import re

HOSTNAME = socket.gethostname()

SHADCN_STYLESHEET = """
QWidget {
    background-color: #0E1016;
    color: #F5F7FA;
    font-family: 'Segoe UI', Inter, sans-serif;
    font-size: 13px;
}
QDialog {
    background-color: #0b0d13;
}
QPushButton {
    background-color: #5a1fa6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #4a178a;
}
QPushButton:disabled {
    background-color: #171a24;
    color: #71717a;
}
QPushButton#SecondaryBtn {
    background-color: #0b0d13;
    color: #fafafa;
    border: 1px solid #171a24;
}
QPushButton#SecondaryBtn:hover {
    background-color: #171a24;
}
QPushButton#SecondaryBtn:disabled {
    background-color: #0b0d13;
    color: #71717a;
    border: 1px solid #171a24;
}
QPushButton#DestructiveBtn {
    background-color: #ca2a30;
    color: #ffffff;
    border: none;
}
QPushButton#DestructiveBtn:hover {
    background-color: #b34052;
}
QPushButton#DestructiveBtn:disabled {
    background-color: #171a24;
    color: #71717a;
}
QLineEdit {
    background-color: #171a24;
    color: #fafafa;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 6px 12px;
}
QLineEdit:focus {
    border: 1px solid #5a1fa6;
}
QTextEdit {
    background-color: #171a24;
    color: #a1a1aa;
    font-family: Consolas, monospace;
    font-size: 12px;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 10px;
}
QLabel {
    color: #fafafa;
}
QLabel#MutedLabel {
    color: #a1a1aa;
}
"""

class WorkerThread(QThread):
    log_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(self, api_url, api_token, maya_exec, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.maya_exec = maya_exec
        self.is_running = True

    def get_headers(self):
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json"
        }

    def collect_system_info(self):
        info = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "cpu_count": psutil.cpu_count(logical=True),
            "total_memory_mb": psutil.virtual_memory().total // (1024 * 1024),
        }
        
        try:
            if os.name == 'nt':
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                processor_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                info["cpu_name"] = processor_name.strip()
            else:
                info["cpu_name"] = platform.processor()
        except Exception:
            info["cpu_name"] = platform.processor()
            
        try:
            # Safely query nvidia-smi without popping a terminal window on Windows
            if shutil.which("nvidia-smi"):
                creationflags = 0
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                    
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
                    creationflags=creationflags,
                    text=True,
                    stderr=subprocess.DEVNULL
                )
            if output:
                lines = output.strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    if len(parts) >= 3:
                        info["gpu_name"] = parts[0].strip()
                        info["gpu_vram_mb"] = int(parts[1].strip())
                        info["gpu_percent"] = float(parts[2].strip())
        except Exception:
            pass
            
        return info

    def send_heartbeat(self):
        try:
            payload = {
                "hostname": HOSTNAME,
                "system_info": self.collect_system_info()
            }
            res = requests.post(f"{self.api_url}/workers/ping/", json=payload, headers=self.get_headers(), timeout=5)
            if res.status_code != 200:
                self.log_signal.emit(f"Heartbeat failed: {res.status_code}")
                return False
            return True
        except requests.exceptions.RequestException as e:
            self.log_signal.emit(f"Heartbeat connection error: {str(e)}")
            return False
        except Exception as e:
            self.log_signal.emit(f"Heartbeat unexpected error: {str(e)}")
            return False

    def run_frame(self, frame):
        frame_id = frame["id"]
        command_template = frame["command"]
        
        cmd = command_template
        
        # Normalize paths for safety (use forward slashes)
        normalized_maya_exec = self.maya_exec.replace("\\", "/")
        normalized_scene_path = frame["scene_path"].replace("\\", "/")
        

        # Support both uppercase and lowercase placeholders for robustness
        # Auto-wrap in quotes if not already quoted to handle spaces in paths safely
        for placeholder in ("{MAYA_EXEC}", "{maya_exec}"):
            if placeholder in cmd:
                idx = cmd.find(placeholder)
                if idx > 0 and cmd[idx-1] in ('"', "'") and idx + len(placeholder) < len(cmd) and cmd[idx + len(placeholder)] == cmd[idx-1]:
                    cmd = cmd.replace(placeholder, normalized_maya_exec)
                else:
                    cmd = cmd.replace(placeholder, f'"{normalized_maya_exec}"')
                    
        cmd = cmd.replace("{FRAME}", str(frame["number"])).replace("{frame}", str(frame["number"]))
        
        for placeholder in ("{SCENE_PATH}", "{scene_path}"):
            if placeholder in cmd:
                idx = cmd.find(placeholder)
                if idx > 0 and cmd[idx-1] in ('"', "'") and idx + len(placeholder) < len(cmd) and cmd[idx + len(placeholder)] == cmd[idx-1]:
                    cmd = cmd.replace(placeholder, normalized_scene_path)
                else:
                    cmd = cmd.replace(placeholder, f'"{normalized_scene_path}"')
        
        self.log_signal.emit(f"Executing frame {frame['number']}...")
        
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{frame_id}.log")
        
        if not shutil.which(self.maya_exec):
            self.log_signal.emit(f"Error: Maya executable not found at '{self.maya_exec}'")
            return -1

        exit_status = -1
        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            # Use POSIX mode even on Windows so that shlex correctly handles escaped quotes (like \")
            # inside arguments. POSIX mode automatically strips the outer quotes.
            cmd_list = shlex.split(cmd, posix=True)
            
            # Ensure the first argument is the absolute path to Maya if the command just says "render"
            if cmd_list and cmd_list[0].lower() in ("render", "render.exe"):
                cmd_list[0] = self.maya_exec
            
            # self.log_signal.emit(f"Command list: {cmd_list}")
            
            with open(log_file, "w") as f:
                process = subprocess.Popen(
                    cmd_list,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    text=True,
                )
                
                # Periodically read the process stdout line-by-line to parse progress
                # and send heartbeats while rendering.
                last_heartbeat = time.time()
                output_image_path = None
                
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                        
                    if line:
                        f.write(line)
                        f.flush()
                        
                        # Parse output image location (looks for writing/written/saved + file path with image extension)
                        img_match = re.search(r'(?:writing|written|saved|saving).*?([a-zA-Z]:[^\s]+\.(?:exr|png|iff|jpg|jpeg|tga|tif|tiff|bmp))', line, re.IGNORECASE)
                        if img_match:
                            output_image_path = img_match.group(1).replace("\\", "/")
                            
                    if not self.is_running:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        break
                        
                    time.sleep(0.1) # Small sleep to prevent CPU spiking while reading
                    now = time.time()
                    if now - last_heartbeat > 5:
                        self.send_heartbeat()
                        last_heartbeat = now
                        
                exit_status = process.returncode
                
                # Normalize log file path for display
                display_log_file = log_file.replace("\\", "/")
                
                if exit_status == 0:
                    success_msg = f"Frame {frame['number']} completed successfully."
                    if output_image_path:
                        success_msg += f"\n  Output Image: {output_image_path}"
                    success_msg += f"\n  Log saved to: {display_log_file}"
                    self.log_signal.emit(success_msg)
                else:
                    error_tail = ""
                    try:
                        with open(log_file, "r") as log_r:
                            lines = log_r.readlines()
                            if lines:
                                last_lines = "".join(lines[-3:]).strip()
                                error_tail = f"\n  Output: {last_lines}"
                    except Exception:
                        pass
                    self.log_signal.emit(f"Frame {frame['number']} failed (Exit Code: {exit_status}){error_tail}\n  Log saved to: {display_log_file}")
        except Exception as e:
            self.log_signal.emit(f"Failed to execute frame: {str(e)}")
        
        return exit_status

    def report_status(self, frame_id, exit_status):
        try:
            endpoint = "succeed" if exit_status == 0 else "fail"
            res = requests.post(f"{self.api_url}/frames/{frame_id}/{endpoint}/", json={"exit_status": exit_status}, headers=self.get_headers())
            if res.status_code != 200:
                self.log_signal.emit(f"Failed to report status: {res.status_code}")
        except Exception as e:
            self.log_signal.emit(f"Error reporting status: {str(e)}")

    def run(self):
        self.log_signal.emit(f"Starting Worker on {HOSTNAME}...")
        
        if not shutil.which(self.maya_exec):
            self.log_signal.emit(f"FATAL: Maya executable not found at '{self.maya_exec}'")
            self.log_signal.emit("Please update the path in Settings and restart.")
            self.status_signal.emit("ERROR")
            self.is_running = False
            return
            
        if not self.send_heartbeat():
            self.log_signal.emit("FATAL: Cannot connect to the server or authentication failed.")
            self.log_signal.emit("Please check your API URL and Token in Settings and restart.")
            self.status_signal.emit("ERROR")
            self.is_running = False
            return
            
        self.log_signal.emit("Worker started successfully!")
        self.status_signal.emit("ONLINE")
        psutil.cpu_percent(interval=1)
        
        last_heartbeat = time.time()
        
        while self.is_running:
            now = time.time()
            if now - last_heartbeat > 5:
                self.send_heartbeat()
                last_heartbeat = now
                
            try:
                res = requests.post(f"{self.api_url}/frames/dispatch/", json={"worker_name": HOSTNAME}, headers=self.get_headers())
                if res.status_code == 200:
                    self.status_signal.emit("RENDERING")
                    frame = res.json()
                    self.log_signal.emit(f"Received frame {frame['id']} (Frame {frame['number']})")
                    
                    exit_status = self.run_frame(frame)
                    self.report_status(frame["id"], exit_status)
                    self.status_signal.emit("ONLINE")
                elif res.status_code == 404:
                    time.sleep(5)  # No frames
                else:
                    self.log_signal.emit(f"Dispatch error: {res.status_code}")
                    time.sleep(5)
            except Exception as e:
                self.log_signal.emit(f"Error connecting to server: {str(e)}")
                time.sleep(5)

    def stop(self):
        self.is_running = False
        self.log_signal.emit("Worker stopping...")
        self.status_signal.emit("OFFLINE")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Worker Settings")
        self.setMinimumWidth(400)
        
        self.settings = QSettings("RenderHive", "WorkerDaemon")
        
        layout = QFormLayout(self)
        
        self.api_url_input = QLineEdit()
        self.api_url_input.setText(self.settings.value("api_url", "http://api.renderhive.local/api"))
        layout.addRow("API URL:", self.api_url_input)
        
        self.api_token_input = QLineEdit()
        self.api_token_input.setText(self.settings.value("api_token", ""))
        self.api_token_input.setEchoMode(QLineEdit.Password)
        layout.addRow("API Token:", self.api_token_input)
        
        self.maya_exec_input = QLineEdit()
        self.maya_exec_input.setText(self.settings.value("maya_exec", "C:/Program Files/Autodesk/Maya2025/bin/Render.exe"))
        layout.addRow("Maya Executable:", self.maya_exec_input)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def save_settings(self):
        self.settings.setValue("api_url", self.api_url_input.text().strip())
        self.settings.setValue("api_token", self.api_token_input.text().strip())
        self.settings.setValue("maya_exec", self.maya_exec_input.text().strip())
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RenderHive Worker")
        self.resize(600, 400)
        
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
            
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(settings_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
        QApplication.instance().aboutToQuit.connect(self.stop_worker)
        
        self.settings = QSettings("RenderHive", "WorkerDaemon")
        self.worker_thread = None
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Top Bar
        top_layout = QHBoxLayout()
        
        self.status_label = QLabel("Status: OFFLINE")
        self.status_label.setObjectName("MutedLabel")
        top_layout.addWidget(self.status_label)
        
        top_layout.addStretch()
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("SecondaryBtn")
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn)
        
        main_layout.addLayout(top_layout)
        
        # Log Console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        main_layout.addWidget(self.log_console)
        
        # Bottom Bar
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 10, 0, 0)
        
        self.start_btn = QPushButton("Start Worker")
        self.start_btn.clicked.connect(self.start_worker)
        
        self.stop_btn = QPushButton("Stop Worker")
        self.stop_btn.setObjectName("DestructiveBtn")
        self.stop_btn.clicked.connect(self.stop_worker)
        self.stop_btn.setEnabled(False)
        
        bottom_layout.addWidget(self.start_btn)
        bottom_layout.addWidget(self.stop_btn)
        main_layout.addLayout(bottom_layout)
        
        self.log("Worker UI Loaded. Configure settings and click Start.")

    @Slot(str)
    def log(self, message):
        self.log_console.append(message)

    @Slot(str)
    def update_status(self, status):
        colors = {
            "OFFLINE": "#a1a1aa",
            "ONLINE": "#22c55e",
            "RENDERING": "#f59e0b",
            "ERROR": "#ef4444"
        }
        color = colors.get(status, "#fafafa")
        self.status_label.setText(f"Status: {status}")
        self.status_label.setStyleSheet(f"font-weight: bold; color: {color};")

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def start_worker(self):
        api_url = self.settings.value("api_url", "")
        api_token = self.settings.value("api_token", "")
        maya_exec = self.settings.value("maya_exec", "")
        
        if not api_url or not api_token:
            QMessageBox.warning(self, "Missing Configuration", "Please open Settings and provide the API URL and Token.")
            return

        self.worker_thread = WorkerThread(api_url, api_token, maya_exec)
        self.worker_thread.log_signal.connect(self.log)
        self.worker_thread.status_signal.connect(self.update_status)
        self.worker_thread.finished.connect(self.on_worker_finished)
        self.worker_thread.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.settings_btn.setEnabled(False)

    def stop_worker(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            # Wait for thread to finish asynchronously instead of blocking
            
    def on_worker_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.settings_btn.setEnabled(True)
        self.update_status("OFFLINE")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            self.show()
            self.raise_()
            self.activateWindow()

    def quit_app(self):
        self.is_quitting = True
        QApplication.instance().quit()

    def closeEvent(self, event):
        if hasattr(self, 'is_quitting') and self.is_quitting:
            event.accept()
            return
            
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "RenderHive Worker",
            "Application minimized to tray.",
            QSystemTrayIcon.Information,
            2000
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Enforce single instance
    shared_mem = QSharedMemory("RenderHiveWorkerSingleton")
    if not shared_mem.create(1):
        QMessageBox.warning(None, "Already Running", "RenderHive Worker is already running.")
        sys.exit(0)

    # Fix for Windows Taskbar Icon
    if os.name == 'nt':
        myappid = 'renderhive.worker.daemon.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
    app.setStyleSheet(SHADCN_STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
