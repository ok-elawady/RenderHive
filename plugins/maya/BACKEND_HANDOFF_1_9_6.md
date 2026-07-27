# Backend Handoff — Maya v1.9.6

Only two backend changes are required before the Maya submitter can be considered fully connected for production scheduling.

## Required

### POST `/api/jobs/` response

Return the created Job with a stable `id` and `state`.

Preferred OpenAPI response schema:

```yaml
'201':
  content:
    application/json:
      schema:
        $ref: '#/components/schemas/JobDetail'
```

### Pool targeting

Add an optional array to `LayerCreate` and `LayerDetail`:

```yaml
target_pool_ids:
  type: array
  items:
    type: string
    format: uuid
```

Scheduler behavior:

```text
empty target_pool_ids -> unrestricted
non-empty target_pool_ids -> Worker must belong to at least one target pool
```

After the backend is deployed, set this in `%LOCALAPPDATA%/RenderHive/api_config.json`:

```json
"contract": {
  "version": "0.1.1",
  "job_create_returns_id": true,
  "layer_pool_ids_field": "target_pool_ids",
  "job_start_suspended_field": "",
  "job_machine_limit_field": "",
  "job_dependencies_field": ""
}
```

No Maya UI rewrite is required.

## Optional

The same config can activate future backend fields without changing plugin code:

```json
"contract": {
  "job_start_suspended_field": "start_suspended",
  "job_machine_limit_field": "machine_limit",
  "job_dependencies_field": "dependencies"
}
```

Enable a field only after it exists in the backend serializer and OpenAPI document.
