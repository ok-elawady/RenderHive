from __future__ import absolute_import

import os
import shutil
import tempfile
import unittest

from api import maya_bridge, payload
from submission import task_builder
from validation import autofix, render_checks
from validation.validator import ValidationEngine
import renderhive_installer


class DummyCmds(object):
    def __init__(self):
        self._nodes = {}
        self._attrs = {}
        self._current_time = 1.0

    def objExists(self, name):
        return name in self._nodes or name in self._attrs or "." in name

    def getAttr(self, plug):
        return self._attrs.get(plug, "")

    def setAttr(self, plug, val, **kwargs):
        self._attrs[plug] = val

    def undoInfo(self, *args, **kwargs):
        pass

    def ls(self, *args, **kwargs):
        node_type = kwargs.get("type")
        if node_type:
            return [name for name, t in self._nodes.items() if t == node_type]
        if args:
            pattern = str(args[0]).rstrip("*")
            return [name for name in self._nodes.keys() if name.startswith(pattern)]
        return list(self._nodes.keys())

    def createNode(self, node_type, name=None):
        name = name or "{}_1".format(node_type)
        self._nodes[name] = node_type
        self._attrs[name + ".enabled"] = True
        return name

    def connectAttr(self, src, dst, **kwargs):
        pass

    def currentTime(self, time=None, query=False):
        if query:
            return self._current_time
        self._current_time = float(time)
        return self._current_time

    def render(self, camera, **kwargs):
        return "rendered_frame"

    def arnoldRender(self, **kwargs):
        return "rendered_arnold_frame"


class DummyApi(object):
    def __init__(self, cmds=None):
        self.cmds = cmds or DummyCmds()

    def get_scene_name(self):
        return "shot_010_lighting_v001"

    def get_scene_path(self):
        return "/jobs/shot_010/maya/scenes/shot_010_lighting_v001.ma"

    def get_project_path(self):
        return "/jobs/shot_010/maya"

    def get_output_path(self):
        return "/jobs/shot_010/renders"

    def get_default_output_path(self):
        return "/jobs/shot_010/renders"

    def get_frame_range(self):
        return 100, 1

    def get_resolution(self):
        return 1920, 1080

    def get_current_renderer(self):
        return "arnold"

    def get_text(self, key, default=""):
        data = {
            "rh_project_name": "TestProject",
            "rh_job_name": "Shot01_Lighting",
            "rh_renderer": "arnold",
            "rh_camera": "renderCam",
            "rh_image_name": "beauty",
            "rh_image_format": "exr",
            "rh_submission_mode": "Server Repository Staging",
        }
        return data.get(key, default)

    def get_int(self, key, default=0):
        data = {
            "rh_frame_start": 100,
            "rh_frame_end": 1,
            "rh_frame_step": 1,
            "rh_chunk_size": 10,
            "rh_priority": 50,
            "rh_frame_padding": 4,
            "rh_width": 1920,
            "rh_height": 1080,
        }
        return data.get(key, default)

    def get_bool(self, key, default=False):
        return default

    def get_option(self, key, default=""):
        return self.get_text(key, default)

    def get_cameras(self):
        return ["renderCam", "persp"]

    def get_renderable_camera(self):
        return "renderCam"

    def get_render_layers(self):
        return [{"name": "defaultRenderLayer", "display_name": "defaultRenderLayer", "renderable": True, "is_default": True}]


class SupervisorEnhancementsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="rh_enhancements_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_descending_frame_range_in_task_builder(self):
        api = DummyApi()
        task = task_builder.build_task(api)
        self.assertEqual(task["frames"]["start"], 100)
        self.assertEqual(task["frames"]["end"], 1)
        self.assertEqual(task["frames"]["direction"], "descending")
        self.assertEqual(task["frames"]["count"], 100)
        self.assertEqual(task["frames"]["task_count"], 10)
        self.assertEqual(task["submission_mode"], "Server Repository Staging")

    def test_descending_frame_range_in_payload_builder(self):
        task = {
            "frame_start": 100,
            "frame_end": 1,
            "frame_step": 1,
        }
        range_str = payload.build_frame_range(task)
        self.assertEqual(range_str, "1-100")

        task_step = {
            "frame_start": 50,
            "frame_end": 10,
            "frame_step": 2,
        }
        range_step_str = payload.build_frame_range(task_step)
        self.assertEqual(range_step_str, "10-50x2")

    def test_validation_rule_overrides_severity(self):
        task = {
            "scene_path": "",
            "renderer": "arnold",
            "rule_overrides": {
                "SCENE_NOT_SAVED": "WARNING",
                "RENDER_REGION_ENABLED": "ERROR",
                "PROJECT_PATH_MISSING": "DISABLED",
            }
        }
        engine = ValidationEngine(task)
        self.assertEqual(engine.get_rule_severity("SCENE_NOT_SAVED", "ERROR"), "WARNING")
        self.assertEqual(engine.get_rule_severity("RENDER_REGION_ENABLED", "WARNING"), "ERROR")
        self.assertEqual(engine.get_rule_severity("PROJECT_PATH_MISSING", "ERROR"), "DISABLED")

    def test_configured_aovs_missing_cryptomatte(self):
        old_cmds = render_checks.cmds
        cmds = DummyCmds()
        render_checks.cmds = cmds
        try:
            context = {
                "renderer": "arnold",
                "required_aovs": ["crypto_asset", "crypto_object", "crypto_material"],
            }
            results = render_checks.check_configured_aovs(context)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["code"], "REQUIRED_AOV_MISSING")
            self.assertEqual(results[0]["severity"], "ERROR")
            self.assertIn("crypto_asset", results[0]["message"])
        finally:
            render_checks.cmds = old_cmds

    def test_configured_aovs_passes_when_all_created(self):
        old_cmds = render_checks.cmds
        cmds = DummyCmds()
        cmds.createNode("aiAOV", "aiAOV_crypto_asset")
        cmds.setAttr("aiAOV_crypto_asset.name", "crypto_asset")
        cmds.createNode("aiAOV", "aiAOV_crypto_object")
        cmds.setAttr("aiAOV_crypto_object.name", "crypto_object")
        cmds.createNode("aiAOV", "aiAOV_crypto_material")
        cmds.setAttr("aiAOV_crypto_material.name", "crypto_material")
        render_checks.cmds = cmds
        try:
            context = {
                "renderer": "arnold",
                "required_aovs": ["crypto_asset", "crypto_object", "crypto_material"],
            }
            results = render_checks.check_configured_aovs(context)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["severity"], "PASSED")
        finally:
            render_checks.cmds = old_cmds

    def test_autofix_creates_missing_aovs(self):
        old_cmds = autofix.cmds
        cmds = DummyCmds()
        autofix.cmds = cmds
        try:
            result = {
                "code": "REQUIRED_AOV_MISSING",
                "fixable": True,
                "data": {
                    "missing_aovs": ["crypto_asset", "crypto_object"],
                },
            }
            fix_result = autofix.apply_fix(result)
            self.assertTrue(fix_result.get("success"))
            self.assertIn("crypto_asset", fix_result.get("message"))
            self.assertTrue(cmds.objExists("aiAOV_crypto_asset"))
            self.assertTrue(cmds.objExists("aiAOV_crypto_object"))
        finally:
            autofix.cmds = old_cmds

    def test_installer_uninstall_safety_guards_source_repo(self):
        # A source git directory or plugin root must NEVER be flagged safe to delete
        source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertFalse(renderhive_installer._is_safe_to_uninstall(source_dir))

        # A temp directory outside Maya scripts is NOT safe to delete
        self.assertFalse(renderhive_installer._is_safe_to_uninstall(self.temp_dir))

    def test_scroll_filter_blocks_combobox_scroll(self):
        from ui.common_widgets import ScrollFilter
        from ui.qt_compat import QtWidgets, QtCore, QtGui
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        combo = QtWidgets.QComboBox()
        combo.addItems(["A", "B", "C"])
        combo.setCurrentIndex(0)
        ScrollFilter.install(combo)
        filter_obj = ScrollFilter.get()
        if hasattr(QtGui, "QWheelEvent"):
            event = QtGui.QWheelEvent(
                QtCore.QPointF(10, 10),
                QtCore.QPointF(10, 10),
                QtCore.QPoint(0, 120),
                QtCore.QPoint(0, 120),
                QtCore.Qt.NoButton,
                QtCore.Qt.NoModifier,
                QtCore.Qt.ScrollUpdate if hasattr(QtCore.Qt, "ScrollUpdate") else QtCore.Qt.ScrollPhase(0),
                False
            )
            filtered = filter_obj.eventFilter(combo, event)
            self.assertTrue(filtered)
            self.assertEqual(combo.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
