from __future__ import absolute_import

import json
import os
import tempfile
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
from api.payload import build_job_request
from api.version import PLUGIN_VERSION


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(
    ROOT,
    "contracts",
    "renderhive_api_0_1_0.yaml",
)


class ApiContractTests(unittest.TestCase):
    def test_plugin_version(self):
        self.assertEqual(PLUGIN_VERSION, "1.9.12")

    def test_endpoint_configuration(self):
        self.assertTrue(
            validate_endpoint_config(DEFAULT_CONFIG["endpoints"])
        )
        self.assertNotIn("worker_ping", DEFAULT_CONFIG["endpoints"])
        self.assertNotIn("frame_dispatch", DEFAULT_CONFIG["endpoints"])

    @unittest.skipIf(
        yaml is None or jsonschema is None,
        "PyYAML and jsonschema are development dependencies",
    )
    def test_job_payload_matches_openapi(self):
        with open(SPEC_PATH, "r", encoding="utf-8") as handle:
            spec = yaml.safe_load(handle)

        task = {
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
            "effective_pool_ids": [],
            "effective_pool_names": [],
            "submission_mode": "Shared Storage",
            "software_info": {"maya_version": "2023"},
            "validation": {},
        }

        payload = build_job_request(task, DEFAULT_CONFIG)
        resolver = jsonschema.RefResolver.from_schema(spec)
        jsonschema.validate(
            payload,
            spec["components"]["schemas"]["JobCreate"],
            resolver=resolver,
        )

        self.assertEqual(
            payload["layers"][0]["scene_path"],
            "C:\\RenderHive\\scenes\\test.ma",
        )


if __name__ == "__main__":
    unittest.main()
