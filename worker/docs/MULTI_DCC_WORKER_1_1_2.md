# RenderHive Worker Multi-DCC v1.1.2

## Purpose

The worker now uses one shared worker loop with separate Maya and Houdini
execution adapters. It automatically discovers every installed version instead
of storing one fixed Maya executable.

## Supported execution

- Maya: `Render.exe` from the task's requested Maya year.
- Houdini ROP/LOP: `hython.exe` from the task's requested Houdini major/minor.
- Houdini direct USD: `husk.exe` when the task includes a USD path and explicit
  husk execution data.

## Version selection

- Maya `2023.x` uses an installed Maya 2023 build.
- Houdini `20.5.x` uses the newest installed Houdini 20.5 production build when
  the exact build is unavailable.
- When a task does not request a version, the newest detected version is used.
- A task fails clearly when no compatible installed version exists.

## Backend capabilities

Heartbeat data now includes:

- worker version;
- Maya versions;
- Houdini versions;
- `hython` / `husk` availability;
- CPU, memory, GPU, and live utilization;
- capability tags such as `maya:2023` and `houdini:20.5.278`.

For production scheduling, the backend should filter dispatched tasks using
these capabilities. The worker also performs its own final compatibility check.

## Preserved behavior

- Existing API URL and token in QSettings.
- Existing task dispatch endpoints.
- Existing success/fail reporting.
- Existing system tray UI.
- Existing assets and installer project files.
