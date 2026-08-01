"""Safe icon path helpers for the Houdini package payload."""

from __future__ import absolute_import

import os


def payload_root():
    return os.environ.get("RENDERHIVE_HOUDINI_ROOT", "")


def icon_path(filename="renderhive.svg"):
    root = payload_root()
    if not root:
        return ""
    path = os.path.join(root, "icons", filename)
    return path if os.path.isfile(path) else ""
