"""Modern Dark Studio Production Theme for RenderHive Maya Submitter.

Faithfully mirrors the RenderHive Worker desktop client (worker/ui/theme.py) and
shadcn/ui Web Dashboard design tokens with strict WCAG 2.1 AA/AAA contrast:
- Canvas:  #0E1016  (Deep studio canvas, matches frontend dark bg)
- Surface: #171A24  (Card / raised surface)
- Input:   #080A0F  (VFX console & inset surface)
- Hover:   #1E2536 / #242B3D
- Borders: #283145 (UI borders) & #2A3143 (Card borders)
- Primary: #9C73F2 (Studio Purple, 4.8:1 on dark canvas)
- Text:    #FFFFFF (headers) / #E2E8F0 (body) / #A1A7BB (muted)
- Status:  #4ADE80 (Online) / #FBBF24 (Warn) / #F87171 (Error) / #60A5FA (Info)
"""

from __future__ import absolute_import, print_function

import os


COLORS = {
    # Backgrounds
    "background":    "#080A0E",
    "header_bg":     "#0B0E17",
    "surface":       "#131722",
    "surface2":      "#171A24",
    "surface3":      "#1E2536",
    "surface4":      "#242B3D",
    "surface_input": "#080A0F",
    "terminal":      "#11161F",
    # Borders
    "border":        "#283145",
    "border_card":   "#2A3143",
    "border_strong": "#343B4D",
    "border_focus":  "#9C73F2",
    "divider":       "#1E2536",
    # Brand
    "primary":       "#9C73F2",
    "primary_hover": "#AD8BF5",
    "primary_press": "#7D4EDB",
    "primary_fg":    "#080A0F",
    "accent":        "#C084FC",
    # Text scale
    "text":          "#F8FAFC",
    "text_primary":  "#FFFFFF",
    "secondary":     "#E2E8F0",
    "muted":         "#A1A7BB",
    "disabled":      "#475569",
    # Status
    "success":  "#4ADE80",
    "warning":  "#FBBF24",
    "error":    "#F87171",
    "info":     "#4DA3FF",
    "paused":   "#C084FC",
    # Misc
    "selection_bg": "#4A337A",
    "light":        "#CBD5E1",
    "dark":         "#0B0E17",
}


def _qss_asset(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for sub in ("assets", "icons"):
        path = os.path.join(base_dir, sub, filename)
        if os.path.isfile(path):
            return path.replace("\\", "/")
    return os.path.join(base_dir, "assets", filename).replace("\\", "/")


def stylesheet():
    c = dict(COLORS)
    c.update({
        "combo_down": _qss_asset("chevron_down.svg"),
        "spin_up": _qss_asset("chevron_up.svg"),
        "spin_down": _qss_asset("chevron_down.svg"),
        "check_mark": _qss_asset("check_mark.png"),
    })

    return r"""
    /* ── Global Reset & Accessible Base Typography ── */
    QWidget {
        background-color: transparent;
        color: %(text)s;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
        font-size: 12.5px;
        font-weight: 400;
        selection-background-color: %(selection_bg)s;
        selection-color: %(text_primary)s;
    }

    /* ── Root Submitter & Settings Dialog (Worker Parity) ── */
    QDialog#RenderHiveWindow,
    QWidget#RenderHiveQtSubmitter,
    QDialog#RenderHiveQtSubmitter,
    QWidget#WindowRoot {
        background-color: %(background)s;
        border: none;
        color: %(text)s;
    }

    QDialog#RenderHiveDialog,
    QDialog#SettingsDialog,
    QScrollArea#SettingsScrollArea,
    QWidget#SettingsBody {
        background-color: #080A0E;
        color: #F5F7FA;
    }

    QLabel#SheetSectionTitle {
        color: #94A3B8;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        background-color: transparent;
        border: none;
        padding: 0;
    }

    QFrame#SheetDivider {
        background-color: #202636;
        border: none;
        max-height: 1px;
        min-height: 1px;
        height: 1px;
    }

    QLabel {
        background-color: transparent;
        border: none;
        color: %(text)s;
    }

    QToolTip {
        background-color: #171C28;
        color: #FFFFFF;
        border: 1px solid #3B4764;
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 13px;
        font-weight: 500;
    }

    QScrollArea {
        border: none;
        background: transparent;
    }

    QScrollArea > QWidget > QWidget {
        background: transparent;
    }

    /* ── Top Header Navigation & Action Bar ── */
    QFrame#TopHeaderBar {
        background-color: %(header_bg)s;
        border: none;
        border-bottom: 1px solid %(divider)s;
        border-radius: 0px;
        min-height: 50px;
        max-height: 50px;
    }

    QLabel#HeaderBrand {
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: #FFFFFF;
    }

    QLabel#HeaderSubtitle {
        font-size: 12px;
        font-weight: 500;
        color: %(muted)s;
        margin-right: 4px;
    }

    QLabel#HeaderDivider {
        font-size: 13px;
        color: %(border)s;
        margin: 0 4px;
    }

    /* ── Segmented Pill Navigation (Header Tab Bar — matches Frontend Dashboard) ── */
    QFrame#NavSegmentContainer {
        background-color: #111520;
        border: 1px solid #283145;
        border-radius: 6px;
        padding: 2px;
        margin: 0;
        min-height: 30px;
        max-height: 30px;
        height: 30px;
    }

    QPushButton#SegmentNavBtn {
        background-color: transparent;
        color: #94A3B8;
        border: none;
        border-radius: 4px;
        padding: 0 12px;
        margin: 0;
        font-weight: 500;
        font-size: 12px;
        min-height: 24px;
        max-height: 24px;
        height: 24px;
        text-align: center;
        cursor: pointer;
    }

    QPushButton#SegmentNavBtn:hover {
        background-color: rgba(255, 255, 255, 0.06);
        color: #FFFFFF;
    }

    QPushButton#SegmentNavBtn:checked {
        background-color: %(primary)s;
        color: %(primary_fg)s;
        border: none;
        font-weight: 600;
        border-radius: 4px;
    }

    QPushButton#SegmentNavBtn:focus {
        outline: 2px solid %(primary)s;
        outline-offset: -2px;
    }

    /* ── Bottom Status Footer (Taller for action buttons) ── */
    QFrame#BottomStatusBar,
    QFrame#FooterBar {
        background-color: %(header_bg)s;
        border: none;
        border-top: 1px solid %(divider)s;
        border-radius: 0px;
        min-height: 50px;
        max-height: 52px;
    }

    /* ── Dialog Footer (Worker Parity) ── */
    QFrame#DialogFooter {
        background-color: %(header_bg)s;
        border: none;
    }

    /* ── Dialog Header (Worker Parity) ── */
    QFrame#DialogHeader {
        background-color: %(header_bg)s;
        border: none;
        border-bottom: 1px solid %(divider)s;
        border-radius: 0px;
        min-height: 52px;
    }

    QFrame#DialogDivider {
        background-color: %(divider)s;
        border: none;
        max-height: 1px;
    }

    QLabel#StatusBarDcc {
        color: %(secondary)s;
        font-family: 'JetBrains Mono', Consolas, monospace;
        font-size: 12px;
        font-weight: 500;
        padding: 0 4px;
    }

    QLabel#StatusBarDivider {
        color: #334155;
        font-size: 12px;
        margin: 0 2px;
    }

    QLabel#StatusBarHint {
        color: %(muted)s;
        font-size: 12px;
        font-weight: 500;
        padding: 0 4px;
    }

    QPushButton#StatusBarBtn {
        background-color: transparent;
        color: %(secondary)s;
        border: none;
        border-radius: 4px;
        padding: 0 6px;
        min-height: 20px;
        max-height: 20px;
        height: 20px;
        font-size: 12px;
        font-weight: 500;
    }

    QPushButton#StatusBarBtn:hover {
        background-color: %(surface3)s;
        color: %(text_primary)s;
    }

    QPushButton#StatusBarBtn:pressed {
        background-color: %(border)s;
    }

    /* ── Cards and Surfaces ── */
    QFrame#Card,
    QFrame#SectionCard,
    QFrame#StudioCard,
    QFrame#ActionCard,
    QFrame#DetailsCard,
    QFrame#StatCard {
        background-color: %(surface2)s;
        border: 1px solid %(border_card)s;
        border-radius: 8px;
    }

    QFrame#CardHeader {
        background-color: transparent;
        border-bottom: 1px solid %(border_card)s;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }

    QWidget#CardContent {
        background-color: transparent;
    }

    QFrame#HeroCard {
        background-color: %(surface2)s;
        border: 1px solid %(border_strong)s;
        border-radius: 8px;
    }

    QFrame#DCCCard {
        background-color: #11151F;
        border: 1px solid %(surface4)s;
        border-radius: 8px;
    }

    QFrame#EmptyCard {
        background-color: %(surface2)s;
        border: 1px dashed %(border_strong)s;
        border-radius: 8px;
    }

    /* ── Typography Scale (Matching Frontend Dashboard) ── */
    QLabel#PageTitle {
        font-size: 15px;
        font-weight: 700;
        color: %(text_primary)s;
        letter-spacing: -0.2px;
    }

    QLabel#SectionTitle,
    QLabel#CardTitle {
        font-size: 13px;
        font-weight: 600;
        color: %(text_primary)s;
        letter-spacing: -0.1px;
    }

    /* ── Form Layout Input Labels ── */
    QFormLayout QLabel {
        font-size: 12px;
        font-weight: 500;
        color: %(text)s;
        text-transform: none;
        letter-spacing: 0px;
        background-color: transparent;
        border: none;
    }

    QLabel#FieldLabel {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #CBD5E1;
    }

    QLabel#FieldValue {
        color: %(text_primary)s;
        font-weight: 500;
        font-size: 12.5px;
    }

    QLabel#MutedText,
    QLabel#MutedLabel {
        color: %(muted)s;
        font-size: 11.5px;
        font-weight: 400;
    }

    QLabel#SecondaryText {
        background-color: transparent;
        color: %(secondary)s;
        border: none;
    }

    QLabel#CardDescription {
        color: %(muted)s;
        font-size: 11.5px;
        font-weight: 400;
    }

    QLabel#MonoValue,
    QLabel#CompactBadge {
        color: %(text_primary)s;
        background-color: #1F2330;
        border: 1px solid %(border_strong)s;
        border-radius: 4px;
        padding: 0 12px;
        font-size: 12px;
        font-weight: 500;
        font-family: 'JetBrains Mono', Consolas, monospace;
        min-height: 36px;
        max-height: 36px;
        height: 36px;
    }

    QLabel#BrandMain {
        color: %(text_primary)s;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }

    QLabel#BrandAccent {
        color: %(primary)s;
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.3px;
    }

    QLabel#AccentLabel {
        color: %(accent)s;
        font-weight: 600;
        font-size: 13px;
    }

    QLabel#HelpIcon {
        color: %(muted)s;
        font-weight: 700;
        font-size: 10px;
    }

    QLabel#HelpIcon:hover {
        color: %(primary)s;
    }

    /* ── Form Inputs & Text Fields ── */
    QLineEdit {
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        background-color: %(surface_input)s;
        color: %(text_primary)s;
        border: 1px solid %(border)s;
        border-radius: 5px;
        padding: 0 9px;
        selection-background-color: %(selection_bg)s;
        selection-color: %(text_primary)s;
        font-size: 12px;
    }

    QLineEdit:hover {
        border-color: %(border_card)s;
    }

    QLineEdit:focus {
        border: 1px solid %(border_focus)s;
        background-color: #10141E;
    }

    QLineEdit:disabled {
        background-color: #0A0C11;
        color: %(disabled)s;
        border-color: %(divider)s;
    }

    QTextEdit,
    QPlainTextEdit {
        background-color: %(terminal)s;
        color: %(text)s;
        border: 1px solid %(border_card)s;
        border-radius: 6px;
        padding: 8px;
        font-family: 'JetBrains Mono', Consolas, monospace;
        font-size: 12px;
        selection-background-color: %(selection_bg)s;
        selection-color: %(text_primary)s;
    }

    QTextEdit:focus,
    QPlainTextEdit:focus {
        border: 1px solid %(border_focus)s;
    }

    /* ── Stepper Number Input ── */
    QFrame#StepperFrame {
        background-color: %(surface_input)s;
        border: 1px solid %(border)s;
        border-radius: 5px;
        min-height: 30px;
        max-height: 30px;
        height: 30px;
    }

    QFrame#StepperFrame:hover {
        border-color: %(border_card)s;
    }

    QFrame#StepperFrame:focus-within {
        border: 1px solid %(border_focus)s;
        background-color: #10141E;
    }

    QLineEdit#StepperInput {
        background: transparent;
        border: none;
        color: %(text_primary)s;
        font-size: 12px;
        padding: 0 4px;
        min-height: 26px;
        max-height: 26px;
        height: 26px;
    }

    QPushButton#StepperBtn {
        background-color: transparent;
        border: none;
        border-radius: 4px;
        min-width: 26px;
        max-width: 26px;
        width: 26px;
        min-height: 26px;
        max-height: 26px;
        height: 26px;
        padding: 0px;
        margin: 0px;
        color: %(muted)s;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
    }

    QPushButton#StepperBtn:hover {
        background-color: rgba(255, 255, 255, 0.10);
        color: %(text_primary)s;
    }

    QPushButton#StepperBtn:pressed {
        background-color: rgba(156, 115, 242, 0.25);
        color: %(primary)s;
    }

    QPushButton#StepperBtn:disabled {
        background-color: transparent;
        color: %(disabled)s;
    }

    /* ── Standard QSpinBox fallback ── */
    QSpinBox,
    QDoubleSpinBox {
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        background-color: %(surface_input)s;
        color: %(text_primary)s;
        border: 1px solid %(border)s;
        border-radius: 5px;
        padding-left: 9px;
        padding-right: 28px;
        selection-background-color: %(selection_bg)s;
        selection-color: %(text_primary)s;
        font-size: 12px;
    }

    QSpinBox:focus,
    QDoubleSpinBox:focus {
        border: 1px solid %(border_focus)s;
        background-color: #10141E;
    }

    QSpinBox::up-button,
    QDoubleSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 26px;
        height: 16px;
        background-color: #141924;
        border-left: 1px solid %(border)s;
        border-bottom: 1px solid %(border)s;
        border-top-right-radius: 5px;
        padding: 0px;
        margin: 0px;
    }

    QSpinBox::up-button:hover,
    QDoubleSpinBox::up-button:hover {
        background-color: %(surface4)s;
    }

    QSpinBox::up-button:pressed,
    QDoubleSpinBox::up-button:pressed {
        background-color: %(primary)s;
    }

    QSpinBox::up-arrow,
    QDoubleSpinBox::up-arrow {
        image: url("%(spin_up)s");
        width: 11px;
        height: 11px;
    }

    QSpinBox::down-button,
    QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 26px;
        height: 16px;
        background-color: #141924;
        border-left: 1px solid %(border)s;
        border-bottom-right-radius: 5px;
        padding: 0px;
        margin: 0px;
    }

    QSpinBox::down-button:hover,
    QDoubleSpinBox::down-button:hover {
        background-color: %(surface4)s;
    }

    QSpinBox::down-button:pressed,
    QDoubleSpinBox::down-button:pressed {
        background-color: %(primary)s;
    }

    QSpinBox::down-arrow,
    QDoubleSpinBox::down-arrow {
        image: url("%(spin_down)s");
        width: 11px;
        height: 11px;
    }

    /* ── ComboBox ── */
    QComboBox {
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        background-color: %(surface_input)s;
        color: %(text_primary)s;
        border: 1px solid %(border)s;
        border-radius: 5px;
        padding-left: 9px;
        padding-right: 28px;
        selection-background-color: %(selection_bg)s;
        selection-color: %(text_primary)s;
        font-size: 12px;
        cursor: pointer;
    }

    QComboBox:hover {
        border-color: %(border_card)s;
    }

    QComboBox:focus {
        border: 1px solid %(border_focus)s;
        background-color: #10141E;
    }

    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 28px;
        border: none;
        background: transparent;
        margin-right: 4px;
    }

    QComboBox::down-arrow {
        image: url("%(combo_down)s");
        width: 14px;
        height: 14px;
    }

    QComboBox QAbstractItemView {
        background-color: #131722;
        color: %(text_primary)s;
        border: 1px solid %(border)s;
        border-radius: 6px;
        selection-background-color: %(surface4)s;
        selection-color: %(text_primary)s;
        padding: 4px;
        outline: 0px;
    }

    QComboBox QAbstractItemView::item {
        min-height: 26px;
        padding: 4px 10px;
        border-radius: 4px;
        color: %(secondary)s;
        background-color: transparent;
        border: none;
    }

    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {
        background-color: %(surface4)s;
        color: %(text_primary)s;
    }

    QComboBox QAbstractItemView::item:checked {
        background-color: transparent;
        color: %(primary)s;
        font-weight: 600;
    }

    QComboBox QAbstractItemView::indicator {
        width: 0px;
        height: 0px;
        background: transparent;
        border: none;
    }

    /* ── Push Buttons ── */
    QPushButton {
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        background-color: %(primary)s;
        color: %(primary_fg)s;
        border: 1px solid #7D4EDB;
        border-radius: 5px;
        padding: 0 12px;
        margin: 0;
        font-weight: 600;
        font-size: 12px;
        outline: none;
        cursor: pointer;
    }

    QPushButton:hover {
        background-color: %(primary_hover)s;
        border-color: #BEA1F7;
    }

    QPushButton:pressed {
        background-color: %(primary_press)s;
        border-color: %(primary_press)s;
    }

    QPushButton:disabled {
        background-color: rgba(255, 255, 255, 0.02);
        color: %(disabled)s;
        border: 1px solid %(divider)s;
    }

    QPushButton:focus {
        outline: none;
    }

    /* Secondary / Outlined variant */
    QPushButton#SecondaryBtn,
    QPushButton#ValidateButton,
    QPushButton#OutlinedButton {
        background-color: #171C28;
        color: %(text_primary)s;
        border: 1px solid %(border)s;
        border-radius: 5px;
        margin: 0;
        font-weight: 500;
        font-size: 12px;
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        padding: 0 12px;
        cursor: pointer;
    }

    QPushButton#SecondaryBtn:hover,
    QPushButton#ValidateButton:hover,
    QPushButton#OutlinedButton:hover {
        background-color: #202738;
        border-color: #3B4764;
        color: %(text_primary)s;
    }

    QPushButton#SecondaryBtn:pressed,
    QPushButton#ValidateButton:pressed,
    QPushButton#OutlinedButton:pressed {
        background-color: #12151F;
    }

    QPushButton#SecondaryBtn:checked {
        background-color: rgba(156, 115, 242, 0.18);
        border-color: %(primary)s;
        color: %(accent)s;
        font-weight: 600;
    }

    QPushButton#SecondaryBtn:disabled,
    QPushButton#ValidateButton:disabled,
    QPushButton#OutlinedButton:disabled {
        background-color: rgba(255, 255, 255, 0.02);
        color: %(disabled)s;
        border: 1px solid %(divider)s;
    }

    /* Outlined secondary / ghost buttons */
    QPushButton#GhostBtn,
    QPushButton#GhostButton {
        background-color: #171C28;
        color: %(secondary)s;
        border: 1px solid %(border)s;
        border-radius: 5px;
        font-weight: 500;
        font-size: 12px;
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        padding: 0 12px;
        margin: 0;
        cursor: pointer;
    }

    QPushButton#GhostBtn:hover,
    QPushButton#GhostButton:hover {
        background-color: #202738;
        color: %(text_primary)s;
        border-color: %(border_strong)s;
    }

    QPushButton#GhostBtn:pressed,
    QPushButton#GhostButton:pressed {
        background-color: #12151F;
        border-color: %(primary)s;
    }

    QPushButton#GhostBtn:disabled,
    QPushButton#GhostButton:disabled {
        background-color: rgba(255, 255, 255, 0.02);
        color: %(disabled)s;
        border: 1px solid %(divider)s;
    }

    /* Primary alias names */
    QPushButton#PrimaryButton,
    QPushButton#SubmitButton {
        background-color: %(primary)s;
        color: %(primary_fg)s;
        border: 1px solid #7D4EDB;
        border-radius: 5px;
        font-weight: 600;
        font-size: 12px;
        padding: 0 14px;
        min-height: 30px;
        max-height: 30px;
        height: 30px;
        cursor: pointer;
    }

    QPushButton#PrimaryButton:hover,
    QPushButton#SubmitButton:hover {
        background-color: %(primary_hover)s;
        border-color: #BEA1F7;
    }

    QPushButton#PrimaryButton:pressed,
    QPushButton#SubmitButton:pressed {
        background-color: %(primary_press)s;
    }

    QPushButton#PrimaryButton:disabled,
    QPushButton#SubmitButton:disabled {
        background-color: rgba(255, 255, 255, 0.02);
        color: %(disabled)s;
        border: 1px solid %(divider)s;
    }

    /* Destructive solid variant */
    QPushButton#DestructiveBtn,
    QPushButton#DestructiveButton {
        min-height: 32px;
        max-height: 32px;
        height: 32px;
        background-color: #C95C66;
        color: %(primary_fg)s;
        border: 1px solid #A94852;
        border-radius: 6px;
        padding: 0 14px;
        margin: 0;
        font-weight: 600;
        font-size: 13px;
    }

    QPushButton#DestructiveBtn:hover,
    QPushButton#DestructiveButton:hover {
        background-color: #D76D76;
        border-color: #E08A91;
    }

    QPushButton#DestructiveBtn:pressed,
    QPushButton#DestructiveButton:pressed {
        background-color: #A94852;
        border-color: #963E48;
    }

    QPushButton#DestructiveBtn:disabled,
    QPushButton#DestructiveButton:disabled {
        background-color: rgba(255, 255, 255, 0.02);
        color: %(disabled)s;
        border: 1px solid %(divider)s;
    }

    /* Destructive tonal (soft red) variant */
    QPushButton#DestructiveTonalBtn {
        min-height: 32px;
        max-height: 32px;
        height: 32px;
        background-color: rgba(248, 113, 113, 0.15);
        color: %(error)s;
        border: 1px solid rgba(248, 113, 113, 0.40);
        border-radius: 6px;
        padding: 0 14px;
        margin: 0;
        font-weight: 600;
        font-size: 13px;
    }

    QPushButton#DestructiveTonalBtn:hover {
        background-color: rgba(248, 113, 113, 0.25);
        border-color: rgba(248, 113, 113, 0.60);
    }

    QPushButton#DestructiveTonalBtn:pressed {
        background-color: rgba(248, 113, 113, 0.35);
        color: %(text_primary)s;
    }

    QPushButton#DestructiveTonalBtn:disabled {
        background-color: rgba(255, 255, 255, 0.02);
        color: %(disabled)s;
        border: 1px solid %(divider)s;
    }

    /* Info / Purple tonal variant (cohesive studio palette) */
    QPushButton#InfoButton,
    QPushButton#PurpleTonalBtn {
        background-color: rgba(156, 115, 242, 0.12);
        color: #C084FC;
        border: 1px solid rgba(156, 115, 242, 0.35);
        border-radius: 6px;
        min-height: 32px;
        max-height: 32px;
        height: 32px;
        padding: 0 14px;
        font-weight: 600;
        font-size: 13px;
    }

    QPushButton#InfoButton:hover,
    QPushButton#PurpleTonalBtn:hover {
        background-color: rgba(156, 115, 242, 0.22);
        border-color: rgba(156, 115, 242, 0.60);
        color: #FFFFFF;
    }

    QPushButton#InfoButton:pressed,
    QPushButton#PurpleTonalBtn:pressed {
        background-color: rgba(156, 115, 242, 0.35);
        color: #FFFFFF;
    }

    /* Compact bottom-bar button (24px) */
    QPushButton#BottomBarBtn {
        min-height: 24px;
        max-height: 24px;
        height: 24px;
        padding: 0 10px;
        font-size: 12px;
        border-radius: 4px;
        background-color: #171C28;
        color: %(text_primary)s;
        border: 1px solid %(border)s;
        font-weight: 500;
    }

    QPushButton#BottomBarBtn:hover {
        background-color: #202738;
        border-color: #3B4764;
        color: %(text_primary)s;
    }

    /* ── Segmented Choices (inline tabs / filter groups) ── */
    QFrame#SegmentedControl {
        background-color: #111520;
        border: 1px solid #283145;
        border-radius: 6px;
        padding: 2px;
    }

    QPushButton#SegmentButton {
        background-color: transparent;
        color: #94A3B8;
        border: none;
        border-radius: 4px;
        padding: 0 10px;
        font-size: 11.5px;
        font-weight: 500;
        min-height: 24px;
        max-height: 24px;
        height: 24px;
        cursor: pointer;
    }

    QPushButton#SegmentButton:hover {
        color: #FFFFFF;
        background-color: rgba(255, 255, 255, 0.06);
    }

    QPushButton#SegmentButton:checked {
        background-color: %(primary)s;
        color: %(primary_fg)s;
        font-weight: 600;
        border-radius: 4px;
    }

    /* ── Maintenance Tool Button ── */
    QToolButton#MaintenanceButton {
        background-color: transparent;
        color: #94A3B8;
        border: 1px solid #283145;
        border-radius: 5px;
        min-height: 28px;
        max-height: 28px;
        height: 28px;
        padding: 0 8px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
    }

    QToolButton#MaintenanceButton:hover {
        background-color: #202738;
        color: #FFFFFF;
    }

    QToolButton#MaintenanceButton::menu-indicator {
        image: none;
        width: 0px;
    }

    /* ── Tree Views ── */
    QTreeWidget,
    QListWidget {
        background-color: %(surface_input)s;
        alternate-background-color: #0D1017;
        color: %(text)s;
        border: 1px solid %(border)s;
        border-radius: 6px;
        outline: none;
        font-size: 12px;
    }

    QTreeWidget#RenderLayerTree,
    QTreeWidget#JobDependencyTree {
        background-color: %(surface2)s;
        alternate-background-color: %(surface)s;
        border: 1px solid %(border)s;
        border-radius: 6px;
    }

    QTreeWidget#RenderLayerTree::item,
    QTreeWidget#JobDependencyTree::item,
    QTreeWidget::item,
    QListWidget::item,
    QTableWidget::item {
        padding: 3px 6px;
        border: none;
        border-radius: 0px;
        min-height: 24px;
        font-size: 12px;
    }

    QTreeWidget::item:hover,
    QListWidget::item:hover,
    QTableWidget::item:hover {
        background-color: %(surface3)s;
    }

    QTreeWidget::item:selected,
    QListWidget::item:selected,
    QTableWidget::item:selected {
        background-color: %(selection_bg)s;
        color: %(text_primary)s;
    }

    /* ── Header Views (Matching Dashboard Table Headers with Rounded Corners) ── */
    QHeaderView {
        background-color: transparent;
        border: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }

    QHeaderView::section {
        background-color: #121622;
        color: #94A3B8;
        padding: 4px 8px;
        border: none;
        border-bottom: 1px solid #283145;
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    QHeaderView::section:first,
    QHeaderView::section:horizontal:first {
        border-top-left-radius: 5px;
    }

    QHeaderView::section:last,
    QHeaderView::section:horizontal:last {
        border-top-right-radius: 5px;
    }

    QHeaderView::section:only-one,
    QHeaderView::section:horizontal:only-one {
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
    }

    QTableCornerButton::section {
        background-color: #121622;
        border: none;
        border-top-left-radius: 5px;
        border-bottom: 1px solid #283145;
    }

    /* ── Standard QTabWidget & QTabBar (Matching Frontend Dashboard Tabs) ── */
    QTabWidget::pane {
        border: 1px solid %(border)s;
        border-radius: 6px;
        background-color: %(surface2)s;
        top: -1px;
    }

    QTabBar::tab {
        background-color: transparent;
        color: #94A3B8;
        border: 1px solid transparent;
        border-bottom: 2px solid transparent;
        padding: 5px 12px;
        font-size: 12px;
        font-weight: 500;
        min-height: 24px;
        cursor: pointer;
    }

    QTabBar::tab:hover {
        color: #FFFFFF;
        background-color: rgba(255, 255, 255, 0.05);
    }

    QTabBar::tab:selected {
        color: #FFFFFF;
        font-weight: 600;
        border-bottom: 2px solid %(primary)s;
    }

    /* ── Context Menus (Dark Glassmorphic) ── */
    QMenu {
        background-color: #111520;
        color: %(text)s;
        border: 1px solid %(border)s;
        border-radius: 6px;
        padding: 4px;
        font-size: 13px;
        font-weight: 500;
    }

    QMenu::item {
        background-color: transparent;
        padding: 6px 18px 6px 22px;
        border-radius: 4px;
        margin: 1px 2px;
    }

    QMenu::icon {
        left: 10px;
    }

    QMenu::item:selected {
        background-color: #202738;
        color: %(text_primary)s;
    }

    QMenu::item:disabled {
        color: %(disabled)s;
        background-color: transparent;
    }

    QMenu::separator {
        height: 1px;
        background-color: #202738;
        margin: 4px 6px;
    }

    /* ── Progress Bars ── */
    QProgressBar {
        min-height: 8px;
        max-height: 8px;
        height: 8px;
        border: 1px solid %(surface4)s;
        border-radius: 4px;
        background-color: %(surface_input)s;
        text-align: center;
        color: transparent;
    }

    QProgressBar::chunk {
        background-color: %(primary)s;
        border-radius: 3px;
    }

    /* ── Scrollbars (Worker-exact: 10px, purple hover, inner border) ── */
    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 0px;
        border: none;
    }

    QScrollBar::handle:vertical {
        background-color: %(border)s;
        border: 2px solid %(background)s;
        border-radius: 5px;
        min-height: 24px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: %(primary)s;
    }

    QScrollBar::handle:vertical:pressed {
        background-color: #8455E8;
    }

    QScrollBar::track:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: transparent;
        border: none;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
        background: transparent;
        border: none;
    }

    QScrollBar:horizontal {
        background: transparent;
        height: 10px;
        margin: 0px;
        border: none;
    }

    QScrollBar::handle:horizontal {
        background-color: %(border)s;
        border: 2px solid %(background)s;
        border-radius: 5px;
        min-width: 24px;
    }

    QScrollBar::handle:horizontal:hover {
        background-color: %(primary)s;
    }

    QScrollBar::handle:horizontal:pressed {
        background-color: #8455E8;
    }

    QScrollBar::track:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {
        background: transparent;
        border: none;
    }

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0px;
        background: transparent;
        border: none;
    }

    /* ── Activity / Terminal Log ── */
    QPlainTextEdit#ActivityLog {
        background-color: %(terminal)s;
        color: #D1D5DB;
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 12px;
        border: 1px solid %(border_card)s;
        border-radius: 6px;
        padding: 8px;
    }

    /* ── CheckBoxes, Tree & Table Item Indicators (High-Contrast Crisp) ── */
    QCheckBox {
        color: %(text)s;
        spacing: 8px;
        font-size: 13px;
    }

    QCheckBox::indicator,
    QTreeWidget::indicator,
    QTableWidget::indicator,
    QListWidget::indicator {
        width: 16px;
        height: 16px;
        border: 1.5px solid #3B4764;
        border-radius: 4px;
        background-color: #080A0F;
        margin-right: 4px;
    }

    QCheckBox::indicator:hover,
    QTreeWidget::indicator:hover,
    QTableWidget::indicator:hover,
    QListWidget::indicator:hover {
        border: 1.5px solid %(primary)s;
        background-color: #171A24;
    }

    QCheckBox::indicator:checked {
        background-color: %(primary)s;
        border: 1.5px solid %(primary)s;
        image: url("%(check_mark)s");
    }

    QTreeWidget::indicator:checked {
        background-color: %(primary)s;
        border: 1.5px solid %(primary)s;
        image: url("%(check_mark)s");
    }

    QTableWidget::indicator:checked,
    QListWidget::indicator:checked {
        background-color: %(primary)s;
        border: 1.5px solid %(primary)s;
        image: url("%(check_mark)s");
    }

    QCheckBox::indicator:indeterminate,
    QTreeWidget::indicator:indeterminate,
    QTableWidget::indicator:indeterminate,
    QListWidget::indicator:indeterminate {
        background-color: %(surface3)s;
        border: 1.5px solid %(primary)s;
    }

    QCheckBox::indicator:disabled,
    QTreeWidget::indicator:disabled,
    QTableWidget::indicator:disabled,
    QListWidget::indicator:disabled {
        background-color: #0A0C11;
        border: 1px solid %(divider)s;
    }

    /* ── Inline field helpers ── */
    QWidget#InlineFieldContainer,
    QFrame#RenderLayerSelector {
        background-color: transparent;
        border: none;
    }
    """ % c
