# RenderHive Backend Multi-DCC v0.2.0

This update connects the existing Django backend to RenderHive Worker 1.1.x and
the Houdini submitter without replacing the Maya workflow.

## Added

- Worker heartbeat accepts `status` and structured DCC `capabilities`.
- Worker status can return from `RENDERING` to `ONLINE` after a task.
- Pool detail responses include assigned workers and live worker counts.
- New endpoint: `GET /api/pools/{pool_id}/workers/`.
- Dispatch matches tasks by:
  - pool routing;
  - minimum CPU, RAM and GPU requirements;
  - DCC (`maya` or `houdini`);
  - compatible DCC version;
  - Houdini execution mode (`hython` or `husk`);
  - renderer when a worker explicitly advertises renderer capabilities.
- Dispatch responses include the full multi-DCC task contract:
  `dcc`, `dcc_version`, `renderer`, `render_node`, `camera`,
  `execution_mode`, `output_path`, `project_path`, `usd_output_path`,
  `scene_info`, nested `layer`, nested `job`, and frame data.
- Houdini pool targeting stored in `scene_info.worker_targeting` is translated
  into the Job `included_pools` / `excluded_pools` relations.
- `start_suspended` from Houdini scene metadata creates a paused job.
- Legacy `max_frames_per_worker` is accepted as an alias of
  `max_tasks_per_worker`.

## Version compatibility

- Maya: the requested release year must exist on the worker.
  Example: Maya 2023.2 is compatible with a worker advertising Maya 2023.
- Houdini: major.minor must match; the production build may differ.
  Example: Houdini 20.5.278 is compatible with worker build 20.5.410.
- A worker still performs its own local adapter validation as a final safety
  check.

## Database

No model fields were added, so this release does not require a new migration.
Capabilities remain in `WorkerNode.system_info.capabilities` and `tags`.

Run the normal migration command anyway during deployment:

```bash
uv run python manage.py migrate
```

## Validation

Run:

```bash
uv run pytest
uv run ruff check
```

The package includes new coverage in:

- `apps/workers/tests/test_capabilities.py`
- `apps/jobs/tests/test_multidcc_dispatch.py`
