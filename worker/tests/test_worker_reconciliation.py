from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import MagicMock, patch

from adapters.maya import MayaAdapter
from core.dcc_discovery import DCCInstallation
from core.task_normalizer import normalize_task
from core.task_normalizer import TaskContext


class WorkerReconciliationContractTests(unittest.TestCase):
    def test_maya_adapter_injects_arnold_pre_render_script(self):
        installations = [
            DCCInstallation(
                "maya",
                "2025",
                r"C:\Program Files\Autodesk\Maya2025",
                {
                    "render": r"C:\Program Files\Autodesk\Maya2025\bin\Render.exe",
                    "mayapy": r"C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe",
                },
            )
        ]
        adapter = MayaAdapter(installations)
        task = normalize_task(
            {
                "id": "t-1",
                "job_id": "j-1",
                "job_name": "TestJob",
                "layer_id": "l-1",
                "layer_name": "beauty",
                "dcc": "maya",
                "dcc_version": "2025",
                "renderer": "arnold",
                "scene_path": r"D:\projects\scene.ma",
                "output_path": r"D:\projects\output",
                "project_path": r"D:\projects",
                "camera": "renderCam",
                "frame_start": 1,
                "frame_end": 10,
                "frame_step": 1,
                "command": "",
                "scene_info": {
                    "renderer": "arnold",
                    "image_name": "beauty_render",
                    "image_format": "exr",
                    "frame_padding": 4,
                },
                "force_cpu": True,
            }
        )
        plan = adapter.build_plan(task)
        self.assertIn("-preRender", plan.command)
        self.assertIn("-fnc", plan.command)
        self.assertIn("3", plan.command)
        
        pre_render_idx = plan.command.index("-preRender")
        mel_cmd = plan.command[pre_render_idx + 1]
        self.assertIn('python("', mel_cmd)

    def test_app_source_contains_all_reconciled_logic(self):
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            source = f.read()

        # 1. capabilities_snapshot in claim_next_task
        self.assertIn('"capabilities_snapshot": self._last_system_info', source)

        # 2. Arnold GPU failure auto-retry
        self.assertIn("arnold_gpu_failed = True", source)
        self.assertIn("Unable to load Optix library", source)
        self.assertIn("GPU rendering is not available", source)
        self.assertIn("Failed to initialize GPU", source)
        self.assertIn('task.raw["force_cpu"] = True', source)

        # 3. 2MB bounded report_status payload
        self.assertIn("max_read_bytes = 2 * 1024 * 1024", source)
        self.assertIn('"worker_hostname": HOSTNAME', source)
        self.assertIn('"log_output": log_text', source)
        self.assertIn('"error_tail": error_tail', source)
        self.assertIn('"duration_seconds": duration_seconds', source)
        self.assertIn('"output_image_path": output_image_path', source)

        # 4. Task progress tracking & smooth progress animator
        self.assertIn("TaskProgressTracker", source)
        self.assertIn("SmoothProgressValue", source)
        self.assertIn("task_progress_signal", source)
