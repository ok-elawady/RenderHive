"""Lucide-inspired vector SVG icons for RenderHive Maya Submitter.

Renders crisp, resolution-independent vector icons directly into QIcon and QPixmap instances,
matching the exact design language of the shadcn/ui Next.js frontend and Worker desktop client.
"""

from __future__ import absolute_import, print_function

from .qt_compat import QtCore, QtGui, QtSvg

_ICON_CACHE = {}

SVG_ICONS = {
    "info": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 16v-4"/>'
        '<path d="M12 8h.01"/>'
        '</svg>'
    ),
    "cube": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m21 16-9 5-9-5V8l9-5 9 5v8Z"/>'
        '<path d="M12 21V12"/>'
        '<path d="M3.27 6.96 12 12.01l8.73-5.05"/>'
        '</svg>'
    ),
    "layers": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
        '<polyline points="2 17 12 22 22 17"/>'
        '<polyline points="2 12 12 17 22 12"/>'
        '</svg>'
    ),
    "shield-check": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
        '<path d="m9 12 2 2 4-4"/>'
        '</svg>'
    ),
    "shield-alert": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
        '<line x1="12" y1="8" x2="12" y2="12"/>'
        '<line x1="12" y1="16" x2="12.01" y2="16"/>'
        '</svg>'
    ),
    "radio": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="2"/>'
        '<path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/>'
        '</svg>'
    ),
    "sliders": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/>'
        '<line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/>'
        '<line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/>'
        '<line x1="1" x2="7" y1="14" y2="14"/><line x1="9" x2="15" y1="8" y2="8"/>'
        '<line x1="17" x2="23" y1="16" y2="16"/>'
        '</svg>'
    ),
    "terminal": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="4 17 10 11 4 5"/>'
        '<line x1="12" x2="20" y1="19" y2="19"/>'
        '</svg>'
    ),
    "settings": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
        '</svg>'
    ),
    "refresh": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
        '<path d="M3 3v5h5"/>'
        '<path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/>'
        '<path d="M16 21h5v-5"/>'
        '</svg>'
    ),
    "check": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20 6 9 17l-5-5"/>'
        '</svg>'
    ),
    "x": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M18 6 6 18"/>'
        '<path d="m6 6 12 12"/>'
        '</svg>'
    ),
    "x-circle": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>'
        '</svg>'
    ),
    "check-circle": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/>'
        '</svg>'
    ),
    "copy": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
        '</svg>'
    ),
    "folder": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>'
        '</svg>'
    ),
    "search": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="11" cy="11" r="8"/>'
        '<path d="m21 21-4.3-4.3"/>'
        '</svg>'
    ),
    "send": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="22" y1="2" x2="11" y2="13"/>'
        '<polygon points="22 2 15 22 11 13 2 9 22 2"/>'
        '</svg>'
    ),
    "camera": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
        '<circle cx="12" cy="13" r="4"/>'
        '</svg>'
    ),
    "server": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect width="20" height="8" x="2" y="2" rx="2" ry="2"/>'
        '<rect width="20" height="8" x="2" y="14" rx="2" ry="2"/>'
        '<line x1="6" x2="6.01" y1="6" y2="6"/>'
        '<line x1="6" x2="6.01" y1="18" y2="18"/>'
        '</svg>'
    ),
    "cpu": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect width="16" height="16" x="4" y="4" rx="2"/>'
        '<rect width="6" height="6" x="9" y="9" rx="1"/>'
        '<path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/>'
        '<path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>'
        '</svg>'
    ),
    "activity": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'
        '</svg>'
    ),
    "zap": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
        '</svg>'
    ),
    "wrench": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'
        '</svg>'
    ),
    "maya": (
        '<svg viewBox="0 0 24 24" fill="{color}" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M4.348 0 .69 2.203v16.875l3.657-2.203h17.297V1.219c0-.67-.551-1.219-1.22-1.219H4.349zm18.297 3.75v14.125H4.627l-1.943 1.17v3.736c0 .67.55 1.219 1.218 1.219H23.31V3.75h-.664zm-14.471.025h2.937l1.885 7.508 1.977-7.48-.012-.028h2.857v9.354h-2.216v-6.04l-1.565 6.026v.014h-2.203l-1.656-6.28v6.28H8.174V3.775zm1.33 14.762h1.18l1.068 3.543h-.902l-.217-.773H9.568l-.197.773h-.88l1.013-3.543zm1.918 0h.932l.648 1.494.643-1.494h.894l-1.113 2.133v1.41h-.887v-1.406l-1.117-2.137zm3.826 0h1.18l1.068 3.543h-.9l-.217-.773h-1.065l-.197.773h-.88l1.011-3.543zm-5.156.582-.362 1.53h.73l-.368-1.53zm5.744 0-.36 1.53h.73l-.37-1.53z"/>'
        '</svg>'
    ),
    "arnold": (
        '<svg viewBox="0 0 24 24" fill="{color}" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>'
        '</svg>'
    ),
    "play": (
        '<svg viewBox="0 0 24 24" fill="{color}" stroke="{color}" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="6 3 20 12 6 21 6 3"/>'
        '</svg>'
    ),
    "check-square": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="9 11 12 14 22 4"/>'
        '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'
        '</svg>'
    ),
    "chevrons-down": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="7 13 12 18 17 13"/>'
        '<polyline points="7 6 12 11 17 6"/>'
        '</svg>'
    ),
    "chevrons-up": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="17 11 12 6 7 11"/>'
        '<polyline points="17 18 12 13 7 18"/>'
        '</svg>'
    ),
    "chevron-down": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="6 9 12 15 18 9"/>'
        '</svg>'
    ),
    "globe": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>'
        '<path d="M2 12h20"/>'
        '</svg>'
    ),
    "alert-triangle": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/>'
        '<line x1="12" y1="17" x2="12.01" y2="17"/>'
        '</svg>'
    ),
    "clock": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<polyline points="12 6 12 12 16 14"/>'
        '</svg>'
    ),
    "chevron-up": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="18 15 12 9 6 15"/>'
        '</svg>'
    ),
}


def get_icon(name, color="#F5F7FA", size=16):
    """Create a crisp, resolution-independent QIcon from Lucide SVG templates."""
    key = (str(name), str(color), int(size))
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    raw_svg = SVG_ICONS.get(name)
    if not raw_svg:
        return QtGui.QIcon()

    formatted_svg = raw_svg.format(color=color)
    byte_array = QtCore.QByteArray(formatted_svg.encode("utf-8"))
    renderer = QtSvg.QSvgRenderer(byte_array)
    
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    icon = QtGui.QIcon(pixmap)
    _ICON_CACHE[key] = icon
    return icon


def get_pixmap(name, color="#F5F7FA", size=16):
    """Return a crisp QPixmap from Lucide SVG templates."""
    raw_svg = SVG_ICONS.get(name)
    if not raw_svg:
        return QtGui.QPixmap()

    formatted_svg = raw_svg.format(color=color)
    byte_array = QtCore.QByteArray(formatted_svg.encode("utf-8"))
    renderer = QtSvg.QSvgRenderer(byte_array)
    
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


def icon_path(filename):
    """Return the absolute filesystem path to an icon or asset file."""
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for sub in ("icons", "assets"):
        path = os.path.join(base_dir, sub, filename)
        if os.path.isfile(path):
            return path
    return os.path.join(base_dir, "icons", filename)
