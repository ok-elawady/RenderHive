from __future__ import annotations

import ast
import unittest
from pathlib import Path


class CompactUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.app_text = (cls.root / "app.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.app_text)

    def test_compact_default_window_size(self):
        self.assertIn("self.resize(800, 520)", self.app_text)
        self.assertIn("self.setMinimumSize(720, 470)", self.app_text)

    def test_two_primary_deadline_style_tabs(self):
        self.assertIn('"Job Information"', self.app_text)
        self.assertIn('"Worker Information"', self.app_text)
        self.assertIn("self.main_tabs = QTabWidget()", self.app_text)

    def test_log_is_a_collapsible_drawer(self):
        self.assertIn('self.log_drawer.setVisible(expanded)', self.app_text)
        self.assertIn('def toggle_log_drawer', self.app_text)
        self.assertIn('"Show Log"', self.app_text)

    def test_sidebar_is_not_built(self):
        build_ui = next(
            node for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_build_ui"
        )
        segment = ast.get_source_segment(self.app_text, build_ui) or ""
        self.assertNotIn('setObjectName("Sidebar")', segment)
        self.assertNotIn('NavButton(', segment)

    def test_version_is_updated(self):
        version = (self.root / "version.py").read_text(encoding="utf-8")
        self.assertIn('WORKER_VERSION = "1.4.1"', version)


if __name__ == "__main__":
    unittest.main()
