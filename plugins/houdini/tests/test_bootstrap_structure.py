"""Offline structural checks for the Houdini bootstrap package."""

from pathlib import Path
import json
import xml.etree.ElementTree as ET


def test_payload_layout():
    root = Path(__file__).resolve().parents[1] / "payload"
    required = [
        root / "MainMenuCommon.xml",
        root / "toolbar" / "RenderHive.shelf",
        root / "python_panels" / "renderhive.pypanel",
        root / "python_libs" / "renderhive_houdini" / "bootstrap.py",
        root / "python_libs" / "renderhive_houdini" / "ui" / "qt_compat.py",
        root / "python_libs" / "renderhive_houdini" / "adapters" / "render_node_registry.py",
    ]
    assert all(path.is_file() for path in required)


def test_no_python_minor_specific_payload():
    root = Path(__file__).resolve().parents[1] / "payload"
    assert not list(root.glob("python3.*libs"))


def test_xml_files_parse():
    root = Path(__file__).resolve().parents[1] / "payload"
    ET.parse(str(root / "MainMenuCommon.xml"))
    ET.parse(str(root / "toolbar" / "RenderHive.shelf"))
    ET.parse(str(root / "python_panels" / "renderhive.pypanel"))


def test_package_template_parses():
    root = Path(__file__).resolve().parents[1]
    template = (root / "package" / "renderhive.json.template").read_text(encoding="utf-8")
    data = json.loads(template.replace("__RENDERHIVE_HOUDINI_ROOT__", "C:/RenderHive/Houdini"))
    assert any(row.get("var") == "PYTHONPATH" for row in data["env"] if isinstance(row, dict))


def test_menu_has_no_version_specific_ordering_anchor():
    root = Path(__file__).resolve().parents[1] / "payload"
    menu_text = (root / "MainMenuCommon.xml").read_text(encoding="utf-8")
    assert "help_menu" not in menu_text
    assert "insertBefore" not in menu_text
    assert "insertAfter" not in menu_text
