# RenderHive Houdini Backend Submission v0.4.0

## Implemented

- Reads the managed API configuration used by the Maya submitter.
- Reads the same DPAPI-protected token from `%LOCALAPPDATA%\RenderHive\api_token.bin`.
- Connects to:
  - `GET /api/jobs/`
  - `GET /api/workers/`
  - `GET /api/pools/`
  - `POST /api/jobs/`
- Displays backend, Worker and Pool status without exposing connection credentials.
- Supports pool strategies:
  - All Pools
  - Selected Pools Only
  - All Except Selected
- Builds a nested JobCreate/LayerCreate request for Houdini.
- Stores Houdini-specific execution metadata inside `scene_info`.
- Uses pool names as compatibility tags until the backend exposes a layer pool-ID field.

## Worker handoff

The generated command is equivalent to:

```text
hython -m renderhive_houdini.worker.render_rop --scene <HIP> --node <ROP> --frame {frame}
```

The Worker still needs a Houdini adapter that selects the matching Houdini installation and provides the RenderHive Houdini Python package in `PYTHONPATH`.
