"""RenderHive Worker visual theme."""

APP_STYLESHEET = r"""
QWidget {
    background-color: #0b0e14;
    color: #eef1f7;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 12px;
}
QMainWindow, QDialog { background-color: #0b0e14; }
QToolTip {
    background-color: #181d29;
    color: #f5f7fb;
    border: 1px solid #32394a;
    padding: 6px;
}
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#HeaderCard,
QFrame#SectionCard,
QFrame#StatCard,
QFrame#MetricCard,
QFrame#EmptyCard {
    background-color: #121722;
    border: 1px solid #262d3c;
    border-radius: 10px;
}
QFrame#Sidebar {
    background-color: #0e121b;
    border-right: 1px solid #242b39;
}
QLabel#TitleLabel { font-size: 18px; font-weight: 700; color: #ffffff; }
QLabel#PageTitle { font-size: 19px; font-weight: 700; color: #ffffff; }
QLabel#SectionTitle { font-size: 13px; font-weight: 700; color: #f7f8fb; }
QLabel#CardValue { font-size: 18px; font-weight: 700; color: #ffffff; }
QLabel#CardCaption,
QLabel#MutedLabel,
QLabel#FieldLabel { color: #9199aa; }
QLabel#FieldLabel { font-size: 11px; font-weight: 600; }
QLabel#FieldValue { color: #e7eaf0; font-weight: 500; }
QLabel#MonoValue { color: #dfe4ef; font-family: Consolas, 'Cascadia Mono', monospace; }
QLabel#AccentLabel { color: #b891ff; font-weight: 700; }
QLabel#SuccessLabel { color: #46d98b; font-weight: 700; }
QLabel#WarningLabel { color: #f2b84b; font-weight: 700; }
QLabel#DangerLabel { color: #ff6b75; font-weight: 700; }
QPushButton {
    min-height: 34px;
    background-color: #6d32c8;
    color: #ffffff;
    border: 1px solid #7d42d8;
    border-radius: 7px;
    padding: 0 14px;
    font-weight: 650;
}
QPushButton:hover { background-color: #7a3bdd; border-color: #8f56ec; }
QPushButton:pressed { background-color: #5d27af; }
QPushButton:disabled { background-color: #171c27; color: #60697a; border-color: #242b39; }
QPushButton#SecondaryBtn {
    background-color: #171d28;
    color: #e9ecf2;
    border: 1px solid #30384a;
}
QPushButton#SecondaryBtn:hover { background-color: #202838; border-color: #414b61; }
QPushButton#DestructiveBtn {
    background-color: #c93442;
    border-color: #dc4a57;
}
QPushButton#DestructiveBtn:hover { background-color: #dc3e4d; }
QPushButton#GhostBtn {
    background-color: transparent;
    color: #aeb5c4;
    border: 1px solid transparent;
}
QPushButton#GhostBtn:hover { background-color: #181e2a; color: #ffffff; }
QPushButton#NavButton {
    min-height: 40px;
    text-align: left;
    padding-left: 15px;
    background-color: transparent;
    color: #9ca5b6;
    border: none;
    border-radius: 7px;
}
QPushButton#NavButton:hover { background-color: #171d29; color: #ffffff; }
QPushButton#NavButton:checked {
    background-color: #271744;
    color: #d9c4ff;
    border-left: 3px solid #8b4ee8;
    padding-left: 12px;
}
QLineEdit, QComboBox, QSpinBox {
    min-height: 34px;
    background-color: #111722;
    color: #eef1f7;
    border: 1px solid #30384a;
    border-radius: 7px;
    padding: 0 10px;
    selection-background-color: #6d32c8;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #8150d9; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background-color: #151b26;
    color: #eef1f7;
    border: 1px solid #323a4c;
    selection-background-color: #5c2ba6;
}
QTextEdit, QPlainTextEdit {
    background-color: #0e131c;
    color: #aeb7c8;
    border: 1px solid #2a3141;
    border-radius: 8px;
    padding: 9px;
    font-family: Consolas, 'Cascadia Mono', monospace;
    font-size: 11px;
    selection-background-color: #5c2ba6;
}
QProgressBar {
    min-height: 9px;
    max-height: 9px;
    border: none;
    border-radius: 4px;
    background-color: #252c3a;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background-color: #7c43d7; border-radius: 4px; }
QTableWidget {
    background-color: #10151f;
    alternate-background-color: #131a25;
    color: #e7eaf0;
    border: 1px solid #2a3141;
    border-radius: 8px;
    gridline-color: #202736;
    selection-background-color: #332052;
    selection-color: #ffffff;
}
QTableWidget::item { padding: 6px; }
QHeaderView::section {
    background-color: #1b2230;
    color: #aeb6c5;
    padding: 7px;
    border: none;
    border-right: 1px solid #2c3444;
    font-weight: 650;
}
QTabWidget::pane { border: none; }
QCheckBox { color: #dce1eb; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #3a4355;
    border-radius: 4px;
    background-color: #111722;
}
QCheckBox::indicator:checked { background-color: #7040c4; border-color: #8b5bdd; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #343c4d; min-height: 28px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #343c4d; min-width: 28px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""
