# RenderHive Cleanup Report — v1.6.0

## Removed

- `worker/` and every Local Worker script/task file.
- Old task examples.
- Timestamped backup folders.
- Generated submission logs from the distributed package.
- All `__pycache__` and `.pyc` files.
- Old Maya `cmds` UI implementation.
- `ui/renderhive_submitter_window.py`.
- Empty `ui/submitter_window.py`.
- Empty `core/paths.py`, `core/settings.py`, and `core/task_builder.py`.
- Unused `renderhive_logo.png`.
- The separate branding patch module and duplicate MEL branding commands.
- Local Worker fallback from `Submit Job`.
- Unused Task Preview dialog and JSON task-saving code from the active Qt UI.
- Diagnostics code that was no longer exposed by the active UI.

## Renamed and reorganized

- `renderhive_backend/` → `api/`.
- `backend_config.template.json` → `api_config.template.json`.
- Local settings file → `%LOCALAPPDATA%/RenderHive/api_config.json`.
- Backend-facing classes/functions/UI labels → API naming.
- Submission logs → `logs/api_submissions/`.
- UI version → `1.6.0`.

## Fixed

- Restored the missing `validation/autofix.py` module referenced by the UI.
- Added migration from the old local `backend_config.json`.
- Made the installer use the real shelf icon instead of generating an XPM file
  with a `.png` extension.
- Removed three duplicate `show_submitter()` implementations and kept one Qt
  entry point.
- Added protection against generic `api`, `ui`, and `validation` package name
  collisions in Maya.
- Kept the API token out of the ZIP and source repository.

## Kept intentionally

- Worker Pools and Allowed/Denied worker targeting in the submitter UI.
  These are job-submission options, not the removed Local Worker program.
- Submission Mode.
- Validation, Auto Fix, dependency checks, API submission, installer, branding
  assets, and Activity Log.
