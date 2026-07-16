from __future__ import print_function

import importlib
import json
import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel


SHELF_NAME = "RenderHive"
BUTTON_ANNOTATION = "Open RenderHive Maya Submitter"


def get_installed_package_dir():
    return os.path.join(
        cmds.internalVar(
            userScriptDir=True
        ),
        "RenderHive"
    )


def _ignore_runtime_content(
    directory,
    names,
):
    ignored = []

    ignored_names = {
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "backup",
        "backups",
        "logs",
        "reports",
    }

    for name in names:
        lowered = name.lower()

        if (
            name in ignored_names
            or lowered.startswith("backup_")
            or lowered.endswith(".zip")
            or lowered.endswith(".pyc")
        ):
            ignored.append(
                name
            )

    return ignored


def copy_package_to_maya_scripts(
    source_dir
):
    install_dir = get_installed_package_dir()

    if os.path.isdir(
        install_dir
    ):
        shutil.rmtree(
            install_dir
        )

    shutil.copytree(
        source_dir,
        install_dir,
        ignore=_ignore_runtime_content,
    )

    return install_dir


def get_shelf_top_level():
    return mel.eval(
        "$tmp = $gShelfTopLevel"
    )


def ensure_shelf():
    shelf_top = get_shelf_top_level()
    shelves = cmds.tabLayout(
        shelf_top,
        query=True,
        childArray=True
    ) or []

    if SHELF_NAME not in shelves:
        cmds.shelfLayout(
            SHELF_NAME,
            parent=shelf_top
        )

    cmds.tabLayout(
        shelf_top,
        edit=True,
        selectTab=SHELF_NAME
    )

    return SHELF_NAME


def _is_renderhive_button(
    button
):
    values = []

    for flag in (
        "label",
        "annotation",
        "command",
    ):
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

    return "renderhive" in " ".join(
        str(value)
        for value in values
    ).lower()


def remove_renderhive_shelf_buttons():
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
                if _is_renderhive_button(
                    child
                ):
                    cmds.deleteUI(
                        child
                    )

        try:
            mel.eval(
                "saveAllShelves $gShelfTopLevel;"
            )
        except Exception:
            pass

    except Exception:
        pass


def create_shelf_button(
    install_dir
):
    shelf_name = ensure_shelf()
    remove_renderhive_shelf_buttons()

    icon_path = os.path.join(
        install_dir,
        "icons",
        "renderhive_shelf_icon.png"
    ).replace(
        "\\",
        "/"
    )

    command = """
import importlib
import os
import sys

renderhive_path = r"{install_dir}"

if renderhive_path in sys.path:
    sys.path.remove(renderhive_path)
sys.path.insert(0, renderhive_path)

import renderhive_maya_submitter
importlib.reload(renderhive_maya_submitter)
renderhive_maya_submitter.show_submitter()
""".format(
        install_dir=install_dir.replace(
            "\\",
            "\\\\"
        )
    )

    cmds.shelfButton(
        parent=shelf_name,
        label="",
        annotation=BUTTON_ANNOTATION,
        image=icon_path,
        image1=icon_path,
        imageOverlayLabel="",
        style="iconOnly",
        sourceType="python",
        command=command,
    )

    try:
        mel.eval(
            "saveAllShelves $gShelfTopLevel;"
        )
    except Exception:
        pass


def write_install_info(
    install_dir,
    source_dir,
):
    info_path = os.path.join(
        install_dir,
        "renderhive_install_info.json"
    )

    with open(
        info_path,
        "w",
        encoding="utf-8"
    ) as handle:
        json.dump(
            {
                "source_dir": os.path.abspath(
                    source_dir
                ),
                "install_dir": os.path.abspath(
                    install_dir
                ),
            },
            handle,
            indent=4,
        )

    return info_path


def install_from_drag_drop(
    source_dir
):
    install_dir = copy_package_to_maya_scripts(
        source_dir
    )
    write_install_info(
        install_dir,
        source_dir
    )
    create_shelf_button(
        install_dir
    )

    cmds.confirmDialog(
        title="RenderHive Installed",
        message=(
            "RenderHive was installed successfully.\n\n"
            "Installed to:\n{}\n\n"
            "A RenderHive shelf button was created."
        ).format(
            install_dir
        ),
        button=["OK"],
        icon="information",
    )


def close_renderhive_windows():
    try:
        from ui.qt_compat import QtWidgets

        app = QtWidgets.QApplication.instance()

        if app is not None:
            for widget in app.topLevelWidgets():
                if widget.objectName() in (
                    "RenderHiveWindow",
                    "RenderHiveQtSubmitter",
                ):
                    widget.close()
                    widget.deleteLater()
    except Exception:
        pass

    try:
        if cmds.window(
            "renderHiveMayaSubmitter",
            exists=True
        ):
            cmds.deleteUI(
                "renderHiveMayaSubmitter"
            )
    except Exception:
        pass


def uninstall_renderhive(
    confirm=True
):
    install_dir = get_installed_package_dir()

    if confirm:
        result = cmds.confirmDialog(
            title="Uninstall RenderHive",
            message=(
                "Remove the RenderHive shelf button and installed Maya copy?\n\n"
                "{}\n\n"
                "The original source package will not be deleted."
            ).format(
                install_dir
            ),
            button=["Uninstall", "Cancel"],
            defaultButton="Cancel",
            cancelButton="Cancel",
            dismissString="Cancel",
            icon="warning",
        )

        if result != "Uninstall":
            return False

    close_renderhive_windows()
    remove_renderhive_shelf_buttons()

    if os.path.isdir(
        install_dir
    ):
        shutil.rmtree(
            install_dir
        )
        
    # Clear the plugin from Maya's python memory cache
    import sys
    modules_to_remove = []
    for mod_name, mod in sys.modules.items():
        if getattr(mod, "__file__", None) and install_dir in getattr(mod, "__file__", ""):
            modules_to_remove.append(mod_name)
        elif mod_name.startswith("renderhive_"):
            modules_to_remove.append(mod_name)
            
    for mod_name in modules_to_remove:
        try:
            del sys.modules[mod_name]
        except KeyError:
            pass

    cmds.confirmDialog(
        title="RenderHive Uninstalled",
        message=(
            "RenderHive was removed from Maya.\n\n"
            "Restart Maya if the shelf still appears."
        ),
        button=["OK"],
        icon="information",
    )

    return True
