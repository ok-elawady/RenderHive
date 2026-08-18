"""Compact production theme for the RenderHive Worker."""

APP_STYLESHEET = r"""
QWidget {
    background-color: transparent;
    color: #eef1f7;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
}
QMainWindow, QDialog, QWidget#RootWidget { background-color: #0b0e14; }
QWidget#PageRoot, QWidget#EmptyStatePage, QStackedWidget#JobStateStack { background-color: transparent; }
QLabel { background-color: transparent; border: none; }
QLabel#BrandLogo { background-color: transparent; border: none; padding: 0; }
QToolTip {
    background-color: #181d29;
    color: #f5f7fb;
    border: 1px solid #32394a;
    padding: 6px 8px;
}
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }

QFrame#HeaderCard,
QFrame#SectionCard,
QFrame#StatCard,
QFrame#MetricCard,
QFrame#CommandBar,
QFrame#LogDrawer {
    background-color: #121722;
    border: 1px solid #262d3c;
    border-radius: 8px;
}
QFrame#HeaderCard { border-top: 2px solid #7840d4; }
QFrame#EmptyCard {
    background-color: #151b27;
    border: 1px solid #2a3242;
    border-radius: 10px;
}
QLabel#EmptyStateIcon {
    color: #a77aff;
    font-size: 23px;
    font-weight: 700;
}
QLabel#EmptyStateTitle {
    color: #f7f8fb;
    font-size: 14px;
    font-weight: 700;
}
QLabel#EmptyStateMessage {
    color: #9ba4b5;
    font-size: 11px;
}
QFrame#CommandBar { background-color: #10151f; }
QFrame#LogDrawer { background-color: #0e131c; }

QLabel#TitleLabel { font-size: 14px; font-weight: 700; color: #ffffff; }
QLabel#PageTitle { font-size: 16px; font-weight: 700; color: #ffffff; }
QLabel#SectionTitle { font-size: 12px; font-weight: 700; color: #f7f8fb; }
QLabel#CardValue { font-size: 15px; font-weight: 700; color: #ffffff; }
QLabel#CardCaption,
QLabel#MutedLabel,
QLabel#FieldLabel { color: #9199aa; }
QLabel#FieldLabel { font-size: 10px; font-weight: 600; }
QLabel#FieldValue { color: #e7eaf0; font-weight: 500; }
QLabel#MonoValue { color: #dfe4ef; font-family: Consolas, monospace; }
QLabel#CompactBadge {
    color: #c2c9d6;
    background-color: #171d28;
    border: 1px solid #252d3c;
    border-radius: 6px;
    padding: 4px 8px;
}
QLabel#SchedulerHint { color: #aeb6c5; padding: 0 3px; }
QLabel#LogPreview {
    color: #aeb6c5;
    background-color: #151b26;
    border: 1px solid #202837;
    border-radius: 6px;
    padding: 5px 8px;
}
QLabel#VersionLabel { color: #9aa3b4; font-size: 10px; padding: 0 2px; }
QLabel#AccentLabel { color: #b891ff; font-weight: 700; }
QLabel#ProgressPercent {
    color: #ffffff;
    background-color: #25183d;
    border: 1px solid #7040c4;
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#SuccessLabel { color: #46d98b; font-weight: 700; }
QLabel#WarningLabel { color: #f2b84b; font-weight: 700; }
QLabel#DangerLabel { color: #ff6b75; font-weight: 700; }

QPushButton {
    min-height: 28px;
    background-color: #6d32c8;
    color: #ffffff;
    border: 1px solid #7d42d8;
    border-radius: 6px;
    padding: 0 11px;
    font-weight: 600;
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
QPushButton#DestructiveBtn { background-color: #b82f3d; border-color: #cf4250; }
QPushButton#DestructiveBtn:hover { background-color: #cf3948; }
QPushButton#GhostBtn {
    background-color: transparent;
    color: #aeb5c4;
    border: 1px solid #30384a;
}
QPushButton#GhostBtn:hover { background-color: #181e2a; color: #ffffff; }

QLineEdit, QComboBox, QSpinBox {
    min-height: 29px;
    background-color: #111722;
    color: #eef1f7;
    border: 1px solid #30384a;
    border-radius: 6px;
    padding: 0 9px;
    selection-background-color: #6d32c8;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #8150d9; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background-color: #151b26;
    color: #eef1f7;
    border: 1px solid #323a4c;
    selection-background-color: #5c2ba6;
}

QTextEdit, QPlainTextEdit {
    background-color: #0b1018;
    color: #aeb7c8;
    border: 1px solid #283142;
    border-radius: 6px;
    padding: 7px;
    font-family: Consolas, 'Cascadia Mono', monospace;
    font-size: 10px;
    selection-background-color: #5c2ba6;
}

QProgressBar {
    min-height: 9px;
    max-height: 9px;
    border: none;
    border-radius: 3px;
    background-color: #252c3a;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background-color: #7c43d7; border-radius: 3px; }

QTableWidget {
    background-color: #10151f;
    alternate-background-color: #131a25;
    color: #e7eaf0;
    border: 1px solid #2a3141;
    border-radius: 6px;
    gridline-color: #202736;
    selection-background-color: #332052;
    selection-color: #ffffff;
}
QTableWidget::item { padding: 5px; }
QHeaderView::section {
    background-color: #1b2230;
    color: #aeb6c5;
    padding: 6px;
    border: none;
    border-right: 1px solid #2c3444;
    font-weight: 600;
}

QTabWidget#MainTabs::pane {
    border: 1px solid #2a3242;
    border-radius: 8px;
    background-color: #10151f;
    top: -1px;
}
QTabBar::tab {
    background-color: #121722;
    color: #9099aa;
    border: 1px solid #262d3c;
    padding: 7px 16px;
    min-width: 135px;
}
QTabBar::tab:first { border-top-left-radius: 7px; }
QTabBar::tab:last { border-top-right-radius: 7px; }
QTabBar::tab:selected {
    color: #ffffff;
    background-color: #25183d;
    border-bottom: 2px solid #8b4ee8;
}
QTabBar::tab:hover { color: #ffffff; background-color: #181e2a; }

QCheckBox { color: #dce1eb; spacing: 7px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #3a4355;
    border-radius: 4px;
    background-color: #111722;
}
QCheckBox::indicator:checked { background-color: #7040c4; border-color: #8b5bdd; }

QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #343c4d; min-height: 26px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 9px; margin: 2px; }
QScrollBar::handle:horizontal { background: #343c4d; min-width: 26px; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""
