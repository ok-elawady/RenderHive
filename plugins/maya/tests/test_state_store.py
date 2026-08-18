from __future__ import absolute_import

import gc
import os
import shutil
import sqlite3
import tempfile
import unittest
import warnings

from core.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rh_state_test_")
        self.path = os.path.join(self.root, "state.db")

    def tearDown(self):
        gc.collect()
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

    def test_connection_context_closes_connection(self):
        store = StateStore(self.path)
        with store._connection() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_failed_transaction_is_rolled_back_and_closed(self):
        store = StateStore(self.path)
        with self.assertRaises(RuntimeError):
            with store._connection() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                    ("rollback_probe", "should_not_commit"),
                )
                raise RuntimeError("force rollback")
        self.assertEqual(store.get_metadata("rollback_probe", "missing"), "missing")
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_scene_state_restores_across_store_instances(self):
        first = StateStore(self.path)
        first.save_scene_state(
            "scene-key",
            "C:/Project/scenes/shot.ma",
            {"selected_render_layers": ["Characters", "Environment"], "chunk_size": 4},
        )
        del first
        gc.collect()

        second = StateStore(self.path)
        state = second.load_scene_state("scene-key")
        self.assertEqual(state["selected_render_layers"], ["Characters", "Environment"])
        self.assertEqual(state["chunk_size"], 4)

    def test_backup_is_consistent_and_reopenable(self):
        store = StateStore(self.path)
        store.save_scene_state("scene", "identity", {"renderer": "arnold"})
        store.save_app_state("selected_pool_v13", "GPU")
        backup_path = store.backup(os.path.join(self.root, "backup", "maya_state.db"))

        backup_store = StateStore(backup_path)
        self.assertEqual(backup_store.quick_check(), "ok")
        self.assertEqual(backup_store.load_scene_state("scene")["renderer"], "arnold")
        self.assertEqual(backup_store.load_app_state("selected_pool_v13"), "GPU")

    def test_operations_do_not_emit_unclosed_sqlite_resource_warnings(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            store = StateStore(self.path)
            store.save_scene_state("scene", "identity", {"pool": "all"})
            store.load_scene_state("scene")
            store.save_app_state("worker_pools_v13", {"GPU": ["worker-01"]})
            store.load_app_state("worker_pools_v13")
            store.health_report()
            store.backup(os.path.join(self.root, "warning_probe_backup.db"))
            del store
            gc.collect()

        sqlite_warnings = [
            item for item in caught
            if issubclass(item.category, ResourceWarning)
            and "sqlite3.Connection" in str(item.message)
        ]
        self.assertEqual(sqlite_warnings, [])
