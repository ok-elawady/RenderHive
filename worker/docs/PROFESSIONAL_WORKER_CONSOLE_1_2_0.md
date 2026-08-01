# RenderHive Worker Professional Console 1.2.0

## Goal

Replace the minimal log-only worker window with a production worker console inspired by the operational visibility of established render managers, while preserving RenderHive's own visual identity and multi-DCC architecture.

## Interface

The main window now contains four pages:

1. **Overview**
   - Worker, scheduler, current job, and task history cards.
   - Live CPU, memory, disk, and GPU meters.
   - Pause/resume dispatch and pause-after-task controls.
   - Detected Maya and Houdini installations.

2. **Current Job**
   - Job name, user, department, project, priority, submission time, routing, and notes.
   - Task ID, layer, frame range, DCC/version, renderer, execution mode, render node, camera, exit code, and output image.
   - Scene, project, output, and task-log paths.
   - Busy progress while rendering and frame progress when a supported DCC log line is detected.
   - Current-task cancellation.

3. **Worker Info**
   - Worker/scheduler/backend state, uptime, after-task behavior, region, description, comment, pools, tags, and task totals.
   - OS, user, CPU, cores, RAM, IP, MAC, disk, GPU, version, and last ping.
   - Full multi-DCC capability table.

4. **Logs**
   - Timestamped worker events.
   - Search, copy, clear, and open-log-folder actions.

## Operational behavior

- **Pause Dispatch** leaves the worker online and continues heartbeat updates but does not claim new tasks.
- **Pause After Current Task** completes the running task and then pauses dispatch.
- **Cancel Current Task** terminates the DCC process tree and reports a non-zero task result.
- Pool assignments are read from the backend worker record. The heartbeat does not overwrite administrator-managed pools.
- Worker profile values are published inside `system_info.worker_profile` and custom tags are appended to the capability tags.
- Task job metadata is enriched with a best-effort `GET /jobs/{id}/` request using the existing farm token.

## Compatibility

- Existing Maya and Houdini adapters remain unchanged.
- Every detected Maya version continues to use its matching `Render.exe`.
- Every detected Houdini version continues to use its matching `hython` or `husk` executable.
- The backend endpoints introduced by Backend Multi-DCC 0.2.0 are used without requiring a new migration.
