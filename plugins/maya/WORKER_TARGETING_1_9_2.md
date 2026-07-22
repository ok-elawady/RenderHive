# Worker Targeting — UI 1.9.2

## Changes

- Replaced simultaneous Allowed/Denied editing with one explicit assignment strategy.
- Added **Use All Workers in Pool** with optional **Excluded Workers**.
- Added **Use Selected Workers Only** with a required **Selected Workers** list.
- A worker cannot exist in both lists.
- Changing pools automatically removes selections that are no longer members.
- Added a compact pool availability summary.
- Moved RAM and VRAM into a separate Resource Requirements section.
- Preserved the existing backend payload fields: `allowed_workers` and `denied_workers`.
- Added `worker_assignment_mode` to the task and per-scene SQLite restore state.

## Payload behavior

### Use All Workers in Pool

```json
{
  "worker_assignment_mode": "all_in_pool",
  "allowed_workers": [],
  "denied_workers": ["worker-id"]
}
```

### Use Selected Workers Only

```json
{
  "worker_assignment_mode": "selected_only",
  "allowed_workers": ["worker-id"],
  "denied_workers": []
}
```
