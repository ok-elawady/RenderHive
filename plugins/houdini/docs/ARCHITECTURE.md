# RenderHive Houdini Architecture

The Houdini plugin is split into six layers:

1. `api` — backend communication and authentication.
2. `core` — state, logging, scene context, dependencies and task payloads.
3. `adapters` — Houdini, ROP, Solaris, Karma and husk integration.
4. `validation` — scene, render, dependency and farm checks.
5. `ui` — PySide6 presentation only.
6. `integration` — Houdini menu, shelf, Python Panel and HIP callbacks.

Worker execution helpers live in `worker` but remain independent of the UI.
