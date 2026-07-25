# RenderHive Maya v1.9.12 Package Manifest

Key production components:

```text
maya/
├── api/
│   ├── client.py
│   ├── config.py
│   ├── contract.py
│   ├── credentials.py
│   ├── maya_bridge.py
│   └── version.py
├── config/
│   ├── api.machine.json
│   ├── api_config.template.json
│   └── validation_rules.json
├── core/
│   ├── diagnostics.py
│   ├── runtime_log.py
│   └── state_store.py
├── tests/
│   ├── test_api_client.py
│   ├── test_api_contract.py
│   ├── test_api_security.py
│   ├── test_config_security.py
│   ├── test_managed_config.py
│   └── test_state_store.py
├── ui/
│   ├── qt_submitter_window.py
│   └── qt_theme.py
├── validation/
├── MANAGED_BACKEND_CONFIG_1_9_9.md
├── BUILD_VALIDATION_1_9_9.md
├── RenderHive.mod
└── renderhive_maya_submitter.py
```

Runtime secrets, SQLite state and logs remain outside the package under
`%LOCALAPPDATA%\RenderHive`. The studio API configuration is read from
`%PROGRAMDATA%\RenderHive\config\api.json` when present.
