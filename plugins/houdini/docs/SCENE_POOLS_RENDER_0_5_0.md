# RenderHive Houdini v0.5.0

## Scene lifecycle

- Project, Job Name, HIP path, `$HIP`, `$JOB`, timeline and validation context
  refresh when another HIP file is loaded or saved under a new path.
- User-edited Job/Project values are preserved while working in the same HIP.
- HIP callbacks are deferred and coalesced to avoid updating widgets while Houdini
  is still loading the scene.
- Render-node selections from the previous HIP are cleared when the scene changes.

## Pool targeting

- Pool selection uses explicit checkboxes and pool IDs.
- Selection is preserved after backend refresh.
- Selected-only and all-except-selected strategies are supported.
- Double-click a pool or use **View Pool Details** to inspect its workers.
- Pool details include status, IP, CPU cores, RAM, GPU and last heartbeat.

## Render configuration

- Render Camera is selectable from `/obj` cameras or Solaris Camera prims.
- Renderer choices are read from compatible renderer/delegate menus when available.
- Execution mode is automatic:
  - ROP: Hython
  - USD/Solaris: Husk through the selected USD render source
- Solaris final image output is read from the USD Render Product. The intermediate
  USD path is shown separately.
- Output can use the render node settings or be overridden for the submitted job.
- Job-level camera, renderer, output and resolution overrides are passed to the
  headless worker command without modifying the saved HIP file.
