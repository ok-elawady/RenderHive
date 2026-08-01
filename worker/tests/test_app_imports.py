from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AppImportTests(unittest.TestCase):
    def test_qsystemtrayicon_is_imported_from_qtwidgets(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        tree = ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets":
                imported.update(alias.name for alias in node.names)
        self.assertIn("QSystemTrayIcon", imported)


if __name__ == "__main__":
    unittest.main()
