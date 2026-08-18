from __future__ import absolute_import

import os
import shutil
import tempfile
import unittest

from submission.task_validation import validate_task
from validation import submission_checks
from ui.worker_data import worker_meets_requirements, worker_gpu_count


POOL_A = "11111111-1111-1111-1111-111111111111"
POOL_B = "22222222-2222-2222-2222-222222222222"
DEP_A = "33333333-3333-3333-3333-333333333333"


class ProductionSubmissionValidationTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="renderhive_maya_validation_")
        self.scene = os.path.join(self.root, "shot.ma")
        self.output = os.path.join(self.root, "images")
        os.makedirs(self.output)
        with open(self.scene, "w", encoding="utf-8") as handle:
            handle.write("// Maya ASCII\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def valid_task(self):
        return {
            "job_name": "Shot010",
            "scene_path": self.scene,
            "project_path": self.root,
            "output_path": self.output,
            "frame_start": 1,
            "frame_end": 10,
            "frame_step": 1,
            "chunk_size": 2,
            "concurrent_tasks": 1,
            "retry_count": 2,
            "task_timeout_minutes": 90,
            "camera": "renderCam",
            "renderer": "arnold",
            "image_name": "beauty",
            "image_format": "exr",
            "frame_padding": 4,
            "width": 1920,
            "height": 1080,
            "minimum_cores": 8,
            "minimum_ram_gb": 16,
            "minimum_gpus": 1,
            "render_layers": [
                {"name": "defaultRenderLayer", "renderable": True},
                {"name": "Characters", "renderable": True},
            ],
            "render_layer_missing_names": [],
            "pool_strategy": "selected",
            "selected_pool_ids": [POOL_A],
            "excluded_pool_ids": [],
            "effective_pool_ids": [POOL_A],
            "job_dependencies": [DEP_A],
            "validation": {"errors": 0},
        }

    def test_valid_production_task_passes(self):
        self.assertEqual(validate_task(self.valid_task()), [])

    def test_render_layer_and_arnold_failures_are_blocking(self):
        task = self.valid_task()
        task["renderer"] = "mayaHardware2"
        task["render_layers"] = []
        task["render_layer_missing_names"] = ["Environment"]
        errors = validate_task(task)
        self.assertTrue(any("Arnold only" in item for item in errors))
        self.assertTrue(any("Select at least one Maya render layer" in item for item in errors))
        self.assertTrue(any("Environment" in item for item in errors))

    def test_scheduling_and_hardware_failures_are_blocking(self):
        task = self.valid_task()
        task.update({
            "frame_step": 0,
            "chunk_size": 0,
            "concurrent_tasks": 0,
            "retry_count": -1,
            "task_timeout_minutes": -10,
            "minimum_cores": -1,
            "minimum_ram_gb": -2,
            "minimum_gpus": -3,
        })
        errors = validate_task(task)
        self.assertGreaterEqual(len(errors), 8)

    def test_pool_ids_strategy_and_dependencies_are_validated(self):
        task = self.valid_task()
        task["selected_pool_ids"] = ["not-a-uuid"]
        task["effective_pool_ids"] = []
        task["job_dependencies"] = ["broken", DEP_A, DEP_A]
        errors = validate_task(task)
        self.assertTrue(any("Pool id" in item for item in errors))
        self.assertTrue(any("Job dependency must be" in item for item in errors))
        self.assertTrue(any("selected more than once" in item for item in errors))

    def test_validation_report_errors_cannot_be_bypassed(self):
        task = self.valid_task()
        task["validation"] = {"errors": 2}
        self.assertIn(
            "Scene validation still contains blocking errors.",
            validate_task(task),
        )

    def test_worker_resource_preview_matches_requirements(self):
        worker = {
            "cores": 16,
            "memory_mb": 32768,
            "gpu_models": ["NVIDIA RTX"],
            "system_info": {},
        }
        self.assertEqual(worker_gpu_count(worker), 1)
        self.assertTrue(worker_meets_requirements(worker, 8, 16, 1))
        self.assertFalse(worker_meets_requirements(worker, 32, 16, 1))
        self.assertFalse(worker_meets_requirements(worker, 8, 64, 1))
        self.assertFalse(worker_meets_requirements(worker, 8, 16, 2))

    def test_submission_validation_reports_hardware_mismatch_as_warning(self):
        context = self.valid_task()
        context.update({
            "worker_targeting_synced": True,
            "online_pool_worker_count": 2,
            "eligible_worker_count": 0,
        })
        results = submission_checks.check_hardware_requirements(context)
        self.assertEqual(results[0]["severity"], "WARNING")
        self.assertEqual(results[0]["code"], "NO_WORKER_MEETS_HARDWARE_REQUIREMENTS")

    def test_submission_checks_validate_selected_pool_requirement(self):
        context = self.valid_task()
        context["selected_pool_ids"] = []
        context["effective_pool_ids"] = []
        results = submission_checks.check_pool_targeting(context)
        codes = {item["code"] for item in results}
        self.assertIn("POOL_SELECTION_EMPTY", codes)

    def test_cleanup_removed_duplicate_and_legacy_validation_paths(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "ui", "qt_submitter_window.py"), "r", encoding="utf-8") as handle:
            qt_source = handle.read()
        with open(os.path.join(root, "validation", "scene_checks.py"), "r", encoding="utf-8") as handle:
            scene_source = handle.read()
        with open(os.path.join(root, "api", "maya_bridge.py"), "r", encoding="utf-8") as handle:
            bridge_source = handle.read()
        with open(os.path.join(root, "ui", "targeting_widgets.py"), "r", encoding="utf-8") as handle:
            targeting_source = handle.read()

        self.assertNotIn("_renderhive_legacy_validate_task", qt_source)
        self.assertNotIn("def validate_submission_task", qt_source)
        self.assertNotIn("def check_renderer", scene_source)
        self.assertNotIn("def check_camera", scene_source)
        self.assertNotIn("def get_api_layer_frames", bridge_source)
        self.assertNotIn("class WorkerSelectionDialog", targeting_source)
        self.assertNotIn("class ApiWorkerPoolManagerDialog", targeting_source)


if __name__ == "__main__":
    unittest.main()
