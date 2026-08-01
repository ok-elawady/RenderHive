"""Maya-parity RenderHive theme for Houdini Qt5 and Qt6 builds."""

COLORS = {
    "background": "#10131A",
    "surface": "#181D28",
    "surface2": "#202635",
    "surface3": "#2A3244",
    "border": "#364055",
    "divider": "#2B3447",
    "primary": "#5A1FA6",
    "hover": "#6C2AC4",
    "active": "#7A39D9",
    "light": "#9C73F2",
    "text": "#F5F7FA",
    "secondary": "#B7BDC9",
    "muted": "#8A92A5",
    "disabled": "#5C6372",
    "info": "#4DA3FF",
    "success": "#3DDC84",
    "warning": "#FFB84D",
    "error": "#FF5D73",
    "terminal": "#0D1118",
}


def stylesheet():
    return r"""
    QWidget {
        background-color: %(background)s;
        color: %(text)s;
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 11px;
    }
    QLabel { background: transparent; border: none; }
    QToolTip {
        background-color: #252C3B;
        color: %(text)s;
        border: 1px solid %(border)s;
        padding: 6px 8px;
        font-size: 10px;
    }
    QFrame#HeaderCard, QFrame#Card, QFrame#FooterCard, QFrame#Sidebar {
        background-color: %(surface)s;
        border: 1px solid %(border)s;
        border-radius: 10px;
    }
    QFrame#HeaderCard { border-top: 2px solid %(primary)s; }
    QLabel#BrandMain, QLabel#BrandAccent {
        font-size: 19px;
        font-weight: 700;
        letter-spacing: 1px;
    }
    QLabel#BrandAccent { color: %(light)s; }
    QLabel#BrandSubtitle {
        color: %(muted)s;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1px;
    }
    QLabel#SceneMeta { color: %(muted)s; font-size: 10px; }
    QLabel#PageTitle { font-size: 17px; font-weight: 700; }
    QLabel#SectionTitle { font-size: 12px; font-weight: 700; }
    QLabel#FieldLabel { color: %(secondary)s; font-size: 10px; font-weight: 600; }
    QLabel#ReadOnlyValue {
        background-color: #151A24;
        color: %(text)s;
        border: 1px solid %(divider)s;
        border-radius: 7px;
        min-height: 31px;
        padding: 6px 9px;
    }
    QLabel#MetaChip {
        background-color: %(surface2)s;
        border: 1px solid %(divider)s;
        border-radius: 10px;
        color: %(secondary)s;
        padding: 3px 8px;
        font-size: 10px;
        font-weight: 600;
    }
    QToolButton#InfoTipButton {
        background-color: %(surface2)s;
        color: %(muted)s;
        border: 1px solid %(divider)s;
        border-radius: 8px;
        font-size: 10px;
        font-weight: 700;
        padding: 0;
    }
    QToolButton#InfoTipButton:hover {
        color: %(text)s;
        border-color: %(light)s;
        background-color: %(surface3)s;
    }
    QPushButton#NavButton {
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
        color: %(muted)s;
        min-height: 42px;
        padding: 0 11px;
        text-align: left;
        font-weight: 600;
    }
    QPushButton#NavButton:hover { color: %(text)s; background-color: %(surface2)s; }
    QPushButton#NavButton:checked {
        color: %(text)s;
        background-color: #24193D;
        border-left: 3px solid %(active)s;
    }
    QPushButton {
        background-color: %(surface2)s;
        color: %(text)s;
        border: 1px solid %(border)s;
        border-radius: 7px;
        min-height: 31px;
        padding: 0 12px;
        font-weight: 600;
    }
    QPushButton:hover { border-color: %(light)s; background-color: %(surface3)s; }
    QPushButton#PrimaryButton, QPushButton#SubmitButton {
        background-color: %(primary)s;
        border-color: %(primary)s;
        color: white;
    }
    QPushButton#PrimaryButton:hover, QPushButton#SubmitButton:hover {
        background-color: %(hover)s;
    }
    QPushButton:disabled {
        color: %(disabled)s;
        background-color: #151923;
        border-color: %(divider)s;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
        background-color: #151A24;
        color: %(text)s;
        border: 1px solid %(border)s;
        border-radius: 7px;
        min-height: 31px;
        padding: 0 10px;
        selection-background-color: %(primary)s;
    }
    QTextEdit { padding: 7px 9px; }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {
        border-color: %(hover)s;
        background-color: %(surface2)s;
    }
    QComboBox::drop-down {
        width: 28px;
        border: none;
        border-left: 1px solid %(divider)s;
        background-color: %(surface2)s;
    }
    QComboBox QAbstractItemView {
        background-color: %(surface2)s;
        color: %(text)s;
        border: 1px solid %(border)s;
        selection-background-color: %(primary)s;
    }
    QCheckBox { spacing: 7px; color: %(secondary)s; }
    QCheckBox::indicator {
        width: 17px; height: 17px;
        border: 1px solid %(border)s;
        border-radius: 4px;
        background-color: #151A24;
    }
    QCheckBox::indicator:checked {
        background-color: %(primary)s;
        border-color: %(light)s;
    }
    QTreeWidget {
        background-color: %(terminal)s;
        border: 1px solid %(border)s;
        border-radius: 7px;
        alternate-background-color: #141923;
    }
    QTreeWidget::item {
        min-height: 26px;
        padding: 2px 5px;
    }
    QTreeWidget::item:selected {
        background-color: %(primary)s;
        color: %(text)s;
    }
    QTreeWidget::indicator {
        width: 16px;
        height: 16px;
    }
    QTreeWidget::indicator:unchecked {
        background-color: #151A24;
        border: 1px solid %(border)s;
        border-radius: 3px;
    }
    QTreeWidget::indicator:checked {
        background-color: %(primary)s;
        border: 1px solid %(light)s;
        border-radius: 3px;
    }
    QHeaderView::section {
        background-color: %(surface2)s;
        color: %(secondary)s;
        border: none;
        border-bottom: 1px solid %(border)s;
        padding: 7px 8px;
        font-weight: 600;
    }
    QPlainTextEdit {
        background-color: %(terminal)s;
        border: 1px solid %(border)s;
        border-radius: 7px;
        color: %(secondary)s;
        font-family: Consolas, monospace;
        padding: 8px;
    }
    QLabel#InlineStatus { padding: 4px 2px; }
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 2px;
    }
    QScrollBar::handle:vertical {
        background: %(surface3)s;
        min-height: 30px;
        border-radius: 4px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """ % COLORS
