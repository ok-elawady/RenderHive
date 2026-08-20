from __future__ import annotations

import ast
import unittest
from pathlib import Path


class StudioUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.window_text = (cls.root / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.window_text)

    def test_studio_window_size(self):
        self.assertIn("self.resize(920, 600)", self.window_text)
        self.assertIn("self.setMinimumSize(780, 500)", self.window_text)

    def test_top_segmented_navigation_built(self):
        self.assertIn('setObjectName("TopHeaderBar")', self.window_text)
        self.assertIn('setObjectName("NavSegmentContainer")', self.window_text)
        self.assertIn('setObjectName("PauseButtonGroup")', self.window_text)
        self.assertIn("self.nav_dash_btn", self.window_text)
        self.assertIn("self.nav_telemetry_btn", self.window_text)
        self.assertIn("self.nav_logs_btn", self.window_text)
        self.assertIn("self.pause_dispatch_btn", self.window_text)
        self.assertIn("self.after_task_btn", self.window_text)
        self.assertIn("self.start_btn", self.window_text)
        self.assertIn("self.settings_btn", self.window_text)
        self.assertIn("self.main_stack = QStackedWidget()", self.window_text)

    def test_status_chips_integrated_in_title_bar(self):
        self.assertIn("self.status_chip", self.window_text)
        self.assertIn("self.conn_chip", self.window_text)

    def test_bottom_status_bar_built(self):
        self.assertIn('setObjectName("BottomStatusBar")', self.window_text)
        self.assertIn("self.header_dcc_label", self.window_text)
        self.assertIn("self.refresh_btn", self.window_text)

    def test_version_is_updated(self):
        version = (self.root / "version.py").read_text(encoding="utf-8")
        self.assertIn('WORKER_VERSION = "1.4.1"', version)


if __name__ == "__main__":
    unittest.main()
