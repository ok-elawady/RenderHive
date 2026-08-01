# Backend Contract Scope

The Houdini submitter will reuse the same RenderHive API for:

- authentication
- workers
- pools
- jobs
- layers
- frames
- pause, resume and cancel operations

Houdini-specific task metadata will include the HIP path, Houdini version,
render node path, renderer, execution mode, frame range, output path and
required worker capabilities.
