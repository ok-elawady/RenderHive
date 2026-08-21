"""Font loader for RenderHive Maya plugin.

Loads bundled Inter and JetBrains Mono fonts into the Qt application font database
and configures DirectWrite / ClearType subpixel rendering to eliminate jagged/pixelated text.
"""

from __future__ import absolute_import, print_function

import os
from .qt_compat import QtGui, QtWidgets

try:
    from core.runtime_log import get_logger
    LOGGER = get_logger("font_loader")
except Exception:
    LOGGER = None

_FONTS_LOADED = False


def get_fonts_dir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "assets",
        "fonts",
    )


def _apply_smooth_font_hints(font):
    """Configure hinting preference and style strategies for crisp subpixel text rendering."""
    # 1. PreferNoHinting: let Windows ClearType / DirectWrite do subpixel rasterization
    # instead of Qt's stem-snapping rasterizer, which causes pixelated/jagged fonts on dark surfaces.
    try:
        if hasattr(QtGui.QFont, "PreferNoHinting"):
            font.setHintingPreference(QtGui.QFont.PreferNoHinting)
        elif hasattr(QtGui.QFont, "HintingPreference") and hasattr(QtGui.QFont.HintingPreference, "PreferNoHinting"):
            font.setHintingPreference(QtGui.QFont.HintingPreference.PreferNoHinting)
    except Exception:
        pass

    # 2. PreferAntialias | ForceOutline: always use vector outline glyphs, never bitmap strikes
    strategy = 0
    try:
        if hasattr(QtGui.QFont, "PreferAntialias"):
            strategy |= QtGui.QFont.PreferAntialias
        elif hasattr(QtGui.QFont, "StyleStrategy") and hasattr(QtGui.QFont.StyleStrategy, "PreferAntialias"):
            strategy |= QtGui.QFont.StyleStrategy.PreferAntialias

        if hasattr(QtGui.QFont, "ForceOutline"):
            strategy |= QtGui.QFont.ForceOutline
        elif hasattr(QtGui.QFont, "StyleStrategy") and hasattr(QtGui.QFont.StyleStrategy, "ForceOutline"):
            strategy |= QtGui.QFont.StyleStrategy.ForceOutline

        if strategy:
            font.setStyleStrategy(strategy)
    except Exception:
        pass

    return font


def load_application_fonts(target_widget_or_app=None):
    """Register bundled TrueType fonts in QFontDatabase and configure smooth font defaults."""
    global _FONTS_LOADED
    if not _FONTS_LOADED:
        fonts_dir = get_fonts_dir()
        loaded_count = 0
        if os.path.isdir(fonts_dir):
            for filename in sorted(os.listdir(fonts_dir)):
                if filename.lower().endswith((".ttf", ".otf")):
                    font_path = os.path.join(fonts_dir, filename)
                    try:
                        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
                        if font_id >= 0:
                            loaded_count += 1
                    except Exception:
                        pass

        if LOGGER:
            LOGGER.info("Registered %s bundled font files from %s", loaded_count, fonts_dir)
        _FONTS_LOADED = True

    default_font = get_ui_font(13)
    if target_widget_or_app is not None:
        try:
            target_widget_or_app.setFont(default_font)
        except Exception:
            pass

    return True


def get_ui_font(size=13, weight=None, bold=False, italic=False):
    """Create a configured QFont prioritizing Inter with smooth subpixel antialiasing."""
    if not _FONTS_LOADED:
        load_application_fonts()

    font = QtGui.QFont()
    if hasattr(font, "setFamilies"):
        font.setFamilies(["Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Arial", "sans-serif"])
    else:
        font.setFamily("Inter, Segoe UI, sans-serif")

    # Style hint
    try:
        if hasattr(QtGui.QFont, "SansSerif"):
            font.setStyleHint(QtGui.QFont.SansSerif)
        elif hasattr(QtGui.QFont, "StyleHint") and hasattr(QtGui.QFont.StyleHint, "SansSerif"):
            font.setStyleHint(QtGui.QFont.StyleHint.SansSerif)
    except Exception:
        pass

    font.setPixelSize(int(size))

    if bold:
        font.setBold(True)
    elif weight is not None:
        font.setWeight(weight)
    font.setItalic(bool(italic))

    _apply_smooth_font_hints(font)
    return font


def get_monospace_font(size=12, bold=False):
    """Create a configured monospace QFont prioritizing JetBrains Mono with smooth rendering."""
    if not _FONTS_LOADED:
        load_application_fonts()

    font = QtGui.QFont()
    if hasattr(font, "setFamilies"):
        font.setFamilies(["JetBrains Mono", "Consolas", "Courier New", "monospace"])
    else:
        font.setFamily("JetBrains Mono, Consolas, monospace")

    font.setPixelSize(int(size))

    if bold:
        font.setBold(True)

    _apply_smooth_font_hints(font)
    return font

    # Monospace hint
    try:
        if hasattr(QtGui.QFont, "Monospace"):
            font.setStyleHint(QtGui.QFont.Monospace)
        elif hasattr(QtGui.QFont, "StyleHint") and hasattr(QtGui.QFont.StyleHint, "Monospace"):
            font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    except Exception:
        pass

    font.setPixelSize(int(size))
    if bold:
        font.setBold(True)

    _apply_smooth_font_hints(font)
    return font
