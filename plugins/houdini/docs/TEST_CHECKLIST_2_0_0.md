# Houdini v2.0.0 Runtime Acceptance Checklist

- [ ] Open RenderHive from menu, shelf and Python Panel.
- [ ] Reopen the same HIP and confirm saved Job/Render/Pool/Dependency state restores.
- [ ] Submit one ROP source and verify one backend layer.
- [ ] Submit two checked render sources and verify exactly two backend layers.
- [ ] Render a Hython ROP task through the Worker.
- [ ] Render a Solaris/USD Render ROP task and verify Husk output.
- [ ] Verify Current Frame / Progress / ETA update in the Worker.
- [ ] Test All Pools.
- [ ] Test Selected Pools Only.
- [ ] Test All Except Selected.
- [ ] Test CPU/RAM/GPU minimum filtering.
- [ ] Test Karma XPU with a GPU worker and rejection when no eligible GPU worker exists.
- [ ] Test Chunk Size and Tasks per Worker.
- [ ] Test Retry and Task Timeout.
- [ ] Select a Maya or Houdini Job dependency and verify this Job waits for it.
- [ ] Verify validation blocks unsaved/invalid scenes, missing output and incompatible farm resources.
- [ ] Test Cancel/Fail/Complete task states through the RenderHive Worker/backend.
- [ ] Confirm final output paths and no output collision between selected sources.
