from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs" / "renderhive_houdini"


def test_footer_has_no_indeterminate_progress_bar():
    text = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    footer = text.split("def _build_footer", 1)[1].split("def _restore_window_state", 1)[0]
    assert "QProgressBar" not in footer
    assert "self.progress" not in text
    assert "self._busy = bool(busy)" in text


def test_validation_uses_maya_style_severity_colors():
    text = (ROOT / "ui" / "pages" / "validation_page.py").read_text(encoding="utf-8")
    for token in ('COLORS["error"]', 'COLORS["warning"]', 'COLORS["info"]', 'COLORS["success"]', 'COLORS["light"]'):
        assert token in text
    assert "border-top: 3px solid %s" in text
    assert "item.setForeground(0" in text
