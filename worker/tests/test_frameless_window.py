"""Unit and contract tests for the Studio Frameless Window, Edge Resizing, and Navigation."""

from __future__ import annotations

import sys
import unittest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, RESIZE_MARGIN
from ui.title_bar import CustomTitleBar


class FramelessWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow()
        if hasattr(self.window, "tray_icon") and self.window.tray_icon:
            self.window.tray_icon.setVisible(False)
        self.window.nav_dash_btn.click()

    def tearDown(self):
        self.window.is_quitting = True
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()

    def test_native_window_properties(self):
        self.assertIn("RenderHive Worker", self.window.windowTitle())
        self.assertIsNotNone(self.window.status_chip)
        self.assertIsNotNone(self.window.conn_chip)

    def test_top_header_controls(self):
        self.assertIsNotNone(self.window.start_btn)
        self.assertIsNotNone(self.window.settings_btn)
        self.assertIsNotNone(self.window.pause_dispatch_btn)

    def test_maximize_restore_toggle(self):
        self.window.show()
        QApplication.processEvents()
        if self.window.isMaximized():
            self.window.toggle_maximize_window()
            QApplication.processEvents()
        self.assertFalse(self.window.isMaximized())

        self.window.toggle_maximize_window()
        QApplication.processEvents()
        self.assertTrue(self.window.isMaximized())

        self.window.toggle_maximize_window()
        QApplication.processEvents()
        self.assertFalse(self.window.isMaximized())

    def test_top_segmented_navigation_switch(self):
        self.assertEqual(self.window.main_stack.currentIndex(), 0)

        # Switch to Telemetry (page 1)
        self.window.nav_telemetry_btn.click()
        self.assertEqual(self.window.main_stack.currentIndex(), 1)

        # Switch to Console Logs (page 2)
        self.window.nav_logs_btn.click()
        self.assertEqual(self.window.main_stack.currentIndex(), 2)

        # Switch back to Dashboard (page 0)
        self.window.nav_dash_btn.click()
        self.assertEqual(self.window.main_stack.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
