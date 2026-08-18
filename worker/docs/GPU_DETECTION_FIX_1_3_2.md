# RenderHive Worker GPU Detection Fix 1.3.2

## Issue

The worker only used `shutil.which("nvidia-smi")`. NVIDIA commonly installs
`nvidia-smi.exe` in Windows System32 or the NVIDIA NVSMI directory without
adding it to the process PATH. GPU collection also ran only inside the active
worker thread, so the compact UI could show `Not detected` while the worker was
stopped.

## Resolution

- Search PATH, Windows System32, NVIDIA NVSMI, and optional `NVSMI_DIR`.
- Read NVIDIA utilization and VRAM through `nvidia-smi` when available.
- Fall back to `Win32_VideoController` for NVIDIA, AMD, and Intel model discovery.
- Cache the generic Windows query to avoid launching PowerShell every heartbeat.
- Run local GPU discovery in the UI even before the worker is started.
- Include GPU models in the backend heartbeat.
- Show `N/A` instead of a misleading `0%` when a model is detected but live
  telemetry is unavailable.
