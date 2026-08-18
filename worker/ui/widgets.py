"""Reusable widgets for the RenderHive Worker dashboard."""

from __future__ import annotations

from typing import Iterable, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SectionCard(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("SectionCard")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(11, 9, 11, 10)
        self.root.setSpacing(8)

        if title or subtitle:
            header = QVBoxLayout()
            header.setSpacing(2)
            if title:
                title_label = QLabel(title)
                title_label.setObjectName("SectionTitle")
                header.addWidget(title_label)
            if subtitle:
                subtitle_label = QLabel(subtitle)
                subtitle_label.setObjectName("MutedLabel")
                subtitle_label.setWordWrap(True)
                header.addWidget(subtitle_label)
            self.root.addLayout(header)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.root.addWidget(widget, stretch)

    def add_layout(self, layout, stretch: int = 0) -> None:
        self.root.addLayout(layout, stretch)


class StatCard(QFrame):
    def __init__(self, caption: str, value: str = "—", detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(2)

        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("CardCaption")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("MutedLabel")
        self.detail_label.setWordWrap(True)

        layout.addWidget(self.caption_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)
        layout.addStretch()

    def set_value(self, value: object, detail: str | None = None) -> None:
        self.value_label.setText(str(value if value not in (None, "") else "—"))
        if detail is not None:
            self.detail_label.setText(detail)


class ResourceMeter(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 8)
        layout.setSpacing(5)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("FieldLabel")
        self.value_label = QLabel("0%")
        self.value_label.setObjectName("FieldValue")
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.value_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.detail_label = QLabel("—")
        self.detail_label.setObjectName("MutedLabel")

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
    COLORS = {
        "OFFLINE": ("#8d96a8", "#202631", "#31394a"),
        "ONLINE": ("#4ce095", "#11291f", "#24573e"),
        "RENDERING": ("#f1bd59", "#2d2413", "#5b4822"),
        "PAUSED": ("#c7a2ff", "#261b3b", "#523878"),
        "ERROR": ("#ff7881", "#351a1e", "#71313a"),
        "CONNECTED": ("#4ce095", "#11291f", "#24573e"),
        "DISCONNECTED": ("#ff7881", "#351a1e", "#71313a"),
    }

    def __init__(self, status: str = "OFFLINE", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(24)
        self.setContentsMargins(10, 0, 10, 0)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        normalized = str(status or "OFFLINE").upper()
        foreground, background, border = self.COLORS.get(
            normalized, self.COLORS["OFFLINE"]
        )
        self.setText(normalized.replace("_", " "))
        self.setStyleSheet(
            "QLabel { color: %s; background: %s; border: 1px solid %s; "
            "border-radius: 12px; font-weight: 700; padding: 2px 9px; }"
            % (foreground, background, border)
        )


class NavButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)


class InfoGrid(QWidget):
    def __init__(self, fields: Iterable[Tuple[str, str]], columns: int = 2, parent=None):
        super().__init__(parent)
        self._labels = {}
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        fields_list: List[Tuple[str, str]] = list(fields)
        columns = max(1, int(columns))

        for index, (key, caption) in enumerate(fields_list):
            column = index % columns
            row = (index // columns) * 2
            label = QLabel(caption)
            label.setObjectName("FieldLabel")
            value = QLabel("—")
            value.setObjectName("FieldValue")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(label, row, column)
            grid.addWidget(value, row + 1, column)
            self._labels[key] = value

        for column in range(columns):
            grid.setColumnStretch(column, 1)

    def set_value(self, key: str, value: object) -> None:
        label = self._labels.get(key)
        if label is None:
            return
        text = str(value if value not in (None, "") else "—")
        label.setText(text)
        label.setToolTip(text)

    def set_values(self, values: dict) -> None:
        for key, value in values.items():
            self.set_value(key, value)

    def value_label(self, key: str):
        return self._labels.get(key)


class EmptyState(QFrame):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setObjectName("EmptyCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        icon_label = QLabel("◇")
        icon_label.setObjectName("EmptyStateIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("EmptyStateTitle")
        title_label.setAlignment(Qt.AlignCenter)
        message_label = QLabel(message)
        message_label.setObjectName("EmptyStateMessage")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setMaximumWidth(310)
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(message_label)
