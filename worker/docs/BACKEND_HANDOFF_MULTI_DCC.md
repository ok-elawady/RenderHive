# Backend handoff: Multi-DCC worker

The worker remains compatible with the current legacy endpoints:

- `POST /workers/ping/`
- `POST /tasks/dispatch/`
- `POST /tasks/{id}/succeed/`
- `POST /tasks/{id}/fail/`

## Heartbeat additions

The existing WorkerNode fields are populated with:

- `tags`: `dcc:maya`, `maya:2023`, `dcc:houdini`, `houdini:20.5.278`, etc.
- `cores`, `memory_mb`, and `gpu_models`.
- `system_info.capabilities.maya.versions`.
- `system_info.capabilities.houdini.versions`.
- `system_info.capabilities.houdini.execution_modes`.

## Dispatch recommendation

Before assigning a task, match:

- task `dcc`;
- requested DCC version;
- required renderer tags;
- worker pool membership;
- worker online status and resources.

The worker rejects incompatible versions locally as a final safety check, but
backend-side filtering prevents avoidable failed frames.
