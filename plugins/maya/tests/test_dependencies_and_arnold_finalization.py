from __future__ import absolute_import

import os
import unittest

from api import payload
from api.config import DEFAULT_CONFIG
from submission import task_builder


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEP_JOB = "33333333-3333-3333-3333-333333333333"


class _Api(object):
    class _Cmds(object):
        @staticmethod
        def about(version=False):
            return "2025" if version else ""
    cmds = _Cmds()
    VALIDATION_REPORT = {"summary": {"ERROR": 0, "WARNING": 0, "INFO": 0, "PASSED": 0, "total": 0}}

    def get_scene_name(self): return "shot"
    def get_scene_path(self): return r"D:\\Project\\shot.ma"
    def get_project_path(self): return r"D:\\Project"
    def get_default_output_path(self): return r"D:\\Project\\images"
    def get_frame_range(self): return (1, 2)
    def get_resolution(self): return (1920, 1080)
    def get_current_renderer(self): return "mayaHardware2"
    def get_renderable_camera(self): return "renderCam"
    def get_render_layers(self):
        return [{"name": "defaultRenderLayer", "display_name": "Beauty", "source": "legacy", "renderable": True, "is_default": True}]
    def get_text(self, name, default=""):
        values = {"rh_job_dependencies": DEP_JOB, "rh_image_name": "beauty"}
        return values.get(name, default)
    def get_int(self, name, default=0): return int(default)
    def get_option(self, name, default=""):
        values = {"rh_renderer": "mayaHardware2", "rh_camera": "renderCam", "rh_image_format": "jpg"}
        return values.get(name, default)


class DependenciesAndArnoldFinalizationTests(unittest.TestCase):
    def test_task_builder_forces_arnold_and_normalizes_jpeg(self):
        task = task_builder.build_task(_Api(), window=None, widgets=None)
        self.assertEqual(task["renderer"], "arnold")
        self.assertEqual(task["software_info"]["renderer"], "arnold")
        self.assertEqual(task["image_format"], "jpeg")
        self.assertEqual(task["job_dependencies"], [DEP_JOB])

    def test_payload_rejects_non_arnold_renderer(self):
        task = {
            "renderer": "mayaHardware2",
            "camera": "renderCam",
            "project_path": r"D:\\Project",
            "output_path": r"D:\\Project\\images",
            "scene_path": r"D:\\Project\\shot.ma",
        }
        with self.assertRaises(payload.PayloadError):
            payload.build_maya_command(task, DEFAULT_CONFIG)

    def test_arnold_command_loads_mtoa_and_sets_renderer(self):
        task = {
            "renderer": "arnold",
            "camera": "renderCam",
            "project_path": r"D:\\Project",
            "output_path": r"D:\\Project\\images",
            "scene_path": r"D:\\Project\\shot.ma",
            "image_name": "beauty",
            "image_format": "jpg",
            "frame_padding": 4,
        }
        command = payload.build_maya_command(task, DEFAULT_CONFIG)
        self.assertIn("-r arnold", command)
        self.assertIn("-preRender", command)
        # The Python pre-render script is base64 encoded, so enforce these in source.
        with open(os.path.join(ROOT, "api", "payload.py"), "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("cmds.loadPlugin('mtoa', quiet=True)", source)
        self.assertIn("currentRenderer', 'arnold'", source)
        self.assertIn('image_format == "jpg"', source)
        self.assertIn('image_format = "jpeg"', source)

    def test_render_page_exposes_only_arnold(self):
        with open(os.path.join(ROOT, "ui", "pages", "render_page.py"), "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('renderer.addItem("arnold")', source)
        self.assertNotIn('renderer.addItems(["arnold", "sw", "mayaHardware2"])', source)

    def test_job_dependency_browser_replaces_manual_uuid_field(self):
        with open(os.path.join(ROOT, "ui", "pages", "job_page.py"), "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('QtWidgets.QPushButton("Browse Jobs…")', source)
        self.assertIn('dependencies.setVisible(False)', source)
        self.assertNotIn("Enter job IDs separated by commas", source)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "ui", "job_dependency_widgets.py")))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "ui", "controllers", "dependency_controller.py")))

    def test_installer_and_audit_require_dependency_modules(self):
        required = (
            'os.path.join("ui", "controllers", "dependency_controller.py")',
            'os.path.join("ui", "job_dependency_widgets.py")',
        )
        for relative_path in ("renderhive_installer.py", os.path.join("tools", "production_audit.py")):
            with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as handle:
                source = handle.read()
            for expression in required:
                self.assertIn(expression, source)


if __name__ == "__main__":
    unittest.main()
