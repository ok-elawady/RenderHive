from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs"
sys.path.insert(0, str(ROOT))

from renderhive_houdini.api.models import normalize_worker, worker_supports_houdini
from renderhive_houdini.validation.result import ValidationResult
from renderhive_houdini.validation.auto_fix import can_fix_result, is_batch_safe
from renderhive_houdini.core.logging_utils import redact


def test_worker_capability_filtering_accepts_matching_houdini_series():
    worker = normalize_worker({
        "id": 1,
        "hostname": "worker-1",
        "status": "ONLINE",
        "system_info": {"capabilities": {"houdini": {"versions": ["20.5.410"], "execution_modes": ["hython", "husk"]}}},
    })
    assert worker_supports_houdini(worker, "20.5.278", "husk", "Karma XPU")
    assert not worker_supports_houdini(worker, "21.0.440", "husk", "Karma XPU")


def test_autofix_metadata_distinguishes_safe_and_confirmed_actions():
    safe = ValidationResult("WARNING", "Output", "Missing dir", code="OUTPUT_DIRECTORY_MISSING", fixable=True, batch_safe=True, data={"path": "X:/render"})
    save = ValidationResult("WARNING", "Scene", "Dirty", code="SCENE_DIRTY", fixable=True, requires_confirmation=True)
    assert can_fix_result(safe) and is_batch_safe(safe)
    assert can_fix_result(save) and not is_batch_safe(save)


def test_redaction_removes_tokens():
    value = redact({"auth": {"token": "secret"}, "Authorization": "Token abc"})
    assert value["auth"]["token"] == "***REDACTED***"
    assert value["Authorization"] == "***REDACTED***"


def test_ui_contains_maya_parity_actions():
    text = (ROOT / "renderhive_houdini" / "ui" / "pages" / "validation_page.py").read_text(encoding="utf-8")
    for label in ("Validate Scene", "Fix Selected", "Fix All Safe", "Select Node", "Export Report"):
        assert label in text
