# Per-Scene Submitter State — v2.0.0

RenderHive stores submitter choices outside the `.ma` / `.mb` scene so changing
farm options never dirties the Maya scene.

## Storage

Per-scene restore data and the offline Worker/Pool cache are stored in SQLite:

`%LOCALAPPDATA%\RenderHive\maya_state.db`

`QSettings` is used only for small UI preferences such as window geometry and
the last open page.

## Saved submitter values

The scene state includes job metadata, pool targeting, frame/chunk settings,
resource requirements, retry/timeout policy, selected Maya render layers,
renderer/camera choices and output settings. Authentication credentials are never stored in scene state.

## Save behavior

- A 500 ms monitor detects scene switches and changed UI values.
- Changes are debounced for 1.5 seconds.
- A forced save occurs when the plugin closes, before switching scenes, after
  Worker/Pool synchronization and before job submission.
- SQLite uses WAL mode, transactional upserts, a 5-second busy timeout and
  short-lived connections. Every connection is explicitly closed in a `finally`
  path, so Maya does not retain database handles after reads, writes, backups or
  failed transactions.

## Recovery

Corrupt local state is moved aside and a fresh database is created. Previous
QSettings scene-state values remain available to the migration logic where
applicable.

## Render layer restore behavior

Saved render-layer names are intersected with the layers that currently exist in Maya. Deleted or renamed layers are silently removed from the restored selection. The plugin never adds `defaultRenderLayer` to a saved custom selection.
