# RenderHive Maya Production Core — v1.9.6

This update intentionally does not redesign the UI and does not add Submission Review or Receipt windows.

## API hardening

- Endpoint map aligned with RenderHive API `0.1.0`.
- Added Job PATCH and read-only Layer/Frame client methods.
- Removed Worker-only endpoint configuration from the Maya submitter.
- Pool and Worker access exposed as read-only to Maya.
- GET requests retry transient network and `429/502/503/504` failures.
- Mutating requests are never automatically retried.
- Every request receives a traceable `X-RenderHive-Request-ID`.
- Explicit errors for authentication, not found and rate limiting.
- Pagination has loop detection and a maximum page limit.
- Created Job fallback is paginated and time-filtered.

## Security and local data

- API token is no longer written in plain text to `api_config.json`.
- On Windows the token is protected by the current user account through DPAPI.
- Existing plain-text tokens are migrated automatically.
- Submission logs moved to `%LOCALAPPDATA%/RenderHive/logs/api_submissions`.
- Logs include failed requests and use atomic writes.
- Log retention is configurable and defaults to 200 files.

## Payload reliability

- `JobCreate` request validated against the supplied OpenAPI schema.
- Windows paths remain Windows paths during tests and tools.
- Arnold pre-render Python is Base64 encoded before entering the command line.
- RAM values now map to `min_memory_mb` when supplied.
- Contract extension fields are supported but disabled until the backend accepts them.

## Version consistency

- UI, main Maya module and HTTP User-Agent now share `api/version.py`.
