# RenderHive Houdini v2.0.5

RenderHive Houdini is the production Houdini submitter for the RenderHive render farm. It uses the same RenderHive API 0.2.0 contract, scheduling concepts, validation model, job dependencies and visual language as the RenderHive Maya v2.0.0 submitter, while keeping Houdini-native ROP, Solaris and USD/Karma behavior.


## v2.0.5 Tools page parity

- Rebuilt **Tools** to match the compact Maya production layout.
- Removed the large Compatibility and Maintenance cards from the artist-facing page.
- Backend connection is now one compact status row with **Retry Connection** and managed configuration status.
- Long backend exceptions are kept out of the main surface and remain available through the status tooltip/activity log.
- Runtime Logs, Support Bundle, Production Check, Reset Scene Settings and **Uninstall RenderHive…** now live under a compact `•••` maintenance menu.
- Activity Log remains visible, matching the Maya production workflow.
- Shelf/package integration remains unchanged from the v2.0.4 known-good shelf build.

## v2.0.4 UI polish

- Removed the indeterminate footer progress strip; connection/submission state is shown by the existing status line and Submit button state.
- Validation summary counters now use the Maya severity palette: Error red, Warning amber, Info blue, Passed green and Total purple.
- Validation result status cells use the matching severity color.
- Houdini shelf/package integration is unchanged from the v2.0.3 known-good shelf recovery.

## Artist workflow

1. Open or save the HIP scene.
2. Open `RenderHive > Open RenderHive`.
3. Open **Render** and refresh render sources.
4. Check one or more executable ROP/Solaris render sources.
5. Review focused-source camera, renderer, frame range and optional job output overrides.
6. Open **Job** and set scheduling, pool targeting, resources, retry/timeout and optional job dependencies.
7. Run **Validation** and resolve blocking errors.
8. Submit the job.

Each checked Houdini render source becomes one RenderHive backend layer in the same Job.

## Production feature set

- Houdini 19.5+ from one PySide2/PySide6-compatible codebase.
- RenderHive menu, shelf, Python Panel and persistent floating submitter.
- HIP/project/timeline/version context detection and per-HIP SQLite state restore.
- Executable ROP and Solaris render-source discovery.
- Multi-source submission: selected sources map 1:1 to backend `layers[]`.
- ROP/Solaris camera, renderer/delegate, frame range, final output and intermediate USD inspection.
- Hython worker handoff for HIP-driven rendering, including USD Render ROP/Karma workflows that invoke Husk from Houdini.
- Direct Husk helper for pre-generated USD workflows.
- Per-focused-source job overrides without mutating the saved HIP file.
- Native API 0.2.0 pool targeting: All Pools, Selected Pools Only, All Except Selected.
- Worker compatibility filtering by Houdini version, execution mode, renderer tags and CPU/RAM/GPU requirements.
- Karma XPU automatically requires at least one GPU in both payload validation and eligibility checks.
- Chunk Size, Tasks per Worker, Retry Attempts and Task Timeout.
- Cross-DCC Job Dependencies browser for Maya/Houdini jobs.
- Scene/render/dependency/farm validation and safe Auto Fix flows.
- Runtime logs, redacted support bundles and production diagnostics.
- Worker progress frame markers for RenderHive Worker progress/ETA tracking.
- Clean RenderHive UI surfaces and item-view checkmarks shared with the Maya production visual system.

## Backend contract

The embedded OpenAPI source is:

`contracts/renderhive_api_0_2_0.yaml`

Expected SHA-256:

`b77bdeb330bb15cf73fe37f659b67187989d6134f5757cf678acd6f22723172d`

The submitter uses native JobCreate fields such as `included_pools`, `excluded_pools`, `max_tasks_per_worker`, `layers` and `dependencies`. Each backend layer carries the Houdini scene path, render source, compatibility tags, resource requirements, retry/timeout settings and a Hython command template containing `{frame}`.

The API currently documents `POST /api/jobs/` with a `JobCreate` response. If the response omits a Job ID, the client resolves the newly-created Job deterministically using the unique RenderHive `task_uid` stored in `scene_info`.

## Deployment

This folder is the source/plugin payload used by the full RenderHive installer. Houdini registration should be done through the included `package/renderhive.json.template`, with the installer replacing `__RENDERHIVE_HOUDINI_ROOT__` with the deployed payload path.

For development and validation, this package includes a one-click current-user installer. The final RenderHive-wide installer can later own Maya, Houdini, Worker and backend deployment.

## Verification boundary

The included automated suite validates the Python source, API 0.2.0 contract, exact payload schema, multi-source/layer mapping, pool strategies, job dependencies, hardware eligibility, state storage, UI contract and worker progress markers.

A final studio acceptance test still needs a real Houdini + backend + worker render environment because Houdini, renderer licenses and Windows worker executables are not available in the offline build environment.

## v2.0.4 Houdini shelf recovery

This build restores the Houdini integration shell to the exact structure used by the previously working RenderHive Houdini package: `toolbar/RenderHive.shelf`, `icon="renderhive"`, and package-level `hpath` through `$RENDERHIVE_HOUDINI_ROOT`. The official RenderHive shelf artwork is installed under `config/Icons`, which is part of Houdini's standard UI icon search path. No installer step deletes or edits the user's Houdini shelf files or desktop state.
