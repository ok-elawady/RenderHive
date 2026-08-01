# RenderHive Houdini v0.5.0

RenderHive Houdini is the Houdini submitter for the existing RenderHive backend.
It supports Houdini 19.5 and newer builds through one PySide2/PySide6-compatible
codebase.

## Current capabilities

- Package-based installation for every detected Houdini version.
- RenderHive menu, shelf tool, Python Panel and persistent floating window.
- Automatic HIP, project, timeline and scene-name detection.
- Automatic refresh when switching or saving HIP files.
- Safe manual discovery of executable ROP and Solaris render sources.
- Camera selection from `/obj` or Solaris Camera prims.
- Compatible renderer/delegate selection.
- Automatic Hython/Husk execution classification.
- Final image output detection, including USD Render Product output.
- Intermediate USD paths shown separately from rendered image output.
- Job-level output, renderer, camera and resolution overrides.
- Managed backend configuration shared with the Maya plugin.
- Worker and Pool synchronization.
- Checkbox-based pool targeting and worker detail inspection.
- Backend-ready Houdini JobCreate submission.
- Basic scene/render validation.

## Installation

1. Close every Houdini process.
2. Run the top-level `install_from_cmd.bat`.
3. Restart Houdini.
4. Use `RenderHive > Open RenderHive`.

The installer updates the project source at:

`D:\Moemen\iti\CGTD\RenderHiveProject\RenderHive\plugins\houdini`

A shared runtime is installed under:

`%LOCALAPPDATA%\RenderHive\Houdini\0.5.0`

Each supported Houdini preferences directory receives:

`Documents\houdiniX.Y\packages\renderhive.json`

## Worker requirement

The RenderHive Worker still needs the production Houdini adapter that resolves
the requested Houdini version and executes the generated Hython/Husk-compatible
command on an eligible Worker.
