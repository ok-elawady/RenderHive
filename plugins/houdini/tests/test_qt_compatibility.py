from pathlib import Path


def package_root():
    return Path(__file__).resolve().parents[1] / "payload" / "python_libs" / "renderhive_houdini"


def test_no_direct_pyside_imports():
    violations = []
    for path in package_root().rglob("*.py"):
        if path.name == "qt_compat.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "from PySide6" in text or "from PySide2" in text or "from hutil.Qt" in text:
            violations.append(str(path))
    assert not violations, violations


def test_compatibility_layer_supports_sidefx_and_both_bindings():
    path = package_root() / "ui" / "qt_compat.py"
    text = path.read_text(encoding="utf-8")
    assert "from hutil.Qt" in text
    assert "from PySide6" in text
    assert "from PySide2" in text
    assert "HEADER_STRETCH" in text
    assert "TEXT_SELECTABLE_BY_MOUSE" in text


def test_houdini_feature_compatibility_module_exists():
    text = (package_root() / "core" / "houdini_compat.py").read_text(encoding="utf-8")
    assert 'getattr(hou, "qt", None)' in text
    assert "mainWindow" in text
    assert "mainQtWindow" in text
