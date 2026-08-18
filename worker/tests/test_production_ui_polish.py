from __future__ import annotations

import unittest
from pathlib import Path


class ProductionUIPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.theme = (cls.root / "ui" / "theme.py").read_text(encoding="utf-8")
        cls.widgets = (cls.root / "ui" / "widgets.py").read_text(encoding="utf-8")
        cls.app = (cls.root / "app.py").read_text(encoding="utf-8")

    def test_labels_are_transparent(self):
        self.assertIn("QLabel { background-color: transparent; border: none; }", self.theme)
        self.assertIn("QLabel#BrandLogo", self.theme)

    def test_empty_state_is_centered_and_compact(self):
        self.assertIn('setObjectName("EmptyStatePage")', self.app)
        self.assertIn('setMaximumWidth(390)', self.app)
        self.assertIn('setObjectName("EmptyStateTitle")', self.widgets)
        self.assertIn('setObjectName("EmptyStateMessage")', self.widgets)

    def test_production_version(self):
        version = (self.root / "version.py").read_text(encoding="utf-8")
        self.assertIn('WORKER_VERSION = "1.4.1"', version)


if __name__ == "__main__":
    unittest.main()
