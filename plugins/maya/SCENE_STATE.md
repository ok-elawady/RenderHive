# Per-Scene Submitter State — v1.9.0

RenderHive stores Maya submitter choices outside the `.ma` / `.mb` scene so
changing plugin options never dirties the Maya scene.

## Storage

Per-scene restore data and the offline Worker Pool cache are stored in SQLite:

`%LOCALAPPDATA%\RenderHive\maya_state.db`

`QSettings` / the Windows Registry is now used only for small UI preferences
such as window geometry and the last open page.

## Save behavior

- A 500 ms monitor detects scene switches and changed UI values.
- Changes are debounced for 1.5 seconds.
- One SQLite write occurs after values stop changing.
- A forced save occurs when the plugin closes, before switching scenes, after
  worker/pool synchronization, and before job submission.

## Migration

On the first v1.9.0 launch, old per-scene data and local pool cache values are
copied from QSettings into SQLite. The old Registry values are not deleted, so
they remain available for rollback.

The SQLite database uses WAL mode, transactional upserts, a 5-second busy
timeout, and one short-lived connection per operation.
