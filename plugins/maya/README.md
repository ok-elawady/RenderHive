# RenderHive Maya Submitter

Current plugin version: **1.9.12**  
Validated API contract: **RenderHive API 0.1.0**

## Current scope

- Maya scene validation and safe Auto Fix.
- API Job submission.
- Backend Worker and Pool synchronization.
- Read-only pool selection and worker details.
- Scene-specific SQLite restore.
- Token authentication.
- Local activity and API submission logs.

## Backend ownership

The backend/admin owns:

- Pool creation, rename and deletion.
- Worker-to-Pool membership.
- Worker ping and Frame lifecycle endpoints.

The Maya submitter only reads Pools and Workers and submits Jobs.

## API configuration

Open `Tools > API Connection` and set the API URL and Token.

Runtime configuration:

```text
%LOCALAPPDATA%/RenderHive/api_config.json
```

The Token is stored separately. On Windows it is encrypted with DPAPI for the current Windows user.

## Contract status

All Maya-side endpoint paths and HTTP methods match the supplied OpenAPI file. Two backend changes remain:

1. `POST /api/jobs/` should return the created Job ID.
2. `LayerCreate` should accept explicit target Pool IDs for guaranteed pool dispatch.

See:

- `API_CONTRACT_AUDIT_1_9_6.md`
- `BACKEND_HANDOFF_1_9_6.md`
- `PRODUCTION_CORE_1_9_6.md`

## Development audit

```bat
python tools\audit_api_contract.py contracts\renderhive_api_0_1_0.yaml
```

## Installation

Drag `drag_to_maya_install.mel` into Maya, or use the packaged CMD installer when included with the release.
