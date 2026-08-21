from __future__ import absolute_import, print_function

import sys
import unittest
from types import ModuleType

# Mock maya modules if not running inside Autodesk Maya
if "maya" not in sys.modules:
    maya_mock = ModuleType("maya")
    maya_cmds_mock = ModuleType("maya.cmds")
    maya_cmds_mock.about = lambda **kwargs: "2024"
    maya_cmds_mock.confirmDialog = lambda **kwargs: "OK"
    maya_cmds_mock.getAttr = lambda *args, **kwargs: 1
    maya_cmds_mock.ls = lambda *args, **kwargs: []
    maya_cmds_mock.setAttr = lambda *args, **kwargs: None
    maya_cmds_mock.file = lambda *args, **kwargs: "untitled.ma"
    maya_cmds_mock.workspace = lambda *args, **kwargs: "C:/maya/projects/default"
    maya_mock.cmds = maya_cmds_mock
    sys.modules["maya"] = maya_mock
    sys.modules["maya.cmds"] = maya_cmds_mock

    maya_omui_mock = ModuleType("maya.OpenMayaUI")
    class MockMQtUtil:
        @staticmethod
        def mainWindow():
            return None
    maya_omui_mock.MQtUtil = MockMQtUtil
    maya_mock.OpenMayaUI = maya_omui_mock
    sys.modules["maya.OpenMayaUI"] = maya_omui_mock

from ui.qt_compat import QtWidgets
import renderhive_maya_submitter as submitter_module
import ui.qt_submitter_window as qt_submitter_window


class SubmitterWindowInstantiationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_show_submitter_opens_window_without_name_errors(self):
        window = qt_submitter_window.show_submitter(submitter_module)
        self.assertIsNotNone(window)
        self.assertTrue(isinstance(window, qt_submitter_window.RenderHiveSubmitter))

        # Test selecting all 4 pages
        for page_idx in range(4):
            window.select_page(page_idx)
            self.assertEqual(window.page_stack.currentIndex(), page_idx)

        # Test status updates
        window.set_status("Ready", level="success")
        window.set_status("Warning encountered", level="warning")
        window.set_status("Error encountered", level="error")

        # Close window
        window.close()


if __name__ == "__main__":
    unittest.main()
