# Build Validation — v1.9.6

- Python syntax compilation: passed.
- Unit tests: 8 passed.
- OpenAPI endpoint audit: 15/15 submitter endpoint mappings passed.
- `JobCreate` payload validation: passed against RenderHive API 0.1.0.
- Token persistence test: passed; token absent from `api_config.json`.
- HTTP client tests: Token auth, pagination, HTTP 204 and authentication errors passed.
- UI layout: unchanged from v1.9.5 except the displayed version source.
- Submission Review and Receipt dialogs: not added.

A live Maya + backend integration run is still required because Maya and the backend service are not available in this build environment.
