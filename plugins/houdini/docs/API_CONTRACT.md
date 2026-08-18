# RenderHive API 0.2.0 Contract

The Houdini v2.0.0 submitter is aligned with the embedded `contracts/renderhive_api_0_2_0.yaml` contract.

Core submitter routes include Jobs, Job Layers/Tasks, Workers, Pools and Pool Workers. Worker-owned routes such as dispatch, start, checkpoint, succeed, fail and ping are audited as part of the same contract even though the DCC submitter does not invoke worker lifecycle operations directly.

## Native scheduling fields

- `included_pools` / `excluded_pools`
- `max_tasks_per_worker`
- `layers[].chunk_size`
- `layers[].min_cores`
- `layers[].min_memory_mb`
- `layers[].min_gpus`
- `layers[].max_retries`
- `layers[].timeout_seconds`
- `dependencies[].parent_job`

Removed legacy/fake artist controls such as Start Suspended, Machine Limit, Allowed Workers and Denied Workers are not part of the v2.0 Houdini submission payload.

## Authentication

The client supports RenderHive API 0.2.0 `Authorization: Token ...` and `X-Session-Token` authentication from managed/shared RenderHive configuration. Credentials are not exposed in the artist UI and are redacted from support bundles.
