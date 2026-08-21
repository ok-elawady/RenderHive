from __future__ import annotations

import unittest
from pathlib import Path


class ProductionUIPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.theme = (cls.root / "ui" / "theme.py").read_text(encoding="utf-8")
        cls.widgets = (cls.root / "ui" / "widgets.py").read_text(encoding="utf-8")
        cls.window = (cls.root / "ui" / "main_window.py").read_text(encoding="utf-8")

    def test_labels_are_transparent(self):
        self.assertIn("QLabel {\n    background-color: transparent;\n    border: none;\n}", self.theme)
        self.assertIn("QLabel#BrandLogo", self.theme)

    def test_empty_state_is_centered_and_compact(self):
        self.assertIn('setObjectName("EmptyStatePage")', self.window)
        self.assertIn("setMaximumWidth(480)", self.window)
        self.assertIn('setObjectName("EmptyHeroCard")', self.widgets)
        self.assertIn('setObjectName("EmptyHeroTitle")', self.widgets)
        self.assertIn('setObjectName("EmptyHeroMessage")', self.widgets)

    def test_production_version(self):
        version = (self.root / "version.py").read_text(encoding="utf-8")
        self.assertIn('WORKER_VERSION = "1.4.1"', version)


if __name__ == "__main__":
    unittest.main()
