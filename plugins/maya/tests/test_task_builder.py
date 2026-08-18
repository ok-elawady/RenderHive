from __future__ import absolute_import

import os
import types
import unittest

from submission import task_builder


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL_A = "11111111-1111-1111-1111-111111111111"
POOL_B = "22222222-2222-2222-2222-222222222222"
DEP_JOB = "33333333-3333-3333-3333-333333333333"


class FakeCmds(object):
    @staticmethod
    def about(version=False):
        return "2025" if version else ""


class FakeApi(object):
    cmds = FakeCmds()
    VALIDATION_REPORT = {
        "summary": {
            "ERROR": 0,
            "WARNING": 1,
            "INFO": 2,
            "PASSED": 3,
            "total": 6,
        }
    }

    def __init__(self):
        self.text = {
            "rh_job_name": "Shot010_Lighting",
            "rh_project_name": "HiveProject",
            "rh_scene_path": r"D:\\Project\\scenes\\shot010.ma",
            "rh_project_path": r"D:\\Project",
            "rh_output_path": r"D:\\Project\\images",
            "rh_image_name": "beauty",
            "rh_department": "Lighting",
            "rh_comment": "Final",
            "rh_job_dependencies": DEP_JOB,
        }
        self.integer = {
            "rh_frame_start": 1,
            "rh_frame_end": 10,
            "rh_frame_step": 1,
            "rh_chunk_size": 4,
            "rh_concurrent_tasks": 2,
            "rh_retry_count": 3,
            "rh_timeout_minutes": 30,
            "rh_minimum_cores": 8,
            "rh_minimum_ram_gb": 16,
            "rh_minimum_gpus": 1,
            "rh_frame_padding": 4,
            "rh_width": 1920,
            "rh_height": 1080,
            "rh_priority": 70,
        }
        self.options = {
            "rh_renderer": "arnold",
            "rh_camera": "renderCam",
            "rh_image_format": "exr",
        }

    def get_scene_name(self):
        return "shot010"

    def get_scene_path(self):
        return r"D:\\Project\\scenes\\shot010.ma"

    def get_project_path(self):
        return r"D:\\Project"

    def get_default_output_path(self):
        return r"D:\\Project\\images"

    def get_frame_range(self):
        return 1, 10

    def get_resolution(self):
        return 1920, 1080

    def get_current_renderer(self):
        return "arnold"

    def get_renderable_camera(self):
        return "renderCam"

    def get_text(self, name, default=""):
        return self.text.get(name, default)

    def get_int(self, name, default=0):
        return int(self.integer.get(name, default))

    def get_option(self, name, default=""):
        return self.options.get(name, default)

    def get_render_layers(self):
        return [
            {
                "name": "defaultRenderLayer",
                "display_name": "defaultRenderLayer (Beauty / Master)",
                "source": "legacy",
                "renderable": False,
                "is_default": True,
            },
            {
                "name": "Characters",
                "display_name": "Characters",
                "source": "renderSetup",
                "renderable": True,
                "is_default": False,
            },
            {
                "name": "Environment",
                "display_name": "Environment",
                "source": "renderSetup",
                "renderable": True,
                "is_default": False,
            },
        ]


class FakeLayerSelector(object):
    def __init__(self, records, selected):
        self._records = list(records)
        self._selected = list(selected)

    def selected_values(self):
        return list(self._selected)

    def selected_records(self):
        selected = set(self._selected)
        return [dict(item) for item in self._records if item["name"] in selected]


class FakeWindow(object):
    worker_target_has_sync = True

    def pool_assignment_strategy_key(self):
        return "selected"

    def selected_pool_ids(self):
        return [POOL_A]

    def excluded_pool_ids(self):
        return []

    def pool_names_from_ids(self, values):
        return ["GPU"] if values else []

    def effective_pool_records(self):
        return [{"id": POOL_A, "name": "GPU"}]

    def effective_pool_worker_ids(self):
        return ["worker-a", "worker-b"]

    def eligible_worker_ids(self):
        return ["worker-a"]

    def worker_data_is_stale(self):
        return False

    def online_pool_workers(self):
        return [{"id": "worker-a"}]


class TaskBuilderTests(unittest.TestCase):
    def test_single_canonical_builder_contains_targeting_and_layers(self):
        api = FakeApi()
        selector = FakeLayerSelector(api.get_render_layers(), ["Characters", "Environment"])
        task = task_builder.build_task(
            api,
            window=FakeWindow(),
            widgets={"rh_render_layers": selector},
        )

        self.assertEqual(task["render_layer_names"], ["Characters", "Environment"])
        self.assertEqual(task["selected_pool_ids"], [POOL_A])
        self.assertEqual(task["effective_pool_ids"], [POOL_A])
        self.assertEqual(task["eligible_workers"], ["worker-a"])
        self.assertEqual(task["frames"]["task_count"], 3)
        self.assertEqual(task["job_dependencies"], [DEP_JOB])
        self.assertEqual(task["validation"]["warnings"], 1)
        self.assertEqual(task["software_info"]["maya_version"], "2025")
        self.assertNotIn("machine_limit", task)
        self.assertNotIn("machine_limit", task["farm"])

    def test_explicit_empty_selector_stays_empty_for_validation(self):
        api = FakeApi()
        selector = FakeLayerSelector(api.get_render_layers(), [])
        task = task_builder.build_task(
            api,
            window=FakeWindow(),
            widgets={"rh_render_layers": selector},
        )
        self.assertEqual(task["render_layers"], [])

    def test_legacy_call_without_selector_uses_scene_renderable_layers(self):
        api = FakeApi()
        task = task_builder.build_task(api, window=None, widgets=None)
        self.assertEqual(task["render_layer_names"], ["Characters", "Environment"])
        self.assertEqual(task["pool_strategy"], "all")

    def test_source_has_no_v2_wrapper_or_machine_limit_contract_hook(self):
        with open(os.path.join(ROOT, "ui", "qt_submitter_window.py"), "r", encoding="utf-8") as handle:
            window_source = handle.read()
        with open(os.path.join(ROOT, "renderhive_maya_submitter.py"), "r", encoding="utf-8") as handle:
            submitter_source = handle.read()
        with open(os.path.join(ROOT, "api", "payload.py"), "r", encoding="utf-8") as handle:
            payload_source = handle.read()
        with open(os.path.join(ROOT, "api", "contract.py"), "r", encoding="utf-8") as handle:
            contract_source = handle.read()

        self.assertNotIn("def build_task_v2", window_source)
        self.assertNotIn("_ORIGINAL_BUILD_TASK", window_source)
        self.assertIn("submission.task_builder", submitter_source)
        self.assertNotIn("machine_limit", payload_source)
        self.assertNotIn("job_machine_limit_field", contract_source)

    def test_installer_and_audit_require_task_builder(self):
        expression = 'os.path.join("submission", "task_builder.py")'
        for relative_path in (
            "renderhive_installer.py",
            os.path.join("tools", "production_audit.py"),
        ):
            with open(os.path.join(ROOT, relative_path), "r", encoding="utf-8") as handle:
                self.assertIn(expression, handle.read())


if __name__ == "__main__":
    unittest.main()
