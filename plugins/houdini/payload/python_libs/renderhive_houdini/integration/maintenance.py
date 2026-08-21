"""Runtime maintenance actions initiated from the Houdini UI."""

from __future__ import absolute_import

import json
import os


def current_package_json():
    try:
        import hou
        root = str(hou.getenv("HOUDINI_USER_PREF_DIR") or "")
    except Exception:
        root = ""
    return os.path.join(root, "packages", "renderhive.json") if root else ""


def uninstall_current_profile():
    path = current_package_json()
    if not path or not os.path.isfile(path):
        return False, "RenderHive package registration was not found for this Houdini profile."
    disabled = path + ".disabled"
    try:
        if os.path.exists(disabled):
            os.remove(disabled)
        os.replace(path, disabled)
        return True, "RenderHive was disabled for this Houdini profile. Restart Houdini to complete removal."
    except Exception as error:
        return False, "Could not disable RenderHive: {}".format(error)
