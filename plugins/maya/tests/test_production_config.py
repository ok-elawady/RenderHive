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

    def test_credentials_in_url_are_rejected(self):
        with self.assertRaises(Exception):
            config.normalize_config({"base_url": "http://user:pass@localhost:8000"})
