"""Validation rules and severity control dialog for RenderHive Houdini Submitter."""

from __future__ import absolute_import

from renderhive_houdini.ui.qt_compat import QtCore, QtGui, QtWidgets, dialog_exec
from renderhive_houdini.ui.widgets import SectionCard, ScrollFilter
from renderhive_houdini.ui.icons import get_icon
from renderhive_houdini.ui.theme import COLORS, stylesheet
from renderhive_houdini.validation.validator import KNOWN_HOUDINI_RULES, RULE_PROFILES


class ValidationRulesDialog(QtWidgets.QDialog):
    """Configures rule severities, profiles, and override rules for scene validation."""

    def __init__(self, current_overrides=None, parent=None):
        super(ValidationRulesDialog, self).__init__(parent)
        self.setObjectName("RenderHiveDialog")
        self.setWindowTitle("RenderHive — Validation Rules & Severity Control")
        self.setMinimumSize(740, 560)
        self.resize(780, 620)
        self.setModal(True)

        pal = self.palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor("#080A0E"))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor("#080A0E"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setStyleSheet(stylesheet())

        self.rule_overrides = dict(current_overrides or {})
        self.rule_combos = {}

        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header (#0B0E17 matching DWM Titlebar & Settings Dialog) ──
        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("DialogHeader")
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 18, 24, 18)
        header_layout.setSpacing(3)

        title = QtWidgets.QLabel("Validation Rules & Severity Control")
        title.setObjectName("PageTitle")
        subtitle = QtWidgets.QLabel(
            "Customize how scene checks are enforced in Houdini. Errors prevent job submission, "
            "warnings advise artists, and disabled checks are skipped entirely."
        )
        subtitle.setObjectName("MutedLabel")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px; margin-top: 2px;")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header_frame)

        # ── Body Content ──
        body_widget = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 16, 24, 16)
        body_layout.setSpacing(12)

        # Presets Bar
        preset_card = SectionCard("RULE PRESETS", "Quickly apply standard studio enforcement profiles")
        preset_row = QtWidgets.QHBoxLayout()
        preset_row.setSpacing(8)

        btn_std = QtWidgets.QPushButton("Standard (Default)")
        btn_std.setObjectName("SecondaryBtn")
        btn_std.setCursor(QtCore.Qt.PointingHandCursor)
        btn_std.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_std.clicked.connect(lambda: self._apply_profile("standard"))

        btn_strict = QtWidgets.QPushButton("Studio Strict")
        btn_strict.setObjectName("SecondaryBtn")
        btn_strict.setCursor(QtCore.Qt.PointingHandCursor)
        btn_strict.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_strict.clicked.connect(lambda: self._apply_profile("studio_strict"))

        btn_lookdev = QtWidgets.QPushButton("LookDev / Relaxed")
        btn_lookdev.setObjectName("SecondaryBtn")
        btn_lookdev.setCursor(QtCore.Qt.PointingHandCursor)
        btn_lookdev.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_lookdev.clicked.connect(lambda: self._apply_profile("lookdev"))

        preset_row.addWidget(btn_std)
        preset_row.addWidget(btn_strict)
        preset_row.addWidget(btn_lookdev)
        preset_row.addStretch()
        preset_card.add_layout(preset_row)
        body_layout.addWidget(preset_card)

        # Rule Tree Table
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("RulesTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Validation Check / Rule", "Category", "Severity"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.tree.setColumnWidth(2, 195)

        self._populate_rules()
        body_layout.addWidget(self.tree, 1)

        root.addWidget(body_widget, 1)

        # ── Full-Width Divider above action buttons ──
        actions_divider = QtWidgets.QFrame()
        actions_divider.setObjectName("SheetDivider")
        actions_divider.setFixedHeight(1)
        root.addWidget(actions_divider)

        # ── Full-Width Dialog Footer (#0B0E17 matching DWM Titlebar & Settings Dialog) ──
        footer_frame = QtWidgets.QFrame()
        footer_frame.setObjectName("DialogFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(8)

        reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        reset_btn.setObjectName("GhostBtn")
        reset_btn.setCursor(QtCore.Qt.PointingHandCursor)
        reset_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        reset_btn.clicked.connect(self._reset_factory_defaults)
        footer_layout.addWidget(reset_btn)

        footer_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        save_btn = QtWidgets.QPushButton("  Save Changes")
        save_btn.setObjectName("SubmitButton")
        save_btn.setIcon(get_icon("check", COLORS["primary_fg"], 13))
        save_btn.setCursor(QtCore.Qt.PointingHandCursor)
        save_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        save_btn.setFixedHeight(30)
        save_btn.setMinimumWidth(130)
        save_btn.clicked.connect(self._save_and_accept)
        footer_layout.addWidget(save_btn)

        root.addWidget(footer_frame)

    def _populate_rules(self):
        self.tree.clear()
        self.rule_combos.clear()

        for code, category, desc, default_sev in KNOWN_HOUDINI_RULES:
            item = QtWidgets.QTreeWidgetItem([desc, category, ""])
            item.setData(0, QtCore.Qt.UserRole, code)
            item.setSizeHint(0, QtCore.QSize(0, 28))
            item.setSizeHint(1, QtCore.QSize(0, 28))
            item.setSizeHint(2, QtCore.QSize(0, 28))
            item.setTextAlignment(0, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            item.setTextAlignment(1, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            self.tree.addTopLevelItem(item)

            combo = QtWidgets.QComboBox()
            combo.setObjectName("SeverityCombo")
            combo.setCursor(QtCore.Qt.PointingHandCursor)
            ScrollFilter.install(combo)
            combo.addItems(["Required (Error)", "Optional (Warning)", "Advisory (Info)", "Disabled (Ignore)"])

            current_val = self.rule_overrides.get(code, default_sev).upper()
            if current_val == "ERROR":
                combo.setCurrentIndex(0)
            elif current_val == "WARNING":
                combo.setCurrentIndex(1)
            elif current_val == "INFO":
                combo.setCurrentIndex(2)
            elif current_val in ("DISABLED", "IGNORE", "OFF"):
                combo.setCurrentIndex(3)
            else:
                combo.setCurrentIndex(0)

            self.rule_combos[code] = combo

            cell_container = QtWidgets.QWidget()
            cell_layout = QtWidgets.QHBoxLayout(cell_container)
            cell_layout.setContentsMargins(2, 0, 2, 0)
            cell_layout.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            cell_layout.addWidget(combo)
            self.tree.setItemWidget(item, 2, cell_container)

    def _apply_profile(self, profile_name):
        prof = RULE_PROFILES.get(profile_name, {})
        overrides = prof.get("overrides", {})

        for code, combo in self.rule_combos.items():
            target_sev = overrides.get(code)
            if not target_sev:
                for c, cat, desc, def_sev in KNOWN_HOUDINI_RULES:
                    if c == code:
                        target_sev = def_sev
                        break

            target_sev = (target_sev or "ERROR").upper()
            if target_sev == "ERROR":
                combo.setCurrentIndex(0)
            elif target_sev == "WARNING":
                combo.setCurrentIndex(1)
            elif target_sev == "INFO":
                combo.setCurrentIndex(2)
            elif target_sev in ("DISABLED", "IGNORE", "OFF"):
                combo.setCurrentIndex(3)

    def _reset_factory_defaults(self):
        self.rule_overrides.clear()
        self._populate_rules()

    def _save_and_accept(self):
        self.rule_overrides = {}
        for code, combo in self.rule_combos.items():
            idx = combo.currentIndex()
            if idx == 0:
                self.rule_overrides[code] = "ERROR"
            elif idx == 1:
                self.rule_overrides[code] = "WARNING"
            elif idx == 2:
                self.rule_overrides[code] = "INFO"
            elif idx == 3:
                self.rule_overrides[code] = "DISABLED"

        self.accept()

    def showEvent(self, event):
        super(ValidationRulesDialog, self).showEvent(event)
        self._apply_window_theme()

    def _apply_window_theme(self):
        import sys
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
