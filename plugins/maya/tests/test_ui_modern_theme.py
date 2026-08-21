from __future__ import absolute_import, print_function

import os
import unittest

from ui.qt_theme import COLORS, build_stylesheet
from ui.font_loader import get_fonts_dir, load_application_fonts, get_ui_font, get_monospace_font


class UIModernThemeTests(unittest.TestCase):
    def test_color_tokens_defined(self):
        required_keys = [
            "background", "surface", "surface2", "surface3", "surface_input",
            "border", "border_card", "border_focus", "primary", "primary_hover",
            "primary_active", "text", "text_primary", "secondary", "muted",
            "disabled", "info", "success", "warning", "error", "paused", "terminal"
        ]
        for key in required_keys:
            self.assertIn(key, COLORS)
            self.assertTrue(COLORS[key].startswith("#"), "Color for {} must be hex".format(key))

    def test_stylesheet_generation(self):
        qss = build_stylesheet()
        self.assertIn("QWidget", qss)
        self.assertIn("QFrame#StepperWidget", qss)
        self.assertIn("QPushButton#StepperButton", qss)
        self.assertIn("QLineEdit#StepperInput", qss)
        self.assertIn("QLabel#BrandMain", qss)
        self.assertIn("QScrollBar:vertical", qss)
        self.assertIn("QPlainTextEdit#ActivityLog", qss)

    def test_fonts_directory_has_bundled_fonts(self):
        fonts_dir = get_fonts_dir()
        self.assertTrue(os.path.isdir(fonts_dir), "Fonts dir must exist: {}".format(fonts_dir))
        files = os.listdir(fonts_dir)
        inter_fonts = [f for f in files if f.startswith("Inter-") and f.endswith(".ttf")]
        jetbrains_fonts = [f for f in files if f.startswith("JetBrainsMono-") and f.endswith(".ttf")]
        self.assertGreaterEqual(len(inter_fonts), 4, "Must have at least 4 Inter fonts")
        self.assertGreaterEqual(len(jetbrains_fonts), 2, "Must have at least 2 JetBrains Mono fonts")

    def test_font_loader_execution(self):
        result = load_application_fonts()
        self.assertTrue(result)
        ui_font = get_ui_font(size=13)
        self.assertIsNotNone(ui_font)
        mono_font = get_monospace_font(size=11)
        self.assertIsNotNone(mono_font)


if __name__ == "__main__":
    unittest.main()
