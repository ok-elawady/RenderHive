# RenderHive Managed Backend Configuration — v1.9.9

## Artist experience

The Maya plugin no longer displays the backend URL, API token, enable toggle,
or configuration save controls. Artists see only connection status and a
Retry Connection action.

## Configuration priority

1. Environment variables
2. `%PROGRAMDATA%\RenderHive\config\api.json`
3. `%LOCALAPPDATA%\RenderHive\api_config.json`

Supported environment variables:

- `RENDERHIVE_API_CONFIG`
- `RENDERHIVE_API_URL`
- `RENDERHIVE_API_TOKEN`
- `RENDERHIVE_API_ENABLED`
- `RENDERHIVE_API_VERIFY_SSL`
- `RENDERHIVE_ADMIN_MODE`

## Security

The shared machine JSON file does not own or store the API token. Credentials
remain protected per Windows user through DPAPI, or are injected through the
`RENDERHIVE_API_TOKEN` environment variable.

## Updates

The installer creates the machine configuration only when it does not already
exist. Updates never overwrite an existing studio configuration.
