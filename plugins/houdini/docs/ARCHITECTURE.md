# RenderHive Houdini v2.0.0 Architecture

The production plugin is split by responsibility instead of keeping submission logic in the window.

- `api/`: managed configuration, authentication, API endpoints, request client and API 0.2.0 contract rules.
- `adapters/`: Houdini scene/render-source discovery and ROP/Solaris details.
- `core/`: scene context, task/payload building, SQLite state, dependencies, logs and production diagnostics.
- `ui/`: Qt compatibility, theme, pages, job dependency browser and composition window.
- `validation/`: scene, render-source, file dependency and farm eligibility checks plus Auto Fix.
- `worker/`: Hython ROP runner and direct Husk helper used by RenderHive workers.
- `integration/`: Houdini menu/shelf/panel and HIP event integration.

## Submission flow

`HIP scene -> selected render sources -> validation -> canonical task -> API 0.2 JobCreate -> scheduler -> worker -> hython/render_rop -> ROP/Solaris/Husk -> output`

Each selected render source is converted into exactly one backend layer. Job-level pool targeting and dependencies remain on JobCreate; resource requirements, command, frame range, retry and timeout are written per layer.
