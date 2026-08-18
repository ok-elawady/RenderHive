from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import struct

ROOT = Path(__file__).resolve().parents[1]


def _png_size(path):
    try:
        from PIL import Image
        image = Image.open(path)
        return image.size
    except ImportError:
        with open(path, "rb") as f:
            data = f.read(24)
            w, h = struct.unpack(">II", data[16:24])
            return (w, h)


def test_shelf_uses_known_good_basename_icon_contract():
    shelf = ROOT / 'payload' / 'toolbar' / 'RenderHive.shelf'
    tree = ET.parse(str(shelf))
    root = tree.getroot()
    toolshelf = root.find('toolshelf')
    tool = root.find('tool')
    assert toolshelf is not None
    assert toolshelf.attrib == {'name': 'renderhive', 'label': 'RenderHive'}
    assert toolshelf.find('memberTool').attrib['name'] == 'renderhive_open'
    assert tool is not None
    assert tool.attrib['name'] == 'renderhive_open'
    assert tool.attrib['icon'] == 'renderhive'
    assert 'renderhive_houdini.bootstrap import show' in (tool.find('script').text or '')


def test_shelf_icon_is_available_on_houdini_ui_icon_path():
    icon_dir = ROOT / 'payload' / 'config' / 'Icons'
    assert (icon_dir / 'renderhive.svg').is_file()
    assert (icon_dir / 'renderhive.png').is_file()
    ET.parse(str(icon_dir / 'renderhive.svg'))
    assert _png_size(icon_dir / 'renderhive.png') == (32, 32)


def test_official_header_logo_is_packaged():
    assert _png_size(ROOT / 'payload' / 'icons' / 'renderhive_header_logo.png') == (52, 52)


def test_package_keeps_known_good_hpath_pattern():
    text = (ROOT / 'package' / 'renderhive.json.template').read_text(encoding='utf-8')
    data = json.loads(text.replace('__RENDERHIVE_HOUDINI_ROOT__', 'C:/RenderHive/Houdini/2.0.5'))
    assert data['hpath'] == '$RENDERHIVE_HOUDINI_ROOT'
    assert data['load_package_once'] is True
    env = data['env']
    assert {'RENDERHIVE_HOUDINI_ROOT': 'C:/RenderHive/Houdini/2.0.5'} in env
    assert {'var': 'PYTHONPATH', 'value': '$RENDERHIVE_HOUDINI_ROOT/python_libs', 'method': 'prepend'} in env


def test_shelf_and_panel_share_same_icon_name():
    shelf = (ROOT / 'payload' / 'toolbar' / 'RenderHive.shelf').read_text(encoding='utf-8')
    panel = (ROOT / 'payload' / 'python_panels' / 'renderhive.pypanel').read_text(encoding='utf-8')
    assert 'icon="renderhive"' in shelf
    assert 'icon="renderhive"' in panel
