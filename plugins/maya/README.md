# RenderHive Maya Submitter

Current plugin version: **2.0.0**  
Validated backend contract: **RenderHive API 0.2.0**

## Production scope

- Maya scene, render, dependency, naming, geometry, material and lighting validation.
- Safe Auto Fix for supported validation results.
- Job submission through `POST /api/jobs/`.
- Pool and Worker synchronization from the backend.
- Backend-native `included_pools` / `excluded_pools` targeting.
- Job-on-job dependencies using RenderHive Job UUIDs.
- Job status, update, pause, resume and delete operations.
- Nested Job Layer and Task inspection using the API 0.2.0 task routes.
- Scheduler resource requirements: minimum CPU cores, RAM and GPU count.
- Maya Render Setup / legacy render layer multi-selection with one backend Layer per selected Maya layer.
- Layer-specific `Render.exe -rl` commands.
- The Render Layers selector is authoritative: only checked Maya layers are submitted; `defaultRenderLayer` is never injected into a custom selection.
- Explicit layer submissions use deterministic per-layer output prefixes to prevent image collisions.
- Deleted or renamed layers are reconciled immediately before submission and cannot be sent as stale layer names.
- Per-scene SQLite submitter state with corruption recovery.
- SQLite connections are transaction-scoped and explicitly closed after every operation, including failure paths and backups.
- Managed API configuration and protected token storage.
- Local runtime logging, submission logs and redacted support bundles.
- Validation page callbacks are routed through the installed API bridge so page modules never depend on unresolved globals after UI extraction.

## UI architecture

The production cleanup now separates presentation, targeting and task construction
without changing the artist-facing submission workflow:

- `ui/common_widgets.py` contains reusable presentation widgets.
- `ui/targeting_widgets.py` contains the active Render Layer and Pool selection widgets plus shared background worker threads.
- `ui/pages/` contains the Job, Render, Validation and Tools page builders.
- `ui/controllers/api_controller.py` owns managed API status, connection testing and asynchronous submission lifecycle.
- `ui/controllers/targeting_controller.py` owns backend Pool/Worker synchronization, normalization, eligibility and targeting state.
- `submission/task_builder.py` is the single canonical Maya task builder used by validation and submission.
- `ui/runtime_registry.py` owns the stable shared widget registry.
- `ui/qt_submitter_window.py` remains the Maya/Qt lifecycle controller, scene synchronization layer and UI coordinator.

The previous `build_task()` + `build_task_v2()` wrapper path has been removed.
Legacy callers and the Qt submitter now delegate to the same task builder. The
unsupported Machine Limit compatibility field was removed from the internal task
model, API configuration and payload metadata because RenderHive API 0.2.0 does
not expose or enforce it. Pool targeting continues to use the backend-native
`included_pools` / `excluded_pools` fields.

## API configuration

The submitter supports studio-managed configuration without embedding secrets in
the plugin package.

Configuration priority:

1. Environment overrides (`RENDERHIVE_API_*`).
2. Managed machine configuration: `%PROGRAMDATA%/RenderHive/config/api.json`.
3. User configuration: `%LOCALAPPDATA%/RenderHive/api_config.json`.

Authentication supported by API 0.2.0:

- `Authorization: Token <token>`
- `X-Session-Token: <token>`

User tokens are not written into the JSON configuration. On Windows, protected
credential storage is used for the current Windows user.

## API 0.2.0 notes

The Maya submitter is aligned with the supplied OpenAPI 0.2.0 contract. Two
backend limitations remain and are handled conservatively by the plugin:

- `POST /api/jobs/` is documented with a `JobCreate` response that does not
  contain the created Job ID. The client resolves the created job using the
  unique Maya `task_uid` when necessary.
- API 0.2.0 has no machine-count limit. The Maya UI and internal task model do
  not expose or carry an unenforceable Machine Limit setting.

The current Maya release uses **Shared Storage** delivery only. Packaging modes
are intentionally not exposed until a complete, testable packaging pipeline is
implemented.

## Contract audit

Run from the plugin source directory:

```bat
python tools\audit_api_contract.py contracts\renderhive_api_0_2_0.yaml
```

Production checks:

```bat
python tools\production_audit.py
```

## Deployment

The production Maya plugin is distributed as part of the full RenderHive package.
The parent RenderHive setup should deploy this `maya` folder and register the
module path. `drag_to_maya_install.mel` remains only as a developer/fallback
installer and is not part of the production deployment contract.

## v1.9.23 finalization

- Maya submissions are Arnold-only and the payload rejects unsupported renderers.
- Arnold/mtoa validation is blocking and can safely switch the scene renderer to Arnold.
- Job Dependencies use a backend Job browser instead of manual UUID entry.
- Dependency UUIDs remain persisted per scene and are sent through API 0.2.0 `dependencies[].parent_job`.


## v1.9.25 UI surface polish

- Job Dependencies inline content now inherits the surrounding card surface instead of drawing a separate black container behind the summary text.
- Render Layer selector containers are explicitly transparent so Maya/Qt palette inheritance cannot introduce dark rectangular patches.
- Render Layer and Job Dependency trees use the normal RenderHive surface palette rather than the terminal/log background, while preserving hover, selection and status readability.

## v1.9.25 checkbox polish

- Replaced Maya/platform-native tree checkbox glyphs with a consistent RenderHive checkbox indicator.
- Render Layers, Job Dependencies and other checkable tree rows now use the same clean white check mark on the purple active surface.
- Added the checkbox icon to installer and production required-file validation so a partial package cannot silently fall back to the platform glyph.


## v1.9.26 production validation and cleanup

- Added a single side-effect-free submission guard in `submission/task_validation.py`; both the classic Maya API and Qt submitter now use the same final validation path.
- Added submission-level validation for scheduling, pool targeting, hardware requirements and cross-DCC Job Dependency UUIDs.
- Worker eligibility preview now respects the selected minimum CPU, RAM and GPU requirements instead of counting every online worker as eligible.
- Render Layer validation now checks the exact layers selected in RenderHive, including missing and duplicate selections.
- Output validation now warns when the render destination is outside the Maya project while preserving shared-storage workflows.
- Removed duplicated scene/render checks and old pre-0.2 frame-route bridge aliases.
- Removed the unused legacy Worker selection/pool-management dialogs and obsolete validation wrapper path.
- Installer and production audit now require the canonical task-validation and submission-validation modules.


## v2.0.0 production release

- Finalized the Maya submitter on RenderHive API 0.2.0.
- Production renderer scope is Arnold / mtoa only.
- Multi Render Layer selection is authoritative and maps one Maya layer to one backend Layer.
- Pool targeting, worker eligibility, CPU/RAM/GPU requirements, chunking, retry and timeout are validated before submission.
- Cross-DCC Job Dependencies are supported through backend Job UUIDs.
- Submission, targeting and task-building logic are split into dedicated controllers/services while preserving the artist workflow.
- SQLite scene state uses short-lived transaction-scoped connections with recovery support.
- UI surface and checkbox fixes are included for Render Layers and Job Dependencies.
- Standalone plugin installation is no longer a production release requirement; deployment is owned by the full RenderHive installer.
