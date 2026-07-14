from __future__ import print_function

import os

import maya.cmds as cmds


SHELF_ICON_NAME = "renderhive_shelf_icon.png"
HEADER_LOGO_NAME = "renderhive_header_logo.png"


def get_package_root():
    return os.path.dirname(os.path.abspath(__file__))


def get_icon_path(filename):
    path = os.path.join(get_package_root(), "icons", filename)
    return os.path.normpath(path).replace("\\", "/")


def get_shelf_icon_path():
    return get_icon_path(SHELF_ICON_NAME)


def get_header_logo_path():
    return get_icon_path(HEADER_LOGO_NAME)


def _button_matches_renderhive(button):
    values = []

    for flag in ("label", "annotation", "command"):
        try:
            values.append(
                cmds.shelfButton(
                    button,
                    query=True,
                    **{flag: True}
                ) or ""
            )
        except Exception:
            pass

    combined = " ".join(str(value) for value in values).lower()
    return (
        "renderhive" in combined
        or "renderhive_maya_submitter" in combined
    )


def find_renderhive_shelf_buttons():
    buttons = []

    try:
        import maya.mel as mel
        shelf_top = mel.eval("$tmp = $gShelfTopLevel")
    except Exception:
        shelf_top = ""

    if not shelf_top or not cmds.tabLayout(shelf_top, exists=True):
        return buttons

    shelves = cmds.tabLayout(
        shelf_top,
        query=True,
        childArray=True
    ) or []

    for shelf in shelves:
        try:
            children = cmds.shelfLayout(
                shelf,
                query=True,
                childArray=True
            ) or []
        except Exception:
            continue

        for child in children:
            if not cmds.shelfButton(child, exists=True):
                continue

            if _button_matches_renderhive(child):
                buttons.append(child)

    return buttons


def apply_shelf_icon():
    """Apply the RenderHive icon and remove every text/overlay label."""

    icon_path = get_shelf_icon_path()

    if not os.path.isfile(icon_path):
        return False

    changed = False

    for button in find_renderhive_shelf_buttons():
        try:
            cmds.shelfButton(
                button,
                edit=True,
                label="",
                annotation="Open RenderHive Maya Submitter",
                image=icon_path,
                image1=icon_path,
                imageOverlayLabel="",
                style="iconOnly"
            )
            changed = True
        except Exception:
            try:
                cmds.shelfButton(
                    button,
                    edit=True,
                    label="",
                    image1=icon_path,
                    imageOverlayLabel=""
                )
                changed = True
            except Exception:
                pass

    return changed
