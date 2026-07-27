# RenderHive Maya API Contract Audit — v1.9.6

Contract checked against `RenderHive API 0.1.0`.

## Result

- All 15 Maya submitter endpoint mappings exist in the supplied OpenAPI file.
- HTTP methods match the OpenAPI contract.
- `Token <value>` authentication matches `tokenAuth`.
- `X-Session-Token` remains supported by the client.
- The generated `JobCreate` request validates against the OpenAPI schema.
- Worker lifecycle endpoints are intentionally not used by the Maya submitter.

## Maya submitter endpoints

| Capability | Method | Endpoint | Status |
|---|---:|---|---|
| Connection test | GET | `/api/jobs/?page=1` | Valid |
| List jobs | GET | `/api/jobs/` | Valid |
| Submit job | POST | `/api/jobs/` | Valid |
| Job details | GET | `/api/jobs/{id}/` | Valid |
| Update job | PATCH | `/api/jobs/{id}/` | Valid |
| Pause job | POST | `/api/jobs/{id}/pause/` | Valid |
| Resume job | POST | `/api/jobs/{id}/resume/` | Valid |
| Delete job | DELETE | `/api/jobs/{id}/` | Valid |
| Job layers | GET | `/api/jobs/{job_pk}/layers/` | Valid |
| Layer details | GET | `/api/jobs/{job_pk}/layers/{id}/` | Valid |
| Layer frames | GET | `/api/jobs/{job_pk}/layers/{layer_pk}/frames/` | Valid |
| Frame details | GET | `/api/jobs/{job_pk}/layers/{layer_pk}/frames/{id}/` | Valid |
| Workers | GET | `/api/workers/` | Valid |
| Worker details | GET | `/api/workers/{id}/` | Valid |
| Pools | GET | `/api/pools/` | Valid |
| Pool details | GET | `/api/pools/{id}/` | Valid |

## Endpoints intentionally excluded from Maya

The following belong to the Worker application, not the DCC submitter:

- `/api/workers/ping/`
- `/api/frames/dispatch/`
- frame start, succeed, fail, skip and checkpoint actions

Pool creation, deletion and membership management remain backend/admin responsibilities. Maya only reads pools and workers.

## Two required backend adjustments

### 1. Return the created Job reference

The OpenAPI `201` response for `POST /api/jobs/` currently uses `JobCreate`, which contains no `id`, `state` or `created_at`.

Recommended response: `JobDetail`, or a compact object containing at least:

```json
{
  "id": "job-uuid",
  "visible_name": "Lighting Shot 010",
  "state": "PENDING",
  "created_at": "2026-07-24T00:00:00Z"
}
```

Until this changes, the plugin resolves the created Job from the paginated Jobs endpoint. The fallback is time-filtered, but a direct ID response is required for reliable production submission.

### 2. Add explicit pool targeting to LayerCreate

The current `LayerCreate` schema contains compatibility `tags`, but no pool IDs. Workers expose `pools` separately from `tags`, so pool membership cannot be guaranteed from the OpenAPI contract.

Recommended field:

```json
{
  "target_pool_ids": ["pool-uuid-1", "pool-uuid-2"]
}
```

Rules:

- Empty list means unrestricted/all pools.
- The scheduler dispatches only to Workers whose pool membership intersects `target_pool_ids`.
- Persist and return the field in `LayerDetail`.

The plugin is already prepared for this field through:

```json
"contract": {
  "layer_pool_ids_field": "target_pool_ids"
}
```

Do not enable it until the backend serializer accepts the field.

## Optional backend adjustments

These controls currently exist in Maya but are metadata or use a fallback:

- `start_suspended`: currently Job is submitted, then paused. Atomic support removes the dispatch race.
- `machine_limit`: not represented in `JobCreate`.
- `dependencies`: not represented in `JobCreate`.

The plugin contains forward-compatible field mappings for all three.
