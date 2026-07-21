from __future__ import print_function

import os


COLORS = {
    "background": "#0E1016",
    "surface": "#171A24",
    "surface2": "#1F2330",
    "surface3": "#2A3040",
    "border": "#343B4D",
    "divider": "#2A3143",
    "primary": "#5A1FA6",
    "hover": "#6C2AC4",
    "active": "#7A39D9",
    "light": "#9C73F2",
    "glow": "#B18CFF",
    "text": "#F5F7FA",
    "secondary": "#B7BDC9",
    "muted": "#8A92A5",
    "disabled": "#5C6372",
    "info": "#4DA3FF",
    "success": "#3DDC84",
    "warning": "#FFB84D",
    "error": "#FF5D73",
    "paused": "#9E8EFF",
    "terminal": "#090B11",
}


def _qss_asset(filename):
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "icons",
        filename
    )
    return path.replace("\\", "/")


def build_stylesheet():
    c = dict(COLORS)
    c.update({
        "combo_down": _qss_asset("combo_down.png"),
        "spin_up": _qss_asset("spin_up.png"),
        "spin_down": _qss_asset("spin_down.png"),
    })
    return r"""
    QWidget {
        background-color: %(background)s;
        color: %(text)s;
        font-family: "Segoe UI";
        font-size: 12px;
    }

    QDialog#RenderHiveWindow {
        background-color: %(background)s;
    }

    QFrame#HeaderCard,
    QFrame#Card,
    QFrame#ActionCard,
    QFrame#DetailsCard {
        background-color: %(surface)s;
        border: 1px solid %(border)s;
        border-radius: 9px;
    }

    QFrame#HeaderCard {
        border-top: 2px solid %(primary)s;
    }

    QLabel#HeaderLogo {
        background-color: transparent;
        border: none;
    }

    QFrame#Sidebar {
        background-color: %(surface)s;
        border: 1px solid %(border)s;
        border-radius: 9px;
    }

    QLabel#BrandMain {
        color: %(text)s;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    QLabel#BrandAccent {
        color: %(light)s;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    QLabel#BrandSubtitle {
        color: %(muted)s;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1px;
    }

    QLabel#PageTitle {
        color: %(text)s;
        font-size: 18px;
        font-weight: 700;
    }

    QLabel#SectionTitle {
        color: %(text)s;
        font-size: 13px;
        font-weight: 700;
    }

    QLabel#SecondaryText {
        color: %(secondary)s;
    }

    QLabel#MutedText,
    QLabel#FieldLabel {
        color: %(muted)s;
    }

    QLabel#FieldLabel {
        font-size: 11px;
        font-weight: 600;
    }

    QLabel#MetaChip {
        background-color: %(surface2)s;
        border: 1px solid %(divider)s;
        border-radius: 9px;
        color: %(secondary)s;
        padding: 3px 8px;
        font-size: 10px;
        font-weight: 600;
    }

    QLabel#StatusDot {
        border-radius: 4px;
        min-width: 8px;
        max-width: 8px;
        min-height: 8px;
        max-height: 8px;
        background-color: %(success)s;
    }

    QLabel#StatusText {
        color: %(secondary)s;
        font-size: 11px;
    }

    QPushButton#NavButton {
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        color: %(muted)s;
        min-height: 40px;
        padding: 0 11px;
        text-align: left;
        font-weight: 600;
    }

    QPushButton#NavButton:hover {
        color: %(text)s;
        background-color: %(surface2)s;
    }

    QPushButton#NavButton:checked {
        color: %(text)s;
        background-color: #24193D;
        border-left: 3px solid %(active)s;
    }

    QLineEdit,
    QSpinBox,
    QComboBox {
        background-color: #161B24;
        color: %(text)s;
        border: 1px solid %(border)s;
        border-radius: 6px;
        min-height: 29px;
        padding: 0 9px;
        selection-background-color: %(primary)s;
    }

    QLineEdit:hover,
    QSpinBox:hover,
    QComboBox:hover {
        border-color: #465066;
    }

    QLineEdit:focus,
    QSpinBox:focus,
    QComboBox:focus {
        border: 1px solid %(hover)s;
        background-color: %(surface2)s;
    }

    QLineEdit:disabled,
    QSpinBox:disabled,
    QComboBox:disabled {
        color: %(disabled)s;
        background-color: #12151D;
        border-color: %(divider)s;
    }

    QComboBox {
        padding-right: 32px;
    }

    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 28px;
        border: none;
        border-left: 1px solid %(divider)s;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
        background-color: %(surface2)s;
    }

    QComboBox::drop-down:hover {
        background-color: %(surface3)s;
        border-left-color: %(border)s;
    }

    QComboBox::down-arrow {
        image: url("%(combo_down)s");
        width: 12px;
        height: 8px;
    }

    QComboBox QAbstractItemView {
        background-color: %(surface2)s;
        color: %(text)s;
        border: 1px solid %(border)s;
        selection-background-color: %(primary)s;
        outline: none;
    }

    QSpinBox,
    QDoubleSpinBox {
        padding-right: 26px;
    }

    QSpinBox::up-button,
    QDoubleSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 22px;
        border: none;
        border-left: 1px solid %(divider)s;
        border-bottom: 1px solid %(divider)s;
        border-top-right-radius: 6px;
        background-color: %(surface2)s;
    }

    QSpinBox::down-button,
    QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 22px;
        border: none;
        border-left: 1px solid %(divider)s;
        border-bottom-right-radius: 6px;
        background-color: %(surface2)s;
    }

    QSpinBox::up-button:hover,
    QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover,
    QDoubleSpinBox::down-button:hover {
        background-color: %(surface3)s;
    }

    QSpinBox::up-button:pressed,
    QSpinBox::down-button:pressed,
    QDoubleSpinBox::up-button:pressed,
    QDoubleSpinBox::down-button:pressed {
        background-color: #24193D;
    }

    QSpinBox::up-arrow,
    QDoubleSpinBox::up-arrow {
        image: url("%(spin_up)s");
        width: 10px;
        height: 6px;
    }

    QSpinBox::down-arrow,
    QDoubleSpinBox::down-arrow {
        image: url("%(spin_down)s");
        width: 10px;
        height: 6px;
    }

    QPushButton {
        background-color: #232939;
        color: %(text)s;
        border: 1px solid #40485D;
        border-radius: 6px;
        min-height: 29px;
        padding: 0 14px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: #2D3447;
        border-color: #505A73;
    }

    QPushButton:pressed {
        background-color: #1C2130;
    }

    QPushButton:disabled {
        color: %(disabled)s;
        background-color: #171A22;
        border-color: %(divider)s;
    }

    QPushButton#PrimaryButton {
        background-color: %(primary)s;
        border-color: %(hover)s;
        min-height: 34px;
    }

    QPushButton#PrimaryButton:hover {
        background-color: %(hover)s;
        border-color: %(light)s;
    }

    QPushButton#PrimaryButton:pressed {
        background-color: #4A1888;
    }

    QPushButton#InfoButton {
        background-color: #203F64;
        border-color: %(info)s;
        min-height: 34px;
    }

    QPushButton#InfoButton:hover {
        background-color: #27517F;
    }

    QPushButton#GhostButton {
        background: transparent;
        color: %(secondary)s;
        border: 1px solid %(divider)s;
    }

    QPushButton#GhostButton:hover {
        color: %(text)s;
        border-color: %(border)s;
        background-color: %(surface2)s;
    }

    QPushButton#IconButton {
        background-color: %(surface2)s;
        border: 1px solid %(border)s;
        border-radius: 6px;
        min-width: 34px;
        max-width: 34px;
        padding: 0;
        font-size: 15px;
    }

    QPushButton#DangerQuiet {
        background: transparent;
        color: %(muted)s;
        border: 1px solid %(divider)s;
    }

    QPushButton#DangerQuiet:hover {
        color: %(error)s;
        border-color: %(error)s;
        background-color: #2A1720;
    }

    QPushButton#CounterCard {
        background-color: %(surface2)s;
        border: 1px solid %(border)s;
        border-top: 3px solid %(muted)s;
        border-radius: 7px;
        min-height: 44px;
        padding: 4px;
        font-weight: 700;
    }

    QPushButton#CounterCard:hover {
        background-color: %(surface3)s;
    }

    QTreeWidget {
        background-color: %(terminal)s;
        alternate-background-color: #0D1017;
        color: %(secondary)s;
        border: 1px solid %(border)s;
        border-radius: 7px;
        outline: none;
        gridline-color: %(divider)s;
    }

    QTreeWidget::item {
        min-height: 30px;
        padding: 2px 5px;
        border-bottom: 1px solid #171B25;
    }

    QTreeWidget::item:hover {
        background-color: %(surface2)s;
    }

    QTreeWidget::item:selected {
        background-color: #24193D;
        color: %(text)s;
    }

    QHeaderView::section {
        background-color: %(surface2)s;
        color: %(secondary)s;
        border: none;
        border-right: 1px solid %(divider)s;
        border-bottom: 1px solid %(border)s;
        padding: 7px 8px;
        font-weight: 600;
    }

    QPlainTextEdit#ActivityLog {
        background-color: %(terminal)s;
        color: #C8D1E1;
        border: 1px solid %(border)s;
        border-radius: 7px;
        padding: 8px;
        font-family: Consolas;
        font-size: 11px;
        selection-background-color: %(primary)s;
    }

    QFrame#FooterBar {
        background-color: %(surface)s;
        border: 1px solid %(border)s;
        border-radius: 9px;
    }

    QProgressBar {
        background-color: %(surface2)s;
        border: 1px solid %(divider)s;
        border-radius: 3px;
        max-height: 5px;
        min-height: 5px;
        text-align: center;
    }

    QProgressBar::chunk {
        background-color: %(primary)s;
        border-radius: 3px;
    }

    QMenu {
        background-color: %(surface2)s;
        color: %(text)s;
        border: 1px solid %(border)s;
        padding: 5px;
    }

    QMenu::item {
        padding: 7px 22px 7px 10px;
        border-radius: 4px;
    }

    QMenu::item:selected {
        background-color: %(primary)s;
    }

    QScrollArea {
        border: none;
        background: transparent;
    }

    QScrollBar:vertical {
        background: %(surface)s;
        width: 10px;
        margin: 0;
    }

    QScrollBar::handle:vertical {
        background: %(surface3)s;
        min-height: 28px;
        border-radius: 5px;
    }

    QScrollBar::handle:vertical:hover {
        background: %(border)s;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0;
    }


    QCheckBox {
        color: %(secondary)s;
        spacing: 7px;
        padding: 3px 0px;
    }

    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid %(border)s;
        background-color: #161B24;
    }

    QCheckBox::indicator:checked {
        background-color: %(primary)s;
        border-color: %(light)s;
    }

    QDialog#TaskPreviewDialog {
        background-color: %(background)s;
    }

    QTabWidget::pane {
        border: 1px solid %(border)s;
        border-radius: 6px;
        background-color: %(surface)s;
        top: -1px;
    }

    QTabBar::tab {
        background-color: %(surface2)s;
        color: %(muted)s;
        border: 1px solid %(border)s;
        padding: 7px 14px;
        min-width: 90px;
    }

    QTabBar::tab:selected {
        color: %(text)s;
        background-color: #24193D;
        border-bottom: 2px solid %(active)s;
    }

    QPlainTextEdit#JsonPreview {
        background-color: %(terminal)s;
        color: #D8DEE9;
        border: none;
        font-family: Consolas, "Courier New";
        font-size: 11px;
        padding: 8px;
    }


    QFrame#SegmentedControl {
        background-color: %(surface2)s;
        border: 1px solid %(border)s;
        border-radius: 7px;
    }

    QPushButton#SegmentButton {
        background-color: transparent;
        border: none;
        border-radius: 5px;
        color: %(muted)s;
        min-height: 28px;
        padding: 0 12px;
        font-weight: 600;
    }

    QPushButton#SegmentButton:hover {
        color: %(text)s;
        background-color: %(surface3)s;
    }

    QPushButton#SegmentButton:checked {
        color: %(text)s;
        background-color: %(primary)s;
    }

    QToolButton#CollapsibleHeader {
        background-color: transparent;
        border: none;
        border-top: 1px solid %(divider)s;
        color: %(secondary)s;
        min-height: 30px;
        padding: 5px 2px;
        text-align: left;
        font-weight: 700;
    }

    QToolButton#CollapsibleHeader:hover {
        color: %(text)s;
        background-color: %(surface2)s;
    }

    QLabel#EligibilitySummary {
        background-color: %(surface2)s;
        border: 1px solid %(divider)s;
        border-radius: 6px;
        color: %(secondary)s;
        padding: 7px 9px;
        font-weight: 600;
    }

    QLabel#PreviewError {
        background-color: #321820;
        color: %(error)s;
        border: 1px solid #6A2735;
        border-radius: 6px;
        padding: 8px 10px;
    }
    """ % c
