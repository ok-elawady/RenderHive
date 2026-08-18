# RenderHive Houdini v0.2.1

## Milestone

This release replaces the bootstrap Render page with real Houdini scene and render-node inspection.

## Included

- Executable ROP discovery under `/out`.
- Executable Solaris render/export-node discovery under `/stage`.
- `Use Selected Node` from the current Houdini network selection.
- Renderer classification for Karma, Arnold, Redshift, Mantra, RenderMan, V-Ray and generic ROPs.
- Frame range, camera, output path, resolution and execution-mode inspection.
- Basic HIP and render-node validation.
- Backend-ready task preview builder for the next API milestone.
- Houdini 19.5+ and PySide2/PySide6 compatibility retained.

## Deliberately deferred

- Backend job submission.
- Pool and worker synchronization.
- Dependency collection and Auto Fix.
- Worker-side hython/husk execution.
