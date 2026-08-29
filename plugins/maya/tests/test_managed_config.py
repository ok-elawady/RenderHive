from __future__ import absolute_import

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from api import config


class ManagedConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rh_managed_config_")
        self.local = os.path.join(self.root, "local")
        self.program = os.path.join(self.root, "program")
        empty_env = os.path.join(self.root, ".env.empty")
        with open(empty_env, "w", encoding="utf-8") as handle:
            handle.write("")
        clean_env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("RENDERHIVE_") and k not in ("NEXT_PUBLIC_API_URL", "API_URL")
        }
        clean_env["LOCALAPPDATA"] = self.local
        clean_env["PROGRAMDATA"] = self.program
        clean_env["RENDERHIVE_ENV_FILE"] = empty_env
        self.env = mock.patch.dict(
            os.environ,
            clean_env,
            clear=True,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_machine_config_overrides_user_url(self):
        config.save_config({
            "enabled": True,
            "base_url": "http://user-host:8000",
            "auth": {"type": "none", "token": ""},
        })

        path = config.get_machine_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({
                "enabled": True,
                "base_url": "http://studio-host:8000",
            }, handle)

        value = config.load_config()
        self.assertEqual(value["base_url"], "http://studio-host:8000")
        self.assertEqual(value["_config_source"], "Managed")

    def test_environment_has_highest_priority(self):
        path = config.get_machine_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"base_url": "http://studio-host:8000"}, handle)

        with mock.patch.dict(
            os.environ,
            {"RENDERHIVE_API_URL": "http://environment-host:9000"},
            clear=False,
        ):
            value = config.load_config()

        self.assertEqual(value["base_url"], "http://environment-host:9000")
        self.assertEqual(value["_config_source"], "Environment")

    def test_machine_file_cannot_supply_plaintext_token(self):
        config.save_config({
            "auth": {"type": "token", "token": "protected-token"},
        })
        path = config.get_machine_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({
                "auth": {"type": "token", "token": "plaintext-machine-token"}
            }, handle)

        value = config.load_config()
        self.assertEqual(value["auth"]["token"], "protected-token")


if __name__ == "__main__":
    unittest.main()
