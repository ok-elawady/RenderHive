import os
import tempfile
import unittest

from adapters.houdini import HoudiniAdapter
from adapters.maya import MayaAdapter
from core.dcc_discovery import DCCInstallation
from core.task_normalizer import normalize_task


class AdapterTests(unittest.TestCase):
    def test_maya_uses_requested_year(self):
        installations = [
            DCCInstallation("maya", "2025", "C:/Maya2025", {"render": "C:/Maya2025/bin/Render.exe", "mayapy": ""}),
            DCCInstallation("maya", "2023", "C:/Maya2023", {"render": "C:/Maya2023/bin/Render.exe", "mayapy": ""}),
        ]
        task = normalize_task(
            {
                "id": 1,
                "dcc": "maya",
                "dcc_version": "2023",
                "command": 'Render.exe -s {START_FRAME} -e {END_FRAME} "{SCENE_PATH}"',
                "scene_path": "P:/scene.ma",
                "frame_start": 1,
                "frame_end": 3,
            }
        )
        plan = MayaAdapter(installations).build_plan(task)
        self.assertIn("Maya2023", plan.command[0])

    def test_houdini_builds_hython_range_command(self):
        installations = [
            DCCInstallation(
                "houdini",
                "20.5.278",
                "C:/Houdini20.5",
                {"hython": "C:/Houdini20.5/bin/hython.exe", "husk": "C:/Houdini20.5/bin/husk.exe"},
            )
        ]
        task = normalize_task(
            {
                "id": 2,
                "dcc": "houdini",
                "dcc_version": "20.5.278",
                "scene_path": "P:/scene.hip",
                "render_node": "/out/karma1",
                "frame_start": 1,
                "frame_end": 5,
                "frame_step": 1,
                "execution_mode": "hython",
            }
        )
        plan = HoudiniAdapter(installations).build_plan(task)
        self.assertEqual(plan.command[0], "C:/Houdini20.5/bin/hython.exe")
        self.assertIn("--start", plan.command)
        self.assertIn("--end", plan.command)
        self.assertIn("/out/karma1", plan.command)

    def test_houdini_usd_render_rop_uses_hython_then_invokes_husk(self):
        installations = [
            DCCInstallation(
                "houdini",
                "20.5.278",
                "C:/Houdini20.5",
                {"hython": "C:/Houdini20.5/bin/hython.exe", "husk": "C:/Houdini20.5/bin/husk.exe"},
            )
        ]
        task = normalize_task(
            {
                "id": 3,
                "dcc": "houdini",
                "dcc_version": "20.5.278",
                "scene_path": "P:/scene.hip",
                "render_node": "/stage/usdrender_rop1",
                "frame_start": 1,
                "frame_end": 1,
                "execution_mode": "husk",
                "usd_output_path": "P:/render/__render__.usd",
                "command": '"hython" -m renderhive_houdini.worker.render_rop --scene "P:/scene.hip" --frame {FRAME}',
            }
        )
        plan = HoudiniAdapter(installations).build_plan(task)
        self.assertEqual(plan.command[0], "C:/Houdini20.5/bin/hython.exe")
        self.assertIn("/stage/usdrender_rop1", plan.command)
        self.assertIn("invokes husk", plan.description)

    def test_standalone_usd_uses_direct_husk_and_ignores_hython_preview_command(self):
        installations = [
            DCCInstallation(
                "houdini",
                "20.5.278",
                "C:/Houdini20.5",
                {"hython": "C:/Houdini20.5/bin/hython.exe", "husk": "C:/Houdini20.5/bin/husk.exe"},
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            usd_path = os.path.join(temp_dir, "scene.usd")
            with open(usd_path, "w", encoding="utf-8") as handle:
                handle.write("#usda 1.0\n")
            task = normalize_task(
                {
                    "id": 4,
                    "dcc": "houdini",
                    "dcc_version": "20.5.278",
                    "scene_path": usd_path,
                    "execution_mode": "husk",
                    "usd_output_path": usd_path,
                    "command": '"hython" -m renderhive_houdini.worker.render_rop --scene "{}"'.format(usd_path),
                }
            )
            plan = HoudiniAdapter(installations).build_plan(task)
            self.assertEqual(plan.command[0], "C:/Houdini20.5/bin/husk.exe")
            self.assertEqual(plan.command[1], usd_path)
            self.assertIn("direct husk", plan.description)


if __name__ == "__main__":
    unittest.main()
