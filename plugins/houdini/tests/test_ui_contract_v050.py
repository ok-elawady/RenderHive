from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs" / "renderhive_houdini"


def test_job_page_has_checkbox_pool_targeting_and_worker_details():
    text = (ROOT / "ui" / "pages" / "job_page.py").read_text(encoding="utf-8")
    assert "ITEM_IS_USER_CHECKABLE" in text
    assert "PoolDetailsDialog" in text
    assert "View Pool Details" in text
    assert "worker_memory_label" in text


def test_render_page_supports_camera_renderer_and_job_output_override():
    text = (ROOT / "ui" / "pages" / "render_page.py").read_text(encoding="utf-8")
    assert "self.camera = QtWidgets.QComboBox()" in text
    assert "self.renderer = QtWidgets.QComboBox()" in text
    assert "Override for This Job" in text
    assert "Intermediate USD" in text


def test_hip_events_are_deferred_and_coalesced():
    text = (ROOT / "integration" / "hip_events.py").read_text(encoding="utf-8")
    assert "QTimer.singleShot" in text
    assert "_PENDING" in text
