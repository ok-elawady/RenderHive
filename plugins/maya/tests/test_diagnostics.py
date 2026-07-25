from __future__ import absolute_import

import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

from api.config import save_config
from core.diagnostics import create_support_bundle


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rh_diag_test_")
        self.env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.root}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_support_bundle_redacts_token(self):
        save_config({"auth": {"type": "token", "token": "SUPER_SECRET_TOKEN"}})
        path = create_support_bundle()
        self.assertTrue(os.path.isfile(path))
        with zipfile.ZipFile(path, "r") as archive:
            combined = b"\n".join(archive.read(name) for name in archive.namelist())
        self.assertNotIn(b"SUPER_SECRET_TOKEN", combined)
        self.assertIn(b"manifest.json", "\n".join(zipfile.ZipFile(path).namelist()).encode())
