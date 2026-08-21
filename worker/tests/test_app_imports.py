from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AppImportTests(unittest.TestCase):
    def test_qsystemtrayicon_is_imported_from_qtwidgets(self):
        window_path = Path(__file__).resolve().parents[1] / "ui" / "main_window.py"
        tree = ast.parse(window_path.read_text(encoding="utf-8"), filename=str(window_path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets":
                imported.update(alias.name for alias in node.names)
        self.assertIn("QSystemTrayIcon", imported)

    def test_bundled_fonts_exist(self):
        fonts_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
        self.assertTrue(fonts_dir.is_dir())
        font_files = [f.name for f in fonts_dir.iterdir() if f.suffix == ".ttf"]
        self.assertIn("Inter-Regular.ttf", font_files)
        self.assertIn("Inter-Bold.ttf", font_files)
        self.assertIn("JetBrainsMono-Regular.ttf", font_files)
        self.assertIn("JetBrainsMono-Bold.ttf", font_files)

    def test_lucide_vector_icons_load(self):
        from ui.icons import SVG_ICONS, get_icon
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        for name in ("play", "stop", "settings", "pause", "refresh", "copy", "x"):
            self.assertIn(name, SVG_ICONS)
            icon = get_icon(name)
            self.assertFalse(icon.isNull())

    def test_custom_title_bar_exists(self):
        from ui.title_bar import CustomTitleBar
        self.assertTrue(callable(CustomTitleBar))


if __name__ == "__main__":
    unittest.main()
