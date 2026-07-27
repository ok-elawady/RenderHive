# RenderHive Maya v1.9.10 — Startup and Main Menu Fix

## Fixed

- Fixed the startup crash caused by `api_admin_mode_enabled` not being exposed through the Maya API bridge.
- Added defensive UI fallbacks so an older cached module cannot prevent the submitter from opening.
- Exposed `get_api_config_source` through the bridge as required by the managed connection UI.

## Maya main menu

A persistent **RenderHive** menu is installed in Maya's top menu bar with:

- Open RenderHive
- Validate Current Scene
- Uninstall RenderHive

The installer adds a marked, non-destructive startup block to the Maya version's existing `userSetup.py`. Existing user startup code is preserved. The block is updated in place on future installs and removed during uninstall.
