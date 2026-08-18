from __future__ import absolute_import

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from api import config


class ProductionConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rh_config_test_")
        self.env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.root}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_string_booleans_are_normalized(self):
        value = config.normalize_config({"enabled": "false", "verify_ssl": "true"})
        self.assertFalse(value["enabled"])
        self.assertTrue(value["verify_ssl"])

    def test_invalid_config_is_backed_up_and_recovered(self):
        path = config.get_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not-json")
        value = config.load_config()
        self.assertEqual(value["schema_version"], config.CONFIG_SCHEMA_VERSION)
        backups = [name for name in os.listdir(os.path.dirname(path)) if ".corrupt_" in name]
        self.assertTrue(backups)


    def test_legacy_frame_endpoint_keys_are_removed(self):
        value = config.normalize_config({
            "endpoints": {
                "job_layer_frames": "/legacy/frames/",
                "job_layer_frame_detail": "/legacy/frames/{frame_id}/",
            }
        })
        self.assertNotIn("job_layer_frames", value["endpoints"])
        self.assertNotIn("job_layer_frame_detail", value["endpoints"])
        self.assertIn("job_layer_tasks", value["endpoints"])


    def test_pre_0_2_contract_settings_are_migrated(self):
        value = config.normalize_config({
            "schema_version": 3,
            "contract": {
                "version": "0.1.0",
                "job_pool_targeting": False,
                "job_dependencies": False,
                "layer_pool_ids_field": "legacy_pool_ids",
                "job_dependencies_field": "legacy_dependencies",
                "job_start_suspended_field": "start_suspended",
                "job_machine_limit_field": "machine_limit",
            },
            "maya": {"use_pool_as_tag": True},
        })
        self.assertEqual(value["contract"]["version"], "0.2.0")
        self.assertTrue(value["contract"]["job_pool_targeting"])
        self.assertTrue(value["contract"]["job_dependencies"])
        self.assertNotIn("job_start_suspended_field", value["contract"])
        self.assertNotIn("job_machine_limit_field", value["contract"])
        self.assertNotIn("layer_pool_ids_field", value["contract"])
        self.assertNotIn("job_dependencies_field", value["contract"])
        self.assertNotIn("use_pool_as_tag", value["maya"])

    def test_credentials_in_url_are_rejected(self):
        with self.assertRaises(Exception):
            config.normalize_config({"base_url": "http://user:pass@localhost:8000"})
