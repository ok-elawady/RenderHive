from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import MagicMock, patch

from adapters.maya import MayaAdapter
from core.dcc_discovery import DCCInstallation
from core.task_normalizer import normalize_task, TaskContext


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

    def test_daemon_source_contains_all_reconciled_logic(self):
        daemon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daemon", "worker_thread.py")
        with open(daemon_path, "r", encoding="utf-8") as f:
            thread_source = f.read()

        api_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daemon", "api_client.py")
        with open(api_path, "r", encoding="utf-8") as f:
            api_source = f.read()

        ui_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "main_window.py")
        with open(ui_path, "r", encoding="utf-8") as f:
            ui_source = f.read()

        # 1. capabilities_snapshot in claim_next_task & api_client
        self.assertIn("capabilities_snapshot=self._last_system_info", thread_source)
        self.assertIn('"capabilities_snapshot": capabilities_snapshot', api_source)

        # 2. Arnold GPU failure auto-retry
        self.assertIn("arnold_gpu_failed = True", thread_source)
        self.assertIn("Unable to load Optix library", thread_source)
        self.assertIn("GPU rendering is not available", thread_source)
        self.assertIn("Failed to initialize GPU", thread_source)
        self.assertIn('task.raw["force_cpu"] = True', thread_source)

        # 3. 2MB bounded report_status payload & peak memory
        self.assertIn("max_read_bytes = 2 * 1024 * 1024", api_source)
        self.assertIn('"worker_hostname": worker_hostname', api_source)
        self.assertIn('"log_output": log_text', api_source)
        self.assertIn('"error_tail": error_tail', api_source)
        self.assertIn('"duration_seconds": duration_seconds', api_source)
        self.assertIn('"output_image_path": output_image_path', api_source)
        self.assertIn('"max_memory_used_mb": max(0, int(max_memory_used_mb or 0))', api_source)

        # 4. Task progress tracking & smooth progress animator
        self.assertIn("TaskProgressTracker", thread_source)
        self.assertIn("task_progress_signal", thread_source)
        self.assertIn("SmoothProgressValue", ui_source)

    def test_heartbeat_payload_pool_names_handling(self):
        from daemon.worker_thread import WorkerThread

        # When pool_names is NOT set in profile -> omitted from payload
        thread_no_pools = WorkerThread("http://localhost:8000/api", "dummy", {}, profile={})
        payload1 = thread_no_pools.heartbeat_payload()
        self.assertNotIn("pool_names", payload1)

        # When custom_pools IS set in profile -> included as list in payload
        thread_with_pools = WorkerThread(
            "http://localhost:8000/api",
            "dummy",
            {},
            profile={"custom_pools": "GPU, VFX, Comp"},
        )
        payload2 = thread_with_pools.heartbeat_payload()
        self.assertIn("pool_names", payload2)
        self.assertEqual(payload2["pool_names"], ["GPU", "VFX", "Comp"])


if __name__ == "__main__":
    unittest.main()
