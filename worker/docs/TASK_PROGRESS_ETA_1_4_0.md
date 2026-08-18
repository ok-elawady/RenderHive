# RenderHive Worker Task Progress and ETA 1.4.0

## UI contract

The Current Job card displays:

- task percentage from 1 to 100
- current phase
- current frame and total frames
- elapsed time
- estimated remaining time
- renderer-level percentage when the renderer publishes one

## Progress sources

1. Explicit `RENDERHIVE_FRAME_START` and `RENDERHIVE_FRAME_DONE` markers.
2. Renderer frame and percentage messages from stdout.
3. Conservative lifecycle phases when precise output is unavailable.

Multi-frame tasks use completed frames for exact progress and ETA. Single-frame
tasks use renderer percentages when available, otherwise a phase-based estimate.
Progress is monotonic and only reaches 100 after the DCC process exits cleanly.

## Houdini

The bundled hython script renders the assigned chunk frame by frame while the
HIP file remains loaded, publishing exact frame-start and frame-complete markers.
USD Render ROP nodes may still invoke husk internally.

## Backend telemetry

The heartbeat `system_info.current_task` object includes task ID, job name,
phase, percentage, current frame, total frames, elapsed seconds, and ETA.
