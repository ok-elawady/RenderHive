# RenderHive Maya Worker Targeting v1.9.3

## Production UI update

- API, worker, pool, and sync-time status chips.
- Searchable worker selector with status, RAM, and GPU columns.
- Offline workers remain visible but cannot be selected.
- Segmented assignment control:
  - Use All Workers in Pool
  - Use Selected Workers Only
- Allowed and excluded worker choices remain mutually exclusive.
- Live eligibility summary based on:
  - selected pool
  - worker status
  - assignment strategy
  - selected/excluded workers
  - minimum RAM and VRAM
- Resource requirements moved into a collapsible advanced section.
- Cached and stale worker data states are clearly shown.
- Worker pool browser now includes hardware details.
- Submission warns when targeting data is stale or no eligible worker exists.
- Scene restore continues to use SQLite and stores worker IDs, not display names.

## Notes

Worker and pool membership remain backend-owned. The Maya plugin only reads,
selects, restores, validates, and submits targeting choices.
