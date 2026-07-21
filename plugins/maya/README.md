# RenderHive Maya Submitter

Clean production package for the RenderHive Maya submitter.

## Main folders

- `api/` — REST client, Token authentication, request payloads and Maya bridge.
- `config/` — API template and validation rules.
- `core/` — dependency collection used by validation.
- `ui/` — active PySide2 interface and theme.
- `validation/` — scene checks and Auto Fix.
- `icons/` — header and shelf icons.

## Installation

Drag `drag_to_maya_install.mel` into Maya.

The package is copied to:

`Documents/maya/<version>/scripts/RenderHive`

The real API token is stored outside the source package at:

`%LOCALAPPDATA%/RenderHive/api_config.json`

Existing settings from the old `backend_config.json` are migrated automatically.

## API setup

Open:

`Tools > API Connection`

Then set the URL, token, enable the API, save, and test the connection.

## Current limitation

The supplied API exposes Jobs, Layers and Frames but no worker-discovery or
pool-management endpoints. Pool definitions therefore remain local and worker
sync returns no online workers until those endpoints are added.


## API Pools & Workers — UI 1.8.0

See `API_INTEGRATION_1_8_0.md`.


## Worker Targeting — UI 1.9.2

Backend pools are read-only in Maya. Use **Job > Browse Pools** to review
pool details and workers, then apply the selected pool to the current job.
Pool creation and membership management remain backend responsibilities.


## Worker Assignment — UI 1.9.2

The Worker Targeting card now provides two explicit strategies:

- **Use All Workers in Pool**: every available pool member is eligible, with optional exclusions.
- **Use Selected Workers Only**: only explicitly selected pool members are eligible.

The active strategy clears the inactive list, so a worker can never be both selected and excluded. Worker selections remain scene-specific through SQLite restore.
