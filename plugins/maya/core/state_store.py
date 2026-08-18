from __future__ import print_function

import datetime
import json
import os
import shutil
import sqlite3
from contextlib import contextmanager

from core.runtime_log import get_logger


LOGGER = get_logger("state")
SCHEMA_VERSION = 2
MIGRATION_KEY = "qsettings_to_sqlite_v1"


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_database_path():
    local_app_data = os.environ.get("LOCALAPPDATA")
    folder = os.path.join(local_app_data, "RenderHive") if local_app_data else os.path.join(os.path.expanduser("~"), ".renderhive")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return os.path.join(folder, "maya_state.db")


class StateStore(object):
    """Durable SQLite state with integrity checking and automatic recovery."""

    def __init__(self, database_path=None):
        self.database_path = os.path.abspath(database_path or default_database_path())
        self.recovery_report = {"recovered": False, "backup_path": "", "error": ""}
        folder = os.path.dirname(self.database_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        self._initialize_with_recovery()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except Exception:
            connection.close()
            raise

    @contextmanager
    def _connection(self):
        """Yield one transactional SQLite connection and always close it."""
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize_with_recovery(self):
        try:
            self._initialize_schema()
            result = self.quick_check()
            if result != "ok":
                raise sqlite3.DatabaseError("SQLite quick_check returned: {}".format(result))
        except sqlite3.DatabaseError as error:
            backup = self._backup_corrupt_database(error)
            self.recovery_report = {"recovered": True, "backup_path": backup, "error": str(error)}
            self._initialize_schema()
            LOGGER.error("Recovered corrupt state database; backup=%s error=%s", backup, error)

    def _initialize_schema(self):
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scene_state (
                    scene_key TEXT PRIMARY KEY,
                    scene_identity TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scene_state_identity ON scene_state(scene_identity);
                CREATE INDEX IF NOT EXISTS idx_scene_state_updated ON scene_state(updated_at);
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            connection.execute("PRAGMA user_version = {}".format(SCHEMA_VERSION))
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def _backup_corrupt_database(self, error):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = "{}.corrupt_{}".format(self.database_path, stamp)
        for suffix in ("", "-wal", "-shm"):
            source = self.database_path + suffix
            if os.path.isfile(source):
                target = backup + suffix
                try:
                    shutil.move(source, target)
                except Exception:
                    try:
                        shutil.copy2(source, target)
                        os.remove(source)
                    except Exception:
                        pass
        return backup

    @staticmethod
    def _decode_json(raw, default=None):
        if raw is None or raw == "":
            return default
        if isinstance(raw, (dict, list, bool, int, float)):
            return raw
        try:
            return json.loads(str(raw))
        except Exception:
            return default

    def quick_check(self):
        with self._connection() as connection:
            row = connection.execute("PRAGMA quick_check").fetchone()
        return str(row[0] if row else "unknown")

    def health_report(self):
        report = {
            "path": self.database_path,
            "exists": os.path.isfile(self.database_path),
            "size_bytes": os.path.getsize(self.database_path) if os.path.isfile(self.database_path) else 0,
            "schema_version": self.get_metadata("schema_version", ""),
            "quick_check": "unknown",
            "scene_states": 0,
            "app_states": 0,
            "recovery": dict(self.recovery_report),
        }
        try:
            report["quick_check"] = self.quick_check()
            with self._connection() as connection:
                report["scene_states"] = int(connection.execute("SELECT COUNT(*) FROM scene_state").fetchone()[0])
                report["app_states"] = int(connection.execute("SELECT COUNT(*) FROM app_state").fetchone()[0])
        except Exception as error:
            report["error"] = str(error)
        return report

    def backup(self, destination=None):
        if destination is None:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = "{}.backup_{}".format(self.database_path, stamp)
        destination = os.path.abspath(destination)
        destination_folder = os.path.dirname(destination)
        if destination_folder and not os.path.isdir(destination_folder):
            os.makedirs(destination_folder)
        with self._connection() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
        return destination

    def prune_scene_states(self, max_entries=500):
        max_entries = max(10, int(max_entries))
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT scene_key FROM scene_state ORDER BY updated_at DESC LIMIT -1 OFFSET ?",
                (max_entries,),
            ).fetchall()
            for row in rows:
                connection.execute("DELETE FROM scene_state WHERE scene_key = ?", (row[0],))
        return len(rows)

    def get_metadata(self, key, default=""):
        with self._connection() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = ?", (str(key),)).fetchone()
        return row[0] if row else default

    def set_metadata(self, key, value):
        with self._connection() as connection:
            connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", (str(key), str(value)))

    def save_scene_state(self, scene_key, scene_identity, state):
        if not scene_key:
            raise ValueError("scene_key cannot be empty")
        if not isinstance(state, dict):
            raise TypeError("scene state must be a dictionary")
        now = _utc_now()
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"))
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO scene_state(scene_key, scene_identity, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scene_key) DO UPDATE SET
                    scene_identity = excluded.scene_identity,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
            """, (str(scene_key), str(scene_identity or ""), payload, now, now))
        return True

    def load_scene_state(self, scene_key):
        if not scene_key:
            return None
        with self._connection() as connection:
            row = connection.execute("SELECT state_json FROM scene_state WHERE scene_key = ?", (str(scene_key),)).fetchone()
        if not row:
            return None
        state = self._decode_json(row[0], default=None)
        return state if isinstance(state, dict) else None

    def delete_scene_state(self, scene_key):
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM scene_state WHERE scene_key = ?", (str(scene_key),))
            deleted = bool(cursor.rowcount)
        return deleted

    def list_scene_states(self):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT scene_key, scene_identity, created_at, updated_at FROM scene_state ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {"scene_key": row[0], "scene_identity": row[1], "created_at": row[2], "updated_at": row[3]}
            for row in rows
        ]

    def save_app_state(self, key, value):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self._connection() as connection:
            connection.execute("""
                INSERT INTO app_state(key, value_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """, (str(key), payload, _utc_now()))
        return True

    def load_app_state(self, key, default=None):
        with self._connection() as connection:
            row = connection.execute("SELECT value_json FROM app_state WHERE key = ?", (str(key),)).fetchone()
        if not row:
            return default
        return self._decode_json(row[0], default=default)

    def migrate_from_qsettings(self, settings):
        if self.get_metadata(MIGRATION_KEY, "") == "done":
            return {"already_migrated": True, "scene_states": 0, "app_settings": 0}
        scene_count, app_count = 0, 0
        try:
            keys = list(settings.allKeys())
        except Exception:
            keys = []
        for key in keys:
            key = str(key)
            if not key.startswith("scene_submitter_state_"):
                continue
            try:
                raw = settings.value(key, "")
            except Exception:
                continue
            state = self._decode_json(raw, default=None)
            if not isinstance(state, dict):
                continue
            self.save_scene_state(key, state.get("scene_identity") or "", state)
            scene_count += 1
        for key, default in (("worker_pools_v13", {}), ("selected_pool_v13", "All Workers")):
            try:
                raw = settings.value(key, None)
            except Exception:
                raw = None
            if raw is None or raw == "":
                continue
            value = self._decode_json(raw, default=raw)
            if key == "worker_pools_v13" and not isinstance(value, dict):
                value = default
            self.save_app_state(key, value)
            app_count += 1
        self.set_metadata(MIGRATION_KEY, "done")
        self.set_metadata("qsettings_migrated_at", _utc_now())
        return {"already_migrated": False, "scene_states": scene_count, "app_settings": app_count}
