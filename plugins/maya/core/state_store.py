from __future__ import print_function

import datetime
import json
import os
import sqlite3


SCHEMA_VERSION = 1
MIGRATION_KEY = "qsettings_to_sqlite_v1"


def _utc_now():
    return datetime.datetime.utcnow().replace(
        microsecond=0
    ).isoformat() + "Z"


def default_database_path():
    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        folder = os.path.join(
            local_app_data,
            "RenderHive",
        )
    else:
        folder = os.path.join(
            os.path.expanduser("~"),
            ".renderhive",
        )

    if not os.path.isdir(folder):
        os.makedirs(folder)

    return os.path.join(
        folder,
        "maya_state.db",
    )


class StateStore(object):
    """Small durable SQLite store for Maya submitter state.

    A connection is opened per operation. This avoids keeping a SQLite
    connection tied to Maya's UI thread and remains safe if future callbacks
    originate from another thread.
    """

    def __init__(self, database_path=None):
        self.database_path = os.path.abspath(
            database_path or default_database_path()
        )

        folder = os.path.dirname(self.database_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

        self._initialize_schema()

    def _connect(self):
        connection = sqlite3.connect(
            self.database_path,
            timeout=5.0,
        )
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_schema(self):
        with self._connect() as connection:
            connection.executescript(
                """
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

                CREATE INDEX IF NOT EXISTS idx_scene_state_identity
                ON scene_state(scene_identity);

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

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

    def get_metadata(self, key, default=""):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?",
                (str(key),),
            ).fetchone()

        return row[0] if row else default

    def set_metadata(self, key, value):
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                (str(key), str(value)),
            )

    def save_scene_state(self, scene_key, scene_identity, state):
        if not scene_key:
            raise ValueError("scene_key cannot be empty")
        if not isinstance(state, dict):
            raise TypeError("scene state must be a dictionary")

        now = _utc_now()
        payload = json.dumps(
            state,
            sort_keys=True,
            separators=(",", ":"),
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scene_state(
                    scene_key,
                    scene_identity,
                    state_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scene_key) DO UPDATE SET
                    scene_identity = excluded.scene_identity,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (
                    str(scene_key),
                    str(scene_identity or ""),
                    payload,
                    now,
                    now,
                ),
            )

        return True

    def load_scene_state(self, scene_key):
        if not scene_key:
            return None

        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM scene_state WHERE scene_key = ?",
                (str(scene_key),),
            ).fetchone()

        if not row:
            return None

        state = self._decode_json(row[0], default=None)
        return state if isinstance(state, dict) else None

    def delete_scene_state(self, scene_key):
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM scene_state WHERE scene_key = ?",
                (str(scene_key),),
            )
        return bool(cursor.rowcount)

    def list_scene_states(self):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT scene_key, scene_identity, created_at, updated_at
                FROM scene_state
                ORDER BY updated_at DESC
                """
            ).fetchall()

        return [
            {
                "scene_key": row[0],
                "scene_identity": row[1],
                "created_at": row[2],
                "updated_at": row[3],
            }
            for row in rows
        ]

    def save_app_state(self, key, value):
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO app_state(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (str(key), payload, _utc_now()),
            )

        return True

    def load_app_state(self, key, default=None):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM app_state WHERE key = ?",
                (str(key),),
            ).fetchone()

        if not row:
            return default

        return self._decode_json(row[0], default=default)

    def migrate_from_qsettings(self, settings):
        """One-time, non-destructive migration from the old Registry data.

        The original QSettings values are intentionally kept as rollback data.
        After the migration marker is written, SQLite becomes authoritative.
        """
        if self.get_metadata(MIGRATION_KEY, "") == "done":
            return {
                "already_migrated": True,
                "scene_states": 0,
                "app_settings": 0,
            }

        scene_count = 0
        app_count = 0

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

            self.save_scene_state(
                key,
                state.get("scene_identity") or "",
                state,
            )
            scene_count += 1

        for key, default in (
            ("worker_pools_v13", {}),
            ("selected_pool_v13", "All Workers"),
        ):
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
        self.set_metadata(
            "qsettings_migrated_at",
            _utc_now(),
        )

        return {
            "already_migrated": False,
            "scene_states": scene_count,
            "app_settings": app_count,
        }
