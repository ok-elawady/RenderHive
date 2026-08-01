import unittest

from core.task_normalizer import normalize_task


class TaskNormalizerTests(unittest.TestCase):
    def test_normalizes_houdini_layer_payload(self):
        task = normalize_task(
            {
                "id": 42,
                "command": '"hython" -m renderhive_houdini.worker.render_rop --scene "P:/shot/test.hip" --frame {frame}',
                "frame_start": 10,
                "frame_end": 14,
                "layer": {
                    "scene_path": "P:/shot/test.hip",
                    "scene_info": {
                        "dcc": "houdini",
                        "houdini_version": "20.5.278",
                        "renderer": "Karma XPU",
                        "render_node": "/stage/usdrender_rop1",
                        "camera": "/cameras/cam1",
                        "output_path": "P:/shot/render/beauty.$F4.exr",
                        "execution": {"mode": "hython", "usd_output_path": "P:/shot/render.usd"},
                    },
                },
            }
        )
        self.assertEqual(task.dcc, "houdini")
        self.assertEqual(task.dcc_version, "20.5.278")
        self.assertEqual(task.render_node, "/stage/usdrender_rop1")
        self.assertEqual(task.frame_start, 10)
        self.assertEqual(task.frame_end, 14)

    def test_houdini_override_flags_and_resolution_are_preserved(self):
        task = normalize_task(
            {
                "id": 43,
                "dcc": "houdini",
                "scene_path": "P:/shot/test.hip",
                "render_node": "/stage/usdrender_rop1",
                "camera": "/cameras/cam2",
                "renderer": "Karma XPU",
                "output_path": "P:/shot/render/beauty.$F4.exr",
                "scene_info": {
                    "resolution": {"width": 1920, "height": 1080},
                    "execution": {
                        "mode": "husk",
                        "camera_override": True,
                        "renderer_override": True,
                        "output_override": True,
                        "resolution_override": True,
                    },
                },
            }
        )
        self.assertTrue(task.camera_override)
        self.assertTrue(task.renderer_override)
        self.assertTrue(task.output_override)
        self.assertTrue(task.resolution_override)
        self.assertEqual(task.resolution_width, 1920)
        self.assertEqual(task.resolution_height, 1080)

    def test_legacy_task_defaults_to_maya(self):
        task = normalize_task(
            {
                "id": 1,
                "command": 'Render.exe -s {START_FRAME} -e {END_FRAME} "{SCENE_PATH}"',
                "scene_path": "P:/show/scene.ma",
                "frame_start": 1,
                "frame_end": 2,
            }
        )
        self.assertEqual(task.dcc, "maya")


if __name__ == "__main__":
    unittest.main()
