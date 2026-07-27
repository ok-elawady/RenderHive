# RenderHive Maya Build Validation — v1.9.7

## Automated validation

- Python syntax compilation: PASS
- Unit and contract tests: 17/17 PASS
- OpenAPI endpoint mapping: 15/15 PASS
- JobCreate payload schema: PASS
- Token redaction support-bundle test: PASS
- Corrupt API configuration recovery test: PASS
- SQLite corruption recovery test: PASS
- Cross-origin pagination protection test: PASS
- Transactional installer smoke test: PASS

## Runtime checks still required in Maya

- Open the plugin in Maya 2023.
- Test API connection with a valid and invalid token.
- Submit single-frame and animation Arnold jobs.
- Confirm worker pickup and final output.
- Test backend offline, timeout, deleted pool, and no eligible worker scenarios.
