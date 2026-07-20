# RenderHive Maya Plugin — API Pools & Workers Integration 1.8.0

Base version: **1.7.5**

This build preserves the complete 1.7.5 UI, per-scene restore system,
validation/Auto Fix, job submission, API token handling, and local worker
fallback. It adds the latest Workers and Pools API integration without
replacing the plugin with an older codebase.

## Added

- Paginated `GET /api/workers/` synchronization.
- Paginated `GET /api/pools/` synchronization.
- Backend pool creation with `POST /api/pools/`.
- Backend pool rename/description updates with `PATCH /api/pools/{id}/`.
- Backend pool deletion with `DELETE /api/pools/{id}/`.
- Worker membership derived from each WorkerNode's read-only `pools` array.
- Allowed and Denied selectors filtered by the selected backend pool.
- `pool_id`, pool name, pool members, allowed and denied workers preserved in
  the local task and `scene_info.worker_targeting` API metadata.
- Offline startup fallback using the last locally cached pool membership.
- Scene-specific pool restore remains pending until API pools finish syncing,
  preventing the restored pool from silently reverting to All Workers.
- Installer version guard prevents an older package from overwriting a newer
  Maya plugin unless `--force` is explicitly supplied.

## Current backend limitation

The supplied OpenAPI schema exposes Worker pools as read-only on WorkerNode and
has no endpoint for assigning/removing a Worker from a Pool. The Maya plugin can
create, rename, describe, and delete Pool records, but membership must currently
be assigned from Django Admin/backend logic.

Also, JobCreate/LayerCreate does not expose a native `pool_id` scheduling field.
The plugin sends the selected pool in `scene_info.worker_targeting` and retains
the pool name as a layer tag for compatibility. The backend scheduler must read
that metadata/tag, or add an explicit pool field, to enforce pool targeting.
