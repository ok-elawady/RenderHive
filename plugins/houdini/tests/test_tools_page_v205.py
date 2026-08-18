from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "payload" / "python_libs" / "renderhive_houdini"


def _tools_source():
    return (ROOT / "ui" / "pages" / "tools_page.py").read_text(encoding="utf-8")


def test_tools_page_matches_compact_maya_layout():
    text = _tools_source()
    assert 'SectionCard(\n            "Connection"' in text
    assert 'SectionCard(\n            "Activity Log"' in text
    assert 'QtWidgets.QToolButton()' in text
    assert 'setObjectName("MaintenanceButton")' in text
    assert 'setText("•••")' in text
    assert '"Retry Connection"' in text


def test_large_compatibility_and_maintenance_cards_are_removed():
    text = _tools_source()
    assert 'SectionCard("Compatibility"' not in text
    assert 'SectionCard("Maintenance"' not in text
    assert 'ReadOnlyRow(' not in text
    assert '"Plugin Version"' not in text
    assert '"Houdini Version"' not in text
    assert '"Python Version"' not in text
    assert '"Qt Binding"' not in text
    assert '"User Preferences"' not in text


def test_maintenance_actions_live_in_three_dot_menu():
    text = _tools_source()
    for label in (
        "Open Runtime Logs",
        "Create Support Bundle",
        "Run Production Check",
        "Reset Current Scene Settings",
        "Uninstall RenderHive…",
    ):
        assert 'menu.addAction("{}")'.format(label) in text
    assert 'self.uninstallRequested.emit' in text


def test_backend_error_surface_is_compact_but_retains_detail_in_tooltip():
    text = _tools_source()
    assert 'text = "Backend unavailable."' in text
    assert 'self.connection_state.setToolTip(detail)' in text


def test_maintenance_button_has_explicit_renderhive_style():
    text = (ROOT / "ui" / "theme.py").read_text(encoding="utf-8")
    assert "QToolButton#MaintenanceButton" in text
    assert "QToolButton#MaintenanceButton::menu-indicator" in text
