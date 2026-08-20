"""Font loading utility for RenderHive Worker.

Loads bundled static hinted Inter and JetBrains Mono fonts into Qt application font database.
"""

from __future__ import annotations

import os
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from core.runtime_paths import bundled_path


def load_application_fonts(app: QApplication) -> None:
    """Register bundled Inter and JetBrains Mono fonts and configure smooth rendering."""
    fonts_dir = bundled_path("assets", "fonts")
    if os.path.isdir(fonts_dir):
        for filename in sorted(os.listdir(fonts_dir)):
            if filename.lower().endswith((".ttf", ".otf")):
                font_path = os.path.join(fonts_dir, filename)
                QFontDatabase.addApplicationFont(font_path)

    # PreferNoHinting: let Windows ClearType / DirectWrite do subpixel rendering
    # instead of Qt's own stem-snapping hinter, which causes the pixelated look.
    # PreferAntialias + NoSubpixelAntialias together delegate AA to the OS compositor.
    default_font = QFont("Inter")
    default_font.setStyleHint(QFont.StyleHint.SansSerif)
    default_font.setPixelSize(13)  # explicit pixel size avoids DPI-conversion rounding
    default_font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias
        | QFont.StyleStrategy.ForceOutline  # always use outline glyphs, never bitmap
    )
    default_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(default_font)
