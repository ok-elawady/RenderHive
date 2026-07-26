from __future__ import absolute_import

import os
import shutil
import tempfile
import unittest

from core.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rh_state_test_")
        self.path = os.path.join(self.root, "state.db")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_save_load_and_health(self):
        store = StateStore(self.path)
        store.save_scene_state("scene", "identity", {"pool": "all"})
        self.assertEqual(store.load_scene_state("scene")["pool"], "all")
        report = store.health_report()
        self.assertEqual(report["quick_check"], "ok")
        self.assertEqual(report["scene_states"], 1)

    def test_corrupt_database_is_recovered(self):
        with open(self.path, "wb") as handle:
            handle.write(b"not-a-sqlite-database")
        store = StateStore(self.path)
        self.assertTrue(store.recovery_report["recovered"])
        self.assertEqual(store.quick_check(), "ok")
        self.assertTrue(os.path.exists(store.recovery_report["backup_path"]))
