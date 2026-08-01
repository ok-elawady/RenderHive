# RenderHive Houdini v0.2.1 - Startup Crash Fix

- Render-node discovery no longer runs automatically while the window is being constructed.
- Opening the plugin reads only lightweight HIP session information.
- Render nodes are scanned only after the artist clicks **Refresh Nodes**.
- Discovery no longer uses `allSubChildren()`. It walks network children with a hard safety limit.
- Discovery does not evaluate renderer, camera, output or resolution parameters.
- This prevents node cooking and third-party renderer callbacks during UI startup.
- HIP file callbacks refresh scene metadata without rescanning render nodes.
