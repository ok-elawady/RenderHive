"""Custom Frameless Window Titlebar for RenderHive Worker.

Provides an integrated, dark studio titlebar matching standard pro desktop software aesthetics
(e.g., VS Code, Blender, Windows 11), with 42px height, comfortable 38x28px window control buttons,
supporting window dragging, top-edge interactive window resizing, double-click maximize/restore,
and balanced 7px padding above and below controls.
"""

from __future__ import annotations

import os
import socket
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui.icons import get_icon
from ui.widgets import StatusChip
from version import WORKER_VERSION

HOSTNAME = socket.gethostname()
RESIZE_MARGIN = 6


class CustomTitleBar(QFrame):
    """Custom frameless window header bar with brand, draggable area, and window controls."""

    def __init__(self, parent_window: QWidget, icon_path: str = ""):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self._drag_pos: QPoint | None = None
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(42)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignVCenter)

        # Brand Icon
        if icon_path and os.path.exists(icon_path):
            logo = QLabel()
            logo.setObjectName("BrandLogo")
            logo.setFixedSize(18, 18)
            logo.setAlignment(Qt.AlignCenter)
            logo.setPixmap(QIcon(icon_path).pixmap(18, 18))
            layout.addWidget(logo, 0, Qt.AlignVCenter)

        # Brand Title & Typography (RenderHive / Worker // HOSTNAME  [Status])
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        title_box.setContentsMargins(4, 0, 4, 0)
        title_box.setAlignment(Qt.AlignVCenter)

        # Render + Hive brand
        brand_label = QLabel('Render<span style="color: #9C73F2;">Hive</span>')
        brand_label.setObjectName("TitleBarBrand")
        brand_label.setTextFormat(Qt.RichText)

        # Divider
        divider_label = QLabel("/")
        divider_label.setObjectName("TitleBarDivider")

        # Subtitle
        worker_label = QLabel("Worker")
        worker_label.setObjectName("TitleBarSubtitle")

        # Hostname (clean monospace, accessible contrast)
        hostname_label = QLabel(HOSTNAME)
        hostname_label.setObjectName("TitleBarHostname")

        # Integrated Unified Status Chip in Title Bar
        self.status_chip = StatusChip("OFFLINE")
        self.conn_chip = self.status_chip  # Alias for backward-compatibility

        title_box.addWidget(brand_label)
        title_box.addWidget(divider_label)
        title_box.addWidget(worker_label)
        title_box.addWidget(hostname_label)
        title_box.addWidget(self.status_chip)
        layout.addLayout(title_box)

        # Draggable Space
        layout.addStretch(1)

        # Window Control Buttons (Minimize, Maximize/Restore, Close - 38x28px standard desktop sizing)
        self.min_btn = QPushButton()
        self.min_btn.setObjectName("WindowControlBtn")
        self.min_btn.setIcon(get_icon("minimize", "#CBD5E1", 12))
        self.min_btn.setFixedSize(38, 28)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.setToolTip("Minimize")
        self.min_btn.setAccessibleName("Minimize Window")
        self.min_btn.clicked.connect(self.handle_minimize)

        self.max_btn = QPushButton()
        self.max_btn.setObjectName("WindowControlBtn")
        self.max_btn.setIcon(get_icon("maximize", "#CBD5E1", 12))
        self.max_btn.setFixedSize(38, 28)
        self.max_btn.setCursor(Qt.PointingHandCursor)
        self.max_btn.setToolTip("Maximize")
        self.max_btn.setAccessibleName("Maximize Window")
        self.max_btn.clicked.connect(self.toggle_maximize)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("WindowCloseBtn")
        self.close_btn.setIcon(get_icon("x", "#CBD5E1", 12))
        self.close_btn.setFixedSize(38, 28)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("Close to Tray")
        self.close_btn.setAccessibleName("Close Window")
        self.close_btn.clicked.connect(self.parent_window.close)

        layout.addWidget(self.min_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.max_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.close_btn, 0, Qt.AlignVCenter)

    def handle_minimize(self) -> None:
        if hasattr(self.parent_window, "animate_minimize"):
            self.parent_window.animate_minimize()
        else:
            self.parent_window.showMinimized()

    def toggle_maximize(self) -> None:
        if hasattr(self.parent_window, "toggle_maximize_window"):
            self.parent_window.toggle_maximize_window()
        else:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
            else:
                self.parent_window.showMaximized()
        self.update_max_icon(self.parent_window.isMaximized())

    def update_max_icon(self, is_maximized: bool) -> None:
        self.max_btn.setIcon(get_icon("restore" if is_maximized else "maximize", "#CBD5E1", 12))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()
            event.accept()
