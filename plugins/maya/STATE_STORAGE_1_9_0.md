# SQLite State Storage Integration — UI v1.9.0

## Added

- `core/state_store.py`
- SQLite database at `%LOCALAPPDATA%\RenderHive\maya_state.db`
- `scene_state`, `app_state`, and `metadata` tables
- One-time non-destructive migration from QSettings
- 1.5-second debounced persistence
- Forced saves on important lifecycle events
- Maintenance menu action: `Open Restore Data Folder`

## Kept in QSettings

- Window geometry
- Last selected navigation page

## Moved to SQLite

- Per-Maya-scene submitter restore data
- Local/offline Worker Pool cache
- Last selected local Pool fallback

The API token is stored outside SQLite and outside the source package. On Windows it is protected with DPAPI in `%LOCALAPPDATA%\RenderHive\api_token.bin`; `api_config.json` contains no plain-text token.
