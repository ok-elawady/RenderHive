"""Reusable Shadcn-styled VFX widgets for the RenderHive Worker dashboard."""

from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_icon


class SegmentNavButton(QPushButton):
    """Pill navigation button that dynamically syncs icon color with checked/unchecked text color."""

    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__("  " + text.strip(), parent)
        self.icon_name = icon_name
        self.setObjectName("SegmentNavBtn")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.setAccessibleName(text.strip())
        self._update_icon(self.isChecked())
        self.toggled.connect(self._update_icon)

    def _update_icon(self, checked: bool) -> None:
        color = "#080A0F" if checked else "#CBD5E1"
        self.setIcon(get_icon(self.icon_name, color, 13))


NavButton = SegmentNavButton


class SectionCard(QFrame):
    """Shadcn Card with optional header divider and clean typography."""

    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("SectionCard")
        # Remove inner margins so CardHeader and CardContent can bleed to the edges
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        if title or subtitle:
            header_frame = QFrame()
            header_frame.setObjectName("CardHeader")
            header = QVBoxLayout(header_frame)
            header.setContentsMargins(16, 14, 16, 14)
            header.setSpacing(4)
            
            if title:
                title_label = QLabel(title)
                title_label.setObjectName("SectionTitle")
                header.addWidget(title_label)
            if subtitle:
                subtitle_label = QLabel(subtitle)
                subtitle_label.setObjectName("MutedLabel")
                subtitle_label.setWordWrap(True)
                header.addWidget(subtitle_label)
            self.root.addWidget(header_frame)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("CardContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(8)
        self.root.addWidget(self.content_widget, 1)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.content_layout.addWidget(widget, stretch)

    def add_layout(self, layout, stretch: int = 0) -> None:
        self.content_layout.addLayout(layout, stretch)


class StatCard(QFrame):
    """Metric Stat Card following shadcn StatChip aesthetic with bold monospace value."""

    def __init__(self, caption: str, value: str = "—", detail: str = "", icon_name: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        # Tighten margins and spacing to match frontend `p-4 gap-4` equivalent
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("CardCaption")
        header.addWidget(self.caption_label)
        header.addStretch()
        
        if icon_name:
            self.icon_label = QLabel()
            self.icon_label.setPixmap(get_icon(icon_name, "#A1A7BB", 14).pixmap(14, 14))
            header.addWidget(self.icon_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("MutedLabel")
        self.detail_label.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)
        # No addStretch() here, so the card wraps its content naturally without blowing up vertically.

    def set_value(self, value: object, detail: str | None = None) -> None:
        self.value_label.setText(str(value if value not in (None, "") else "—"))
        if detail is not None:
            self.detail_label.setText(detail)


class ResourceMeter(QFrame):
    """Telemetry Resource Meter gauge with percentage tag and detailed subtext."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("FieldLabel")
        self.value_label = QLabel("0%")
        self.value_label.setObjectName("FieldValue")
        self.value_label.setStyleSheet("font-weight: 600; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 13px; color: #F5F7FA;")
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.value_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.detail_label = QLabel("—")
        self.detail_label.setObjectName("MutedLabel")
        self.detail_label.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail_label)

    def set_metric(self, percent: float, detail: str = "") -> None:
        safe = max(0, min(100, int(round(float(percent or 0)))))
        self.bar.setValue(safe)
        self.value_label.setText("{}%".format(safe))
        self.detail_label.setText(detail or "—")

    def set_unavailable(self, detail: str = "") -> None:
        self.bar.setValue(0)
        self.value_label.setText("N/A")
        self.detail_label.setText(detail or "Telemetry unavailable")


class StatusChip(QLabel):
    """Clean text status badge with dynamic colorized icon dot and label matching status."""

    # (Foreground Color, Icon/Dot)
    STYLES = {
        "ONLINE": ("#3DDC84", "●"),
        "RENDERING": ("#C084FC", "●"),
        "PAUSED": ("#FFB84D", "●"),
        "OFFLINE": ("#94A3B8", "○"),
        "ERROR": ("#FF5D73", "●"),
        "CONNECTED": ("#3DDC84", "●"),
        "DISCONNECTED": ("#FF5D73", "●"),
    }

    def __init__(self, status: str = "OFFLINE", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.set_status(status)

    def set_status(self, status: str, custom_text: Optional[str] = None) -> None:
        normalized = str(status or "OFFLINE").upper()
        foreground, dot = self.STYLES.get(
            normalized, self.STYLES["OFFLINE"]
        )
        display_text = custom_text if custom_text else "{} {}".format(dot, normalized.title().replace("_", " "))
        self.setText(display_text)
        self.setAccessibleName("Status: {}".format(normalized))
        self.setStyleSheet(
            "QLabel { color: %s; background-color: transparent; border: none; "
            "font-weight: 500; padding: 0 4px; font-size: 12px; "
            "letter-spacing: 0.2px; font-family: 'Inter', system-ui, sans-serif; }"
            % foreground
        )


class InfoGrid(QWidget):
    """High-contrast key/value metadata grid for VFX job and worker properties."""

    def __init__(self, fields: Iterable[Tuple[str, str]], columns: int = 2, parent=None):
        super().__init__(parent)
        self._labels = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        for idx, (key, label) in enumerate(fields):
            row = idx // columns
            col = (idx % columns) * 2

            k_lbl = QLabel(label)
            k_lbl.setObjectName("InfoKey")
            # #8896B3 = 5.0:1 on dark surface — passes WCAG AA
            k_lbl.setStyleSheet("font-weight: 500; font-size: 13px; color: #8896B3;")
            v_lbl = QLabel("—")
            v_lbl.setObjectName("InfoValue")
            v_lbl.setStyleSheet("font-weight: 500; font-size: 13px; color: #F5F7FA; font-family: 'JetBrains Mono', Consolas, monospace;")
            v_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

            grid.addWidget(k_lbl, row, col)
            grid.addWidget(v_lbl, row, col + 1)
            self._labels[key] = v_lbl

    def set_value(self, key: str, value: Any) -> None:
        lbl = self._labels.get(key)
        if lbl is not None:
            lbl.setText(str(value) if value is not None and str(value) != "" else "—")

    def set_values(self, data: Mapping[str, Any]) -> None:
        for k, v in data.items():
            self.set_value(k, v)


class PathBox(QWidget):
    """Path display widget with integrated single-click copy action."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label_text = label
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title_label = QLabel(label)
        self.title_label.setObjectName("InfoKey")
        # #A1A7BB = 6.2:1 on dark — passes WCAG AA
        self.title_label.setStyleSheet("font-weight: 500; font-size: 13px; color: #A1A7BB;")
        header.addWidget(self.title_label)
        header.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("SecondaryBtn")
        self.copy_btn.setIcon(get_icon("copy", "#CBD5E1", 12))
        self.copy_btn.setFixedHeight(26)
        self.copy_btn.setStyleSheet("min-height: 26px; max-height: 26px; padding: 0 10px; font-size: 12px;")
        self.copy_btn.setAccessibleName("Copy {}".format(label))
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        header.addWidget(self.copy_btn)
        layout.addLayout(header)

        self.path_label = QLabel("—")
        self.path_label.setObjectName("LogPreview")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_label.setWordWrap(True)
        self.path_label.setMinimumHeight(30)
        layout.addWidget(self.path_label)

    def set_path(self, path: str) -> None:
        text = str(path or "—")
        self.path_label.setText(text)
        self.path_label.setToolTip(text)

    def copy_to_clipboard(self) -> None:
        text = self.path_label.text().strip()
        if text and text != "—":
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("Copied!")
            self.copy_btn.setIcon(get_icon("check", "#3DDC84", 11))
            QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self) -> None:
        self.copy_btn.setText("Copy")
        self.copy_btn.setIcon(get_icon("copy", "#CBD5E1", 11))


class EmptyState(QFrame):
    """Modern Shadcn-styled empty state container matching the Next.js frontend design language."""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setObjectName("EmptyHeroCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 32, 36, 32)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setSpacing(0)

        # 1. Circular Glow Icon Badge
        self.icon_badge = QFrame()
        self.icon_badge.setObjectName("EmptyIconBadge")
        self.icon_badge.setFixedSize(58, 58)
        badge_layout = QVBoxLayout(self.icon_badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(get_icon("info", "#A78BFA", 28).pixmap(28, 28))
        badge_layout.addWidget(self.icon_label)

        icon_row = QHBoxLayout()
        icon_row.setAlignment(Qt.AlignCenter)
        icon_row.addWidget(self.icon_badge)
        main_layout.addLayout(icon_row)
        main_layout.addSpacing(16)

        # 2. Hero Typography
        self.title_label = QLabel(title)
        self.title_label.setObjectName("EmptyHeroTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)
        main_layout.addSpacing(8)

        self.message_label = QLabel(message)
        self.message_label.setObjectName("EmptyHeroMessage")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumWidth(460)
        main_layout.addWidget(self.message_label)

    def set_content(self, title: str, message: str, status_mode: str = "OFFLINE") -> None:
        self.title_label.setText(title)
        self.message_label.setText(message)
        mode = status_mode.upper()
        if mode in ("ONLINE", "WAITING", "POLLING", "RENDERING"):
            self.icon_badge.setStyleSheet(
                "#EmptyIconBadge { background-color: rgba(74, 222, 128, 0.12); border: 1px solid rgba(74, 222, 128, 0.35); border-radius: 29px; }"
            )
            self.icon_label.setPixmap(get_icon("radio", "#4ADE80", 28).pixmap(28, 28))
        elif mode == "PAUSED":
            self.icon_badge.setStyleSheet(
                "#EmptyIconBadge { background-color: rgba(251, 191, 36, 0.12); border: 1px solid rgba(251, 191, 36, 0.35); border-radius: 29px; }"
            )
            self.icon_label.setPixmap(get_icon("pause", "#FBBF24", 28).pixmap(28, 28))
        else:  # OFFLINE / ERROR
            self.icon_badge.setStyleSheet(
                "#EmptyIconBadge { background-color: rgba(139, 92, 246, 0.12); border: 1px solid rgba(139, 92, 246, 0.35); border-radius: 29px; }"
            )
            self.icon_label.setPixmap(get_icon("info", "#A78BFA", 28).pixmap(28, 28))

    def set_metadata(self, hostname: str = "", dccs: str = "", endpoint: str = "") -> None:
        pass
