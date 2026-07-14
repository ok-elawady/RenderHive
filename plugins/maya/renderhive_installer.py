import os
import sys
import shutil
import importlib

import maya.cmds as cmds
import maya.mel as mel


SHELF_NAME = "RenderHive"
BUTTON_LABEL = "RenderHive"


def copy_package_to_maya_scripts(source_dir):
    user_scripts_dir = cmds.internalVar(userScriptDir=True)
    install_dir = os.path.join(user_scripts_dir, "RenderHive")

    if os.path.exists(install_dir):
        shutil.rmtree(install_dir)

    ignore_names = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "logs",
        "queue",
    }

    def ignore_func(dir_path, names):
        ignored = []

        for name in names:
            if name in ignore_names:
                ignored.append(name)

            if name.endswith(".pyc"):
                ignored.append(name)

        return ignored

    shutil.copytree(source_dir, install_dir, ignore=ignore_func)

    return install_dir


def create_basic_icon(install_dir):
    icons_dir = os.path.join(install_dir, "icons")

    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)

    icon_path = os.path.join(icons_dir, "renderhive_icon.png")

    xpm_data = [
        "32 32 5 1",
        "  c None",
        ". c #111827",
        "+ c #F59E0B",
        "@ c #FFFFFF",
        "# c #2563EB",
        "................................",
        "................................",
        "......++++++++++++++++++++......",
        ".....++++++++++++++++++++++.....",
        "....+++++............+++++......",
        "...+++++..............+++++.....",
        "...++++....########....++++.....",
        "...++++...##########...++++.....",
        "...++++...####..####...++++.....",
        "...++++...####..####...++++.....",
        "...++++...##########...++++.....",
        "...++++...##########...++++.....",
        "...++++...####..####...++++.....",
        "...++++...####..####...++++.....",
        "...++++...####..####...++++.....",
        "...++++...####..####...++++.....",
        "...++++................++++.....",
        "...++++....@@@@@@@@....++++.....",
        "...++++....@@@@@@@@....++++.....",
        "...++++....@@....@@....++++.....",
        "...++++....@@....@@....++++.....",
        "...++++....@@@@@@@@....++++.....",
        "...++++....@@@@@@@@....++++.....",
        "...++++................++++.....",
        "...+++++..............+++++.....",
        "....+++++............+++++......",
        ".....++++++++++++++++++++++.....",
        "......++++++++++++++++++++......",
        "................................",
        "................................",
        "................................",
        "................................",
    ]

    with open(icon_path, "w") as f:
        f.write("/* XPM */\n")
        f.write("static char * renderhive_icon_xpm[] = {\n")

        for i, line in enumerate(xpm_data):
            comma = "," if i < len(xpm_data) - 1 else ""
            f.write('"{}"{}\n'.format(line, comma))

        f.write("};\n")

    return icon_path


def get_shelf_top_level():
    return mel.eval("$tmp = $gShelfTopLevel")


def ensure_shelf():
    shelf_top = get_shelf_top_level()

    shelves = cmds.tabLayout(
        shelf_top,
        query=True,
        childArray=True
    ) or []

    if SHELF_NAME not in shelves:
        cmds.shelfLayout(SHELF_NAME, parent=shelf_top)

    cmds.tabLayout(shelf_top, edit=True, selectTab=SHELF_NAME)

    return SHELF_NAME


def remove_old_button(shelf_name):
    children = cmds.shelfLayout(
        shelf_name,
        query=True,
        childArray=True
    ) or []

    for child in children:
        try:
            label = cmds.shelfButton(child, query=True, label=True)
            annotation = cmds.shelfButton(child, query=True, annotation=True)

            if label == BUTTON_LABEL or "RenderHive" in annotation:
                cmds.deleteUI(child)

        except Exception:
            pass


def create_shelf_button(install_dir):
    shelf_name = ensure_shelf()
    remove_old_button(shelf_name)

    icon_path = create_basic_icon(install_dir)

    command = """
import sys
import importlib

renderhive_path = r"{install_dir}"

if renderhive_path not in sys.path:
    sys.path.insert(0, renderhive_path)

import renderhive_maya_submitter
importlib.reload(renderhive_maya_submitter)

renderhive_maya_submitter.show_submitter()
""".format(install_dir=install_dir.replace("\\", "\\\\"))

    cmds.shelfButton(
        parent=shelf_name,
        label=BUTTON_LABEL,
        annotation="Open RenderHive Maya Submitter",
        image=icon_path,
        imageOverlayLabel="RH",
        sourceType="python",
        command=command
    )

    try:
        mel.eval("saveAllShelves $gShelfTopLevel;")
    except Exception:
        pass


def write_install_info(install_dir, source_dir):
    info_path = os.path.join(install_dir, "renderhive_install_info.json")

    data = {
        "source_dir": os.path.abspath(source_dir),
        "install_dir": os.path.abspath(install_dir)
    }

    import json

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return info_path


def install_from_drag_drop(source_dir):
    install_dir = copy_package_to_maya_scripts(source_dir)
    write_install_info(install_dir, source_dir)
    create_shelf_button(install_dir)

    cmds.confirmDialog(
        title="RenderHive Installed",
        message=(
            "RenderHive was installed successfully.\n\n"
            "Installed to:\n{}\n\n"
            "A RenderHive shelf button was created."
        ).format(install_dir),
        button=["OK"],
        icon="information"
    )


def get_installed_package_dir():
    user_scripts_dir = cmds.internalVar(userScriptDir=True)
    return os.path.join(user_scripts_dir, "RenderHive")


def remove_renderhive_shelf_button():
    try:
        shelf_top = get_shelf_top_level()

        shelves = cmds.tabLayout(
            shelf_top,
            query=True,
            childArray=True
        ) or []

        for shelf_name in shelves:
            children = cmds.shelfLayout(
                shelf_name,
                query=True,
                childArray=True
            ) or []

            for child in children:
                try:
                    label = cmds.shelfButton(child, query=True, label=True)
                    annotation = cmds.shelfButton(
                        child, query=True, annotation=True)

                    if label == BUTTON_LABEL or "RenderHive" in annotation:
                        cmds.deleteUI(child)

                except Exception:
                    pass

        try:
            mel.eval("saveAllShelves $gShelfTopLevel;")
        except Exception:
            pass

    except Exception as e:
        print("RenderHive shelf removal error:", e)


def close_renderhive_windows():
    windows = [
        "renderHiveMayaSubmitter"
    ]

    for win in windows:
        try:
            if cmds.window(win, exists=True):
                cmds.deleteUI(win)
        except Exception:
            pass


def uninstall_renderhive(confirm=True):
    """
    Uninstall RenderHive from Maya scripts folder.
    This does NOT delete the original RenderHive_Maya package folder.
    """

    install_dir = get_installed_package_dir()

    if confirm:
        result = cmds.confirmDialog(
            title="Uninstall RenderHive",
            message=(
                "This will remove the RenderHive shelf button and delete the installed Maya copy:\n\n"
                "{}\n\n"
                "The original RenderHive_Maya project folder will NOT be deleted.\n\n"
                "Continue?"
            ).format(install_dir),
            button=["Uninstall", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
            icon="warning"
        )

        if result != "Uninstall":
            return False

    close_renderhive_windows()
    remove_renderhive_shelf_button()

    deleted_package = False

    if os.path.exists(install_dir):
        try:
            shutil.rmtree(install_dir)
            deleted_package = True
        except Exception as e:
            cmds.confirmDialog(
                title="RenderHive Uninstall Warning",
                message=(
                    "Shelf button was removed, but RenderHive folder could not be deleted:\n\n"
                    "{}\n\n"
                    "Error:\n{}"
                ).format(install_dir, e),
                button=["OK"],
                icon="warning"
            )
            return False

    cmds.confirmDialog(
        title="RenderHive Uninstalled",
        message=(
            "RenderHive was uninstalled from Maya.\n\n"
            "Shelf button removed: Yes\n"
            "Installed folder deleted: {}\n\n"
            "Restart Maya if the shelf still appears visually."
        ).format("Yes" if deleted_package else "Folder was already missing"),
        button=["OK"],
        icon="information"
    )

    return True
