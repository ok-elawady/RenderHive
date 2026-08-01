from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.ui_helpers import (
    build_task_ui_payload,
    extract_progress_frame,
    format_bytes,
    format_duration,
    frame_progress_percent,
    merge_job_detail,
    pool_names_from_worker,
    select_worker_record,
    split_csv,
)


class UIHelperTests(unittest.TestCase):
    def test_formatters(self):
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_duration(3661), "01h 01m 01s")

    def test_split_csv_deduplicates(self):
        self.assertEqual(split_csv("GPU, overnight;gpu, studio-a"), ["GPU", "overnight", "studio-a"])

    def test_build_task_ui_payload(self):
        normalized = SimpleNamespace(
            task_id="task-01",
            frame_start=1,
            frame_end=5,
            frame_step=1,
            dcc="houdini",
            dcc_version="20.5.278",
            renderer="karma_cpu",
            execution_mode="husk",
            scene_path="D:/project/test.hip",
            project_path="D:/project",
            output_path="D:/project/render/test.$F4.exr",
            render_node="/stage/usdrender_rop1",
            camera="/cameras/cam1",
            command="",
        )
        payload = build_task_ui_payload(
            {
                "id": "task-01",
                "name": "Frames 1-5",
                "job": {
                    "id": "job-01",
                    "visible_name": "Test Job",
                    "department": "Lighting",
                    "priority": 50,
                },
                "layer": {"name": "Beauty"},
            },
            normalized,
        )
        self.assertEqual(payload["job_name"], "Test Job")
        self.assertEqual(payload["task_id"], "task-01")
        self.assertEqual(payload["frame_range"], "1-5 x1")
        self.assertEqual(payload["total_frames"], 5)
        self.assertEqual(payload["dcc"], "Houdini")

    def test_merge_job_detail(self):
        merged = merge_job_detail(
            {"job_name": "Old"},
            {
                "visible_name": "New",
                "user": "artist",
                "included_pools": [{"name": "FX"}, {"name": "VFX"}],
            },
        )
        self.assertEqual(merged["job_name"], "New")
        self.assertEqual(merged["job_user"], "artist")
        self.assertEqual(merged["pool"], "FX, VFX")

    def test_progress_parser_and_percent(self):
        self.assertEqual(extract_progress_frame("Rendering frame 3", 1, 10), 3)
        self.assertIsNone(extract_progress_frame("Rendering frame 30", 1, 10))
        self.assertEqual(frame_progress_percent(5, 1, 5, 1), 100)
        self.assertEqual(frame_progress_percent(3, 1, 5, 1), 60)

    def test_worker_record_selection_and_pools(self):
        response = {
            "results": [
                {"hostname": "OTHER", "pools": []},
                {"hostname": "NODE-01", "pools": [{"name": "FX"}, {"name": "GPU"}]},
            ]
        }
        worker = select_worker_record(response, "node-01")
        self.assertEqual(worker["hostname"], "NODE-01")
        self.assertEqual(pool_names_from_worker(worker), ["FX", "GPU"])


if __name__ == "__main__":
    unittest.main()
