# RenderHive Maya Production Readiness — v1.9.7

This release hardens the plugin core without redesigning the UI and without adding Submission Review or Receipt dialogs.

## Completed in the plugin

- Strict and recoverable API configuration with automatic corrupt-file backup.
- Correct boolean parsing for JSON values such as `"false"`.
- Same-origin protection for paginated API URLs to prevent credential leakage.
- Request IDs and idempotency keys on mutating requests.
- Bounded API response size and configurable GET retry policy.
- Retry-After support for rate-limited GET requests.
- Runtime rotating logs with secret redaction.
- Submission-log redaction and plugin-version metadata.
- SQLite quick-check, corruption backup, recovery, health reporting and backup support.
- Support bundle generation with no raw API token or state database.
- Production health check exposed from the Maintenance menu.
- Transactional in-Maya installation with rollback.
- Expanded automated production tests.
- Release manifest with SHA-256 checksums.

## Backend dependencies still required

1. `POST /api/jobs/` should return the created Job ID and state directly.
2. `LayerCreate` and `LayerDetail` should expose `target_pool_ids` so pool targeting is enforced by the scheduler.

The plugin keeps compatible fallbacks until those backend changes are deployed.

## Runtime verification still required

- Maya 2023 clean-machine install.
- Arnold single-frame and animation render.
- Worker pickup and final output validation.
- Invalid token, offline backend, timeout and deleted-pool scenarios.
