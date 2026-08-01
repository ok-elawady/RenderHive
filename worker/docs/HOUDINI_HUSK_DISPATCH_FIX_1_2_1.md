# RenderHive Worker 1.2.1 - Houdini USD/Husk Dispatch Fix

## Root cause

The Houdini submitter describes a USD Render ROP as `execution_mode=husk`, but
its layer preview command is a hython command. Worker 1.2.0 selected the direct
husk branch, reused that hython preview command, and displayed the detected
husk path instead of the actual first command token. On Windows the unresolved
`hython` token was not on PATH, so process creation failed with WinError 2.

## Correct execution model

- Saved HIP plus selected render node: launch the matching `hython.exe` and
  execute the selected ROP/LOP node.
- USD Render ROP: the node generates its intermediate USD and invokes husk
  internally using the scene settings.
- Direct `husk.exe`: used only for a standalone USD file that already exists.

## Additional safeguards

- Arbitrary hython preview commands are never reused as direct husk commands.
- `{HUSK_EXEC}` placeholders are tokenized safely even when the installation
  path contains spaces.
- Executable and working-directory preflight errors now report the actual
  command that failed.
- Worker logs include the resolved command and working directory.
- Camera, renderer, output and resolution overrides are applied only when the
  submitter explicitly enabled the corresponding override.
