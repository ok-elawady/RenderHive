"""SQLite persistence for per-HIP submission settings with integrity recovery."""

from __future__ import absolute_import

import datetime
import json
import os
import shutil
import sqlite3
import threading

from renderhive_houdini.core.constants import STATE_SCHEMA_VERSION
from renderhive_houdini.core.paths import ensure_directory, state_backup_path, state_database_path


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def scene_key(path, fallback="untitled"):
    value = str(path or "").strip()
    if value:
        return os.path.normcase(os.path.abspath(value))
    return "__untitled__:{}".format(str(fallback or "untitled").strip().lower())


class StateStore(object):
    def __init__(self, path=None):
        self.path = os.path.abspath(path or state_database_path())
        self._lock = threading.RLock()
        ensure_directory(os.path.dirname(self.path))
        self._initialize_with_recovery()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_with_recovery(self):
        try:
            self._initialize()
            if not self.integrity_ok():
                raise sqlite3.DatabaseError("SQLite integrity check failed")
        except Exception:
            self._recover_corrupt_database()
            self._initialize()

    def _initialize(self):
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS scene_state ("
                    "scene_key TEXT PRIMARY KEY, scene_path TEXT NOT NULL, "
                    "schema_version INTEGER NOT NULL, payload TEXT NOT NULL, "
                    "updated_at TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
                    (str(STATE_SCHEMA_VERSION),),
                )
                connection.commit()
            finally:
                connection.close()

    def _recover_corrupt_database(self):
        if not os.path.exists(self.path):
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupt = "{}.corrupt_{}".format(self.path, stamp)
        try:
            shutil.copy2(self.path, state_backup_path())
        except Exception:
            pass
        try:
            os.replace(self.path, corrupt)
        except Exception:
            try:
                os.remove(self.path)
            except Exception:
                pass

    def integrity_ok(self):
        if not os.path.isfile(self.path):
            return True
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute("PRAGMA quick_check").fetchone()
                return bool(row and str(row[0]).lower() == "ok")
            finally:
                connection.close()

    def load(self, path, fallback="untitled"):
        key = scene_key(path, fallback)
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT payload FROM scene_state WHERE scene_key = ?", (key,)
                ).fetchone()
            finally:
                connection.close()
        if not row:
            return {}
        try:
            value = json.loads(row[0])
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def save(self, path, payload, fallback="untitled"):
        key = scene_key(path, fallback)
        text = json.dumps(payload or {}, sort_keys=True, default=str)
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    "INSERT OR REPLACE INTO scene_state "
                    "(scene_key, scene_path, schema_version, payload, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, str(path or ""), STATE_SCHEMA_VERSION, text, _utc_now()),
                )
                connection.commit()
            finally:
                connection.close()

    def delete(self, path, fallback="untitled"):
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    "DELETE FROM scene_state WHERE scene_key = ?", (scene_key(path, fallback),)
                )
                connection.commit()
            finally:
                connection.close()

    def count(self):
        with self._lock:
            connection = self._connect()
            try:
                return int(connection.execute("SELECT COUNT(*) FROM scene_state").fetchone()[0])
            finally:
                connection.close()
