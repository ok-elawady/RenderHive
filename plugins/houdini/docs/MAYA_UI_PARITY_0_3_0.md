# RenderHive Houdini v0.3.0

## UI parity
The Houdini submitter now follows the Maya RenderHive visual structure: branded header, left navigation, stacked pages, section cards, footer status and Submit Job placement.

## Automatic scene synchronization
The plugin reads the HIP filename, scene name, $HIP, $JOB, project path, project name, Houdini version, frame range, current frame and FPS without cooking render nodes. These values refresh after HIP load, save and clear events.

## Render safety
Full ROP/LOP discovery remains manual. This avoids evaluating third-party renderer nodes during window startup. The artist may use Refresh Nodes or Use Selected Node.
