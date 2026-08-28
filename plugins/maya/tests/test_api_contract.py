from __future__ import absolute_import

import os
import unittest

try:
    import yaml
except ImportError:
    yaml = None

try:
    import jsonschema
except ImportError:
    jsonschema = None

from api.config import DEFAULT_CONFIG
from api.contract import validate_endpoint_config
from api.payload import PayloadError, build_job_request, build_maya_command
from api.version import API_CONTRACT_VERSION, PLUGIN_VERSION


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(
    ROOT,
    "contracts",
    "renderhive_api_0_2_0.yaml",
)


class ApiContractTests(unittest.TestCase):
    def base_task(self):
        return {
            "project_name": "ContractTest",
            "job_name": "MayaContractTest",
            "department": "Lighting",
            "priority": 50,
            "scene_path": "C:/RenderHive/scenes/test.ma",
            "project_path": "C:/RenderHive",
            "output_path": "C:/RenderHive/images",
            "renderer": "arnold",
            "camera": "renderCam",
            "image_name": "beauty",
            "image_format": "exr",
            "frame_padding": 4,
            "width": 1920,
            "height": 1080,
            "frame_start": 1,
            "frame_end": 10,
            "frame_step": 1,
            "chunk_size": 2,
            "retry_count": 2,
            "task_timeout_minutes": 60,
            "concurrent_tasks": 1,
            "minimum_cores": 8,
            "minimum_ram_gb": 16,
            "minimum_gpus": 1,
            "pool_strategy": "all",
            "selected_pool_ids": [],
            "excluded_pool_ids": [],
            "effective_pool_ids": [],
            "effective_pool_names": [],
            "job_dependencies": [],
            "submission_mode": "Shared Storage",
            "software_info": {"maya_version": "2023"},
            "validation": {},
        }

    def test_plugin_and_contract_version(self):
        self.assertEqual(PLUGIN_VERSION, "1.0.0")
        self.assertEqual(API_CONTRACT_VERSION, "0.2.0")

    def test_endpoint_configuration(self):
        self.assertTrue(
            validate_endpoint_config(DEFAULT_CONFIG["endpoints"])
        )
        self.assertNotIn("worker_ping", DEFAULT_CONFIG["endpoints"])
        self.assertNotIn("frame_dispatch", DEFAULT_CONFIG["endpoints"])
        self.assertNotIn("job_layer_frames", DEFAULT_CONFIG["endpoints"])
        self.assertIn("job_layer_tasks", DEFAULT_CONFIG["endpoints"])

    def test_start_suspended_is_not_submitted(self):
        task = self.base_task()
        task["start_suspended"] = True  # stale state from an older plugin build
        payload = build_job_request(task, DEFAULT_CONFIG)
        self.assertNotIn("start_suspended", payload)
        self.assertNotIn("start_suspended", payload.get("submission", {}))

    @unittest.skipIf(
        yaml is None or jsonschema is None,
        "PyYAML and jsonschema are development dependencies",
    )
    def test_job_payload_matches_openapi(self):
        with open(SPEC_PATH, "r", encoding="utf-8") as handle:
            spec = yaml.safe_load(handle)

        task = self.base_task()
        task.update({
            "pool_strategy": "selected",
            "selected_pool_ids": ["11111111-1111-1111-1111-111111111111"],
            "selected_pool_names": ["GPU"],
            "effective_pool_ids": ["11111111-1111-1111-1111-111111111111"],
            "effective_pool_names": ["GPU"],
            "job_dependencies": ["22222222-2222-2222-2222-222222222222"],
        })

        payload = build_job_request(task, DEFAULT_CONFIG)
        validation_schema = {
            "$ref": "#/components/schemas/JobCreate",
            "components": spec["components"],
        }
        jsonschema.validate(payload, validation_schema)

        self.assertEqual(
            payload["layers"][0]["scene_path"],
            "C:\\RenderHive\\scenes\\test.ma",
        )
        self.assertEqual(
            payload["included_pools"],
            ["11111111-1111-1111-1111-111111111111"],
        )
        self.assertEqual(payload["excluded_pools"], [])
        self.assertEqual(
            payload["dependencies"],
            [{
                "type": "JOB_ON_JOB",
                "parent_job": "22222222-2222-2222-2222-222222222222",
            }],
        )
        self.assertNotIn("GPU", payload["layers"][0]["tags"])
        self.assertEqual(payload["layers"][0]["min_cores"], 8)
        self.assertEqual(payload["layers"][0]["min_memory_mb"], 16 * 1024)
        self.assertEqual(payload["layers"][0]["min_gpus"], 1)
        self.assertEqual(
            payload["layers"][0]["scene_info"]["api_contract_version"],
            "0.2.0",
        )

    def test_all_except_pool_mapping(self):
        task = self.base_task()
        task.update({
            "pool_strategy": "all_except",
            "excluded_pool_ids": ["33333333-3333-3333-3333-333333333333"],
        })
        payload = build_job_request(task, DEFAULT_CONFIG)
        self.assertEqual(payload["included_pools"], [])
        self.assertEqual(
            payload["excluded_pools"],
            ["33333333-3333-3333-3333-333333333333"],
        )

    def test_invalid_dependency_uuid_is_rejected(self):
        task = self.base_task()
        task["job_dependencies"] = ["not-a-uuid"]
        with self.assertRaises(PayloadError):
            build_job_request(task, DEFAULT_CONFIG)

    def test_multi_render_layers_create_backend_layers(self):
        task = self.base_task()
        task["render_layers"] = [
            {
                "name": "defaultRenderLayer",
                "display_name": "Master Layer",
                "source": "renderSetup",
                "is_default": True,
            },
            {
                "name": "characters",
                "display_name": "characters",
                "source": "renderSetup",
                "is_default": False,
            },
        ]

        payload = build_job_request(task, DEFAULT_CONFIG)
        self.assertEqual(
            [layer["name"] for layer in payload["layers"]],
            ["defaultRenderLayer", "characters"],
        )
        self.assertNotIn(
            '-rl "defaultRenderLayer"',
            payload["layers"][0]["command"],
        )
        self.assertIn(
            '-rl "characters"',
            payload["layers"][1]["command"],
        )
        self.assertEqual(
            payload["layers"][1]["env"]["RENDERHIVE_MAYA_RENDER_LAYER"],
            "characters",
        )
        self.assertEqual(
            payload["layers"][1]["scene_info"]["render_layer"],
            "characters",
        )

    def test_multi_render_layer_output_prefixes_are_namespaced(self):
        task = self.base_task()
        task["render_layers"] = [
            {"name": "characters"},
            {"name": "environment"},
        ]
        payload = build_job_request(task, DEFAULT_CONFIG)
        prefixes = [
            layer["scene_info"]["image_name"]
            for layer in payload["layers"]
        ]
        self.assertEqual(
            prefixes,
            ["characters/beauty", "environment/beauty"],
        )
        self.assertEqual(len(prefixes), len(set(prefixes)))

    def test_explicit_selection_does_not_inject_default_layer(self):
        task = self.base_task()
        task["render_layers"] = [
            {"name": "Characters"},
            {"name": "Environment"},
        ]
        payload = build_job_request(task, DEFAULT_CONFIG)
        self.assertEqual(
            [layer["name"] for layer in payload["layers"]],
            ["Characters", "Environment"],
        )
        self.assertNotIn(
            "defaultRenderLayer",
            [layer["name"] for layer in payload["layers"]],
        )

    def test_default_layer_is_submitted_only_when_explicitly_selected(self):
        task = self.base_task()
        task["render_layers"] = [{"name": "defaultRenderLayer", "is_default": True}]
        payload = build_job_request(task, DEFAULT_CONFIG)
        self.assertEqual(
            [layer["name"] for layer in payload["layers"]],
            ["defaultRenderLayer"],
        )
        self.assertNotIn('-rl "defaultRenderLayer"', payload["layers"][0]["command"])

    def test_single_explicit_layer_output_is_namespaced(self):
        task = self.base_task()
        task["render_layers"] = [{"name": "Characters"}]
        payload = build_job_request(task, DEFAULT_CONFIG)
        self.assertEqual(
            payload["layers"][0]["scene_info"]["image_name"],
            "Characters/beauty",
        )

    def test_render_layer_can_override_shared_settings(self):
        task = self.base_task()
        task["render_layers"] = [{
            "name": "preview",
            "camera": "shotCam",
            "frame_start": 101,
            "frame_end": 105,
            "frame_step": 2,
            "chunk_size": 1,
            "minimum_gpus": 2,
        }]
        payload = build_job_request(task, DEFAULT_CONFIG)
        layer = payload["layers"][0]
        self.assertEqual(layer["frame_range"], "101-105x2")
        self.assertEqual(layer["chunk_size"], 1)
        self.assertEqual(layer["min_gpus"], 2)
        self.assertIn('-cam "shotCam"', layer["command"])

    def test_duplicate_render_layer_names_are_rejected(self):
        task = self.base_task()
        task["render_layers"] = [
            {"name": "characters"},
            {"name": "characters"},
        ]
        with self.assertRaises(PayloadError):
            build_job_request(task, DEFAULT_CONFIG)

    def test_empty_explicit_render_layer_selection_is_rejected(self):
        task = self.base_task()
        task["render_layers"] = []
        with self.assertRaises(PayloadError):
            build_job_request(task, DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()
