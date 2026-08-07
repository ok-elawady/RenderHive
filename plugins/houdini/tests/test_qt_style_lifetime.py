from pathlib import Path


def package_root():
    return Path(__file__).resolve().parents[1] / "payload" / "python_libs" / "renderhive_houdini"


def test_no_manual_qstyle_repolish_calls():
    violations = []
    for path in package_root().rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if ".style().unpolish(" in text or ".style().polish(" in text:
            violations.append(str(path))
    assert not violations, violations


def test_status_appearance_uses_palette():
    text = (package_root() / "ui" / "widgets.py").read_text(encoding="utf-8")
    assert "apply_status_appearance" in text
    assert "palette.setColor" in text
    assert "QtGui.QColor" in text
