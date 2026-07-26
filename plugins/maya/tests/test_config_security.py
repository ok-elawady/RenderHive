from __future__ import absolute_import

import json
import os
import shutil
import tempfile
import unittest


class ConfigSecurityTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="renderhive_config_test_")
        self.previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.root

        from api import config
        self.config = config

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.previous
        shutil.rmtree(self.root, ignore_errors=True)

    def test_token_is_not_written_to_json(self):
        saved = self.config.save_config({
            "enabled": True,
            "auth": {
                "type": "token",
                "token": "test-secret-token",
            },
        })
        self.assertEqual(
            saved["auth"]["token"],
            "test-secret-token",
        )

        with open(
            self.config.get_config_path(),
            "r",
            encoding="utf-8",
        ) as handle:
            disk = json.load(handle)

        self.assertEqual(disk["auth"]["token"], "")
        self.assertEqual(
            self.config.load_config()["auth"]["token"],
            "test-secret-token",
        )


if __name__ == "__main__":
    unittest.main()
