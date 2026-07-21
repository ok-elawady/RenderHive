# Production Package Manifest

```text
RenderHive_Maya/
├── api/
│   ├── __init__.py
│   ├── client.py
│   ├── config.py
│   ├── errors.py
│   ├── maya_bridge.py
│   └── payload.py
├── config/
│   ├── api_config.template.json
│   └── validation_rules.json
├── core/
│   ├── __init__.py
│   └── dependency_collector.py
├── icons/
│   ├── renderhive_header_logo.png
│   └── renderhive_shelf_icon.png
├── ui/
│   ├── icons/
│   │   ├── combo_down.png
│   │   ├── spin_down.png
│   │   └── spin_up.png
│   ├── __init__.py
│   ├── qt_submitter_window.py
│   └── qt_theme.py
├── validation/
│   ├── __init__.py
│   ├── autofix.py
│   ├── dependency_checks.py
│   ├── geometry_checks.py
│   ├── lighting_checks.py
│   ├── material_checks.py
│   ├── naming_checks.py
│   ├── render_checks.py
│   ├── scene_checks.py
│   └── validator.py
├── .gitignore
├── CLEANUP_REPORT.md
├── PACKAGE_MANIFEST.md
├── README.md
├── drag_to_maya_install.mel
├── renderhive_installer.py
└── renderhive_maya_submitter.py
```


## UI 1.9.2

Includes mutually exclusive worker assignment strategies and scene-specific SQLite restore.
