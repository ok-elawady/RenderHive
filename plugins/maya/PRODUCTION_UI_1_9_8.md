# RenderHive Maya Production UI — v1.9.8

## UI polish

- Removed the visible black subtitle strips by making labels transparent.
- Moved page and card explanations into hover tooltips with compact info buttons.
- Reworked wording across Job, Render, Validation and Tools for production use.
- Renamed Checks to Validation and changed the header subtitle to Maya Render Submission.
- Replaced Custom with Manual Configuration in render presets.
- Standardized field names, placeholders, button labels, spacing, radii and typography.
- Improved backend, worker, pool and synchronization status wording.
- Reduced visual noise without changing API behavior, validation logic, SQLite restore or submission payloads.

## Scope

This release is a presentation and terminology pass over v1.9.7. Backend integration and production-core behavior remain unchanged.


## v1.9.9 managed connection

Artist-facing backend fields were removed. Connection settings are now managed externally.
